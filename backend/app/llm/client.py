"""Cliente LLM via LiteLLM Proxy (protocolo OpenAI).

A aplicação nunca fala com a OpenRouter direto: toda chamada passa pelo
LiteLLM Proxy configurado em ``settings.litellm_base_url``.
"""

from functools import lru_cache

from openai import AsyncOpenAI
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


async def structured_completion[BaseModelT: BaseModel](
    model: str,
    system: str,
    user: str,
    schema: type[BaseModelT],
    temperature: float = 0.0,
    client: AsyncOpenAI | None = None,
) -> BaseModelT:
    """Chama o LLM exigindo JSON conforme ``schema`` e valida o resultado.

    Structured output não é garantia: o content é sempre validado com
    ``model_validate_json``. Na primeira falha de validação, reenvia a conversa
    com o erro pedindo correção; na segunda falha, levanta ``LLMOutputError``.
    """
    llm = client or get_client()
    messages: list[ChatCompletionMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=system),
        ChatCompletionUserMessageParam(role="user", content=user),
    ]
    response_format = ResponseFormatJSONSchema(
        type="json_schema",
        json_schema=JSONSchema(
            name=schema.__name__,
            schema=schema.model_json_schema(),
            strict=True,
        ),
    )

    last_error: Exception | None = None
    for _attempt in range(2):
        completion = await llm.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format=response_format,
        )
        content = completion.choices[0].message.content
        if not content:
            last_error = ValueError("resposta sem conteúdo (content vazio ou None)")
        else:
            try:
                return schema.model_validate_json(content)
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
