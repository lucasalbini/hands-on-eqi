import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.llm.client import LLMOutputError, structured_completion


class SampleSchema(BaseModel):
    name: str
    value: int


def _completion_with(content: str | None) -> MagicMock:
    completion = MagicMock()
    completion.choices = [MagicMock()]
    completion.choices[0].message.content = content
    return completion


def _mock_client(*contents: str | None) -> AsyncOpenAI:
    client = MagicMock(spec=AsyncOpenAI)
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=[_completion_with(c) for c in contents])
    return client


VALID_JSON = json.dumps({"name": "ok", "value": 42})


async def _call(client: AsyncOpenAI, **overrides: Any) -> SampleSchema:
    kwargs: dict[str, Any] = {
        "model": "extraction-model",
        "system": "system prompt",
        "user": "user prompt",
        "schema": SampleSchema,
        "client": client,
    }
    kwargs.update(overrides)
    return await structured_completion(**kwargs)


async def test_valid_json_returns_schema_instance() -> None:
    client = _mock_client(VALID_JSON)

    result = await _call(client)

    assert result == SampleSchema(name="ok", value=42)
    create_mock: AsyncMock = client.chat.completions.create  # type: ignore[assignment]
    assert create_mock.await_count == 1


async def test_malformed_json_then_valid_retries_with_error_feedback() -> None:
    client = _mock_client("not json at all", VALID_JSON)

    result = await _call(client)

    assert result == SampleSchema(name="ok", value=42)
    create_mock: AsyncMock = client.chat.completions.create  # type: ignore[assignment]
    assert create_mock.await_count == 2
    retry_messages = create_mock.await_args_list[1].kwargs["messages"]
    assert retry_messages[2] == {"role": "assistant", "content": "not json at all"}
    assert retry_messages[3]["role"] == "user"
    assert "Sua resposta anterior falhou na validação" in retry_messages[3]["content"]
    assert "Responda apenas JSON válido conforme o schema." in retry_messages[3]["content"]


async def test_malformed_json_twice_raises_llm_output_error() -> None:
    client = _mock_client("{broken", "{still broken")

    with pytest.raises(LLMOutputError):
        await _call(client)

    create_mock: AsyncMock = client.chat.completions.create  # type: ignore[assignment]
    assert create_mock.await_count == 2


async def test_none_content_is_treated_as_failure() -> None:
    client = _mock_client(None, None)

    with pytest.raises(LLMOutputError):
        await _call(client)

    create_mock: AsyncMock = client.chat.completions.create  # type: ignore[assignment]
    assert create_mock.await_count == 2


async def test_none_content_then_valid_succeeds_on_retry() -> None:
    client = _mock_client(None, VALID_JSON)

    result = await _call(client)

    assert result == SampleSchema(name="ok", value=42)


async def test_temperature_and_response_format_are_forwarded() -> None:
    client = _mock_client(VALID_JSON)

    await _call(client, temperature=0.7)

    create_mock: AsyncMock = client.chat.completions.create  # type: ignore[assignment]
    kwargs = create_mock.await_args.kwargs
    assert kwargs["model"] == "extraction-model"
    assert kwargs["temperature"] == 0.7
    assert kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "SampleSchema",
            "schema": SampleSchema.model_json_schema(),
            "strict": True,
        },
    }
    assert kwargs["messages"][0] == {"role": "system", "content": "system prompt"}
    assert kwargs["messages"][1] == {"role": "user", "content": "user prompt"}


async def test_temperature_defaults_to_zero() -> None:
    client = _mock_client(VALID_JSON)

    await _call(client)

    create_mock: AsyncMock = client.chat.completions.create  # type: ignore[assignment]
    assert create_mock.await_args.kwargs["temperature"] == 0.0
