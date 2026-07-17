import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Analysis, Contract, ContractStatus, ExtractedField, PipelineStage
from tests.integration.test_pipeline_extraction import VALID_EXTRACTION, _upload_fixture

VALID_ANALYSIS = {
    "summary": "Contrato de desenvolvimento de software entre ACME e cliente.",
    "ai_analysis": {
        "overall_assessment": "Contrato equilibrado, com ressalvas na cláusula de multa.",
        "risks": [
            {
                "title": "Multa rescisória desproporcional",
                "description": "Multa de 50% sobre o valor total.",
                "severity": "alta",
                "clause_ref": "Cláusula 8ª",
            }
        ],
        "obligations": [
            {
                "party": "provider",
                "description": "Entregar relatório mensal.",
                "clause_ref": None,
            }
        ],
        "attention_points": [{"description": "Foro difere da sede.", "clause_ref": None}],
    },
}


async def test_full_pipeline_completes_and_persists_analysis(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    llm = fake_llm([json.dumps(VALID_EXTRACTION), json.dumps(VALID_ANALYSIS)])
    contract_id = await _upload_fixture(client)

    contract = await db_session.get(Contract, contract_id)
    assert contract is not None
    assert contract.status is ContractStatus.COMPLETED
    assert contract.current_stage is None

    analysis = (await db_session.execute(select(Analysis))).scalar_one()
    assert analysis.prompt_version == "analysis_v1"
    assert analysis.summary.startswith("Contrato de desenvolvimento")
    assert analysis.ai_analysis["risks"][0]["severity"] == "alta"
    assert len(llm.calls) == 2


async def test_analysis_call_receives_validated_metadata_and_text(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    llm = fake_llm([json.dumps(VALID_EXTRACTION), json.dumps(VALID_ANALYSIS)])
    await _upload_fixture(client)

    analysis_call = llm.calls[1]
    user_message = analysis_call["messages"][1]["content"]
    assert "<contract_text>" in user_message
    # Metadados validados entram normalizados (data ISO, CNPJ formatado).
    assert "2025-11-11" in user_message
    assert "11.222.333/0001-81" in user_message
    assert analysis_call["temperature"] == 0.3


async def test_invalid_analysis_output_fails_at_analyze_keeping_extraction(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    bad = json.loads(json.dumps(VALID_ANALYSIS))
    bad["ai_analysis"]["risks"][0]["severity"] = "critica"  # fora do enum
    llm = fake_llm([json.dumps(VALID_EXTRACTION), json.dumps(bad), json.dumps(bad)])
    contract_id = await _upload_fixture(client)

    contract = await db_session.get(Contract, contract_id)
    assert contract is not None
    assert contract.status is ContractStatus.FAILED
    assert contract.current_stage is PipelineStage.ANALYZE
    assert len(llm.calls) == 3  # extração + análise + retry da análise

    # A extração sobreviveu à falha da análise.
    fields = (await db_session.execute(select(ExtractedField))).scalars().all()
    assert len(fields) == 17
    assert (await db_session.execute(select(Analysis))).scalar_one_or_none() is None


async def test_get_contract_returns_full_detail(client: httpx.AsyncClient, fake_llm: Any) -> None:
    fake_llm([json.dumps(VALID_EXTRACTION), json.dumps(VALID_ANALYSIS)])
    contract_id = await _upload_fixture(client)

    response = await client.get(f"/api/v1/contracts/{contract_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"

    cnpj = body["extraction"]["fields"]["provider.cnpj"]
    assert cnpj == {
        "llm_value": "11.222.333/0001-81",
        "normalized_value": "11.222.333/0001-81",
        "is_valid": True,
        "validation_error": None,
        "corrected_value": None,
        "effective_value": "11.222.333/0001-81",
    }
    assert body["extraction"]["prompt_version"] == "extraction_v1"
    assert body["analysis"]["summary"].startswith("Contrato")
    assert body["analysis"]["ai_analysis"]["overall_assessment"].startswith("Contrato equilibrado")


async def test_get_contract_failed_at_analyze_returns_extraction_without_analysis(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    fake_llm([json.dumps(VALID_EXTRACTION), "not json", "still not json"])
    contract_id = await _upload_fixture(client)

    response = await client.get(f"/api/v1/contracts/{contract_id}")

    body = response.json()
    assert body["status"] == "failed"
    assert body["current_stage"] == "analyze"
    assert body["extraction"] is not None
    assert body["analysis"] is None
    assert body["error_message"]


async def test_get_unknown_contract_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/contracts/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_list_shows_effective_contract_type_after_completion(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    fake_llm([json.dumps(VALID_EXTRACTION), json.dumps(VALID_ANALYSIS)])
    await _upload_fixture(client)

    response = await client.get("/api/v1/contracts")

    items = response.json()
    assert items[0]["status"] == "completed"
    assert items[0]["contract_type"] == "Desenvolvimento de Software"
