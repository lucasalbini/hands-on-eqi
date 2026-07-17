"""Cliente LLM via LiteLLM Proxy (protocolo OpenAI).

A aplicação nunca fala com a OpenRouter direto: toda chamada passa pelo
LiteLLM Proxy configurado em ``settings.litellm_base_url``.
"""

import json
from functools import lru_cache
from typing import Any

from openai import AsyncOpenAI, BadRequestError
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.shared_params import ResponseFormatJSONSchema
from openai.types.shared_params.response_format_json_schema import JSONSchema
from pydantic import BaseModel, ValidationError

from app.config import settings

_RETRY_TEMPLATE = (
    "Sua resposta anterior falhou na validação: {erro}. "
    "Responda apenas JSON válido conforme o schema."
)

_SCHEMA_TEMPLATE = (
    "\n\nResponda APENAS com um JSON válido (sem texto ao redor, sem cercas de código) "
    "que satisfaça exatamente este JSON Schema:\n{schema}"
)


class LLMOutputError(Exception):
    """Falha definitiva ao obter output estruturado válido do LLM."""


@lru_cache(maxsize=1)
def get_client() -> AsyncOpenAI:
    """Client compartilhado apontando para o LiteLLM Proxy (lazy, cacheado)."""
    return AsyncOpenAI(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        timeout=120.0,
        max_retries=2,
    )


def _unsupported_structured_output(exc: BadRequestError) -> bool:
    """Distingue o 'provider não suporta structured output' de um 400 legítimo."""
    message = str(exc).lower()
    return "structured_output" in message or "response_format" in message


async def structured_completion[BaseModelT: BaseModel](
    model: str,
    system: str,
    user: str,
    schema: type[BaseModelT],
    temperature: float = 0.0,
    client: AsyncOpenAI | None = None,
) -> BaseModelT:
    """Chama o LLM exigindo JSON conforme ``schema`` e valida o resultado.

    Tenta primeiro o structured output nativo (``json_schema`` strict). Se o
    provider não suportar (ex.: rota OpenRouter→Anthropic sem structured outputs),
    degrada para JSON via prompt com o schema embutido. Em ambos os modos o
    content é sempre validado com Pydantic, com um retry pedindo correção.
    """
    llm = client or get_client()
    response_format = ResponseFormatJSONSchema(
        type="json_schema",
        json_schema=JSONSchema(
            name=schema.__name__, schema=schema.model_json_schema(), strict=True
        ),
    )

    try:
        return await _complete_and_validate(
            llm, model, system, user, schema, temperature, response_format
        )
    except BadRequestError as exc:
        if not _unsupported_structured_output(exc):
            raise
        # Fallback: sem response_format, schema embutido no prompt.
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        user_with_schema = user + _SCHEMA_TEMPLATE.format(schema=schema_json)
        return await _complete_and_validate(
            llm, model, system, user_with_schema, schema, temperature, None
        )


async def _complete_and_validate[BaseModelT: BaseModel](
    llm: AsyncOpenAI,
    model: str,
    system: str,
    user: str,
    schema: type[BaseModelT],
    temperature: float,
    response_format: ResponseFormatJSONSchema | None,
) -> BaseModelT:
    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system),
        ChatCompletionUserMessageParam(role="user", content=user),
    ]
    # response_format é omitido no modo fallback (provider sem structured output).
    extra: dict[str, Any] = {} if response_format is None else {"response_format": response_format}

    last_error: Exception | None = None
    for _attempt in range(2):
        completion = await llm.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            **extra,
        )
        content = completion.choices[0].message.content
        if not content:
            last_error = ValueError("resposta sem conteúdo (content vazio ou None)")
        else:
            try:
                return schema.model_validate_json(_strip_code_fences(content))
            except ValidationError as exc:
                last_error = exc
        # Reenvia a conversa + erro pedindo correção (retry único).
        messages.append(
            ChatCompletionAssistantMessageParam(role="assistant", content=content or "")
        )
        messages.append(
            ChatCompletionUserMessageParam(
                role="user", content=_RETRY_TEMPLATE.format(erro=last_error)
            )
        )

    raise LLMOutputError(
        f"Output do modelo {model!r} inválido para {schema.__name__} após retry: {last_error}"
    ) from last_error


def _strip_code_fences(content: str) -> str:
    """Remove cercas ```json ... ``` que alguns modelos adicionam no modo prompt."""
    text = content.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    lines = lines[1:]  # descarta a linha de abertura (``` ou ```json)
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
