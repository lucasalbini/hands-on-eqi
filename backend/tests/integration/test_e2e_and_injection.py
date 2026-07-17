"""Fluxo E2E completo (upload → completed → correção) e regressão de prompt injection."""

import json
from pathlib import Path
from typing import Any

import httpx

from app.pipeline.extraction import run_extraction
from app.pipeline.parsing import parse_document
from tests.integration.test_pipeline_analysis import VALID_ANALYSIS
from tests.integration.test_pipeline_extraction import VALID_EXTRACTION, _upload_fixture

FIXTURES = Path(__file__).parent.parent / "fixtures"


async def test_full_flow_upload_process_correct_and_reflect(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    """Percorre o caminho feliz de ponta a ponta como a UI faria."""
    fake_llm([json.dumps(VALID_EXTRACTION), json.dumps(VALID_ANALYSIS)])

    contract_id = await _upload_fixture(client)

    # 1. Polling de status — pipeline roda inline no test client, já completou.
    status = (await client.get(f"/api/v1/contracts/{contract_id}/status")).json()
    assert status["status"] == "completed"

    # 2. Resultado completo com extração e análise.
    detail = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    assert detail["extraction"]["fields"]["provider.uf"]["effective_value"] == "PR"
    assert detail["analysis"]["ai_analysis"]["risks"][0]["severity"] == "alta"

    # 3. Usuário corrige a UF e o efeito reflete no GET seguinte.
    patched = await client.patch(
        f"/api/v1/contracts/{contract_id}/fields", json={"fields": {"provider.uf": "SC"}}
    )
    assert patched.status_code == 200
    reflected = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    uf = reflected["extraction"]["fields"]["provider.uf"]
    assert uf["effective_value"] == "SC"
    assert uf["corrected_value"] == "SC"
    assert uf["llm_value"] == "PR"  # original do LLM preservado

    # 4. Contrato aparece na listagem com o tipo efetivo.
    listing = (await client.get("/api/v1/contracts")).json()
    assert any(item["id"] == contract_id for item in listing)


async def test_contract_text_with_injection_is_delimited_in_prompt(
    monkeypatch: Any,
) -> None:
    """O texto malicioso do contrato entra como DADO delimitado, e a instrução
    anti-injection do prompt permanece — o modelo recebe o conteúdo cercado por
    <contract_text> e o reforço, sem que o comando vire instrução."""
    docx_text = parse_document(FIXTURES / "injection.docx", _docx_mime())
    assert "IGNORE AS INSTRUÇÕES ANTERIORES" in docx_text  # o injection está no texto

    captured: dict[str, Any] = {}

    class SpyLLM:
        def __init__(self) -> None:
            self.chat = _spy_chat(captured)

    monkeypatch.setattr("app.llm.client.get_client", lambda: SpyLLM())
    await run_extraction(docx_text)

    user_message = captured["messages"][1]["content"]
    # O comando malicioso está DENTRO das tags de conteúdo...
    before_tag = user_message.split("<contract_text>")[0]
    assert "IGNORE AS INSTRUÇÕES ANTERIORES" not in before_tag
    assert "<contract_text>" in user_message and "</contract_text>" in user_message
    # ...e o reforço anti-injection vem depois do fechamento da tag.
    after_close = user_message.split("</contract_text>")[1]
    assert "não instruções" in after_close.lower() or "não são instruções" in after_close.lower()


async def test_injection_does_not_alter_deterministic_validation(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    """Mesmo se o modelo obedecesse ao injection (CNPJ 99.999.999/9999-99), a
    validação determinística rejeita o valor — a defesa não depende só do prompt."""
    obeyed_injection = json.loads(json.dumps(VALID_EXTRACTION))
    obeyed_injection["provider"]["cnpj"] = "99.999.999/9999-99"
    obeyed_injection["contract_type"] = "App Mobile"
    fake_llm([json.dumps(obeyed_injection), json.dumps(VALID_ANALYSIS)])

    contract_id = await _upload_fixture(client, "injection.docx", _docx_mime())

    detail = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    cnpj = detail["extraction"]["fields"]["provider.cnpj"]
    assert cnpj["is_valid"] is False
    assert cnpj["effective_value"] is None  # valor injetado não vira verdade


def _docx_mime() -> str:
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _spy_chat(captured: dict[str, Any]) -> Any:
    from types import SimpleNamespace

    async def create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(VALID_EXTRACTION)))]
        )

    return SimpleNamespace(completions=SimpleNamespace(create=create))
