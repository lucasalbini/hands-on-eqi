import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, ExtractedField
from tests.integration.test_pipeline_analysis import VALID_ANALYSIS
from tests.integration.test_pipeline_extraction import VALID_EXTRACTION, _upload_fixture


async def _completed_contract(client: httpx.AsyncClient, fake_llm: Any) -> str:
    fake_llm([json.dumps(VALID_EXTRACTION), json.dumps(VALID_ANALYSIS)])
    return await _upload_fixture(client)


async def _patch(
    client: httpx.AsyncClient, contract_id: str, fields: dict[str, str | None]
) -> httpx.Response:
    return await client.patch(f"/api/v1/contracts/{contract_id}/fields", json={"fields": fields})


async def test_valid_correction_is_normalized_and_preserves_llm_value(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    contract_id = await _completed_contract(client, fake_llm)

    # Correção enviada crua (sem formatação): deve ser normalizada.
    response = await _patch(client, contract_id, {"provider.cnpj": "45723174000110"})

    assert response.status_code == 200
    field_state = response.json()["extraction"]["fields"]["provider.cnpj"]
    assert field_state["corrected_value"] == "45.723.174/0001-10"
    assert field_state["effective_value"] == "45.723.174/0001-10"
    assert field_state["llm_value"] == "11.222.333/0001-81"  # original intocado

    field = (
        await db_session.execute(
            select(ExtractedField).where(ExtractedField.field_name == "provider.cnpj")
        )
    ).scalar_one()
    assert field.corrected_at is not None


async def test_correction_accepts_iso_date_from_ui(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    contract_id = await _completed_contract(client, fake_llm)

    response = await _patch(client, contract_id, {"issue_date": "2025-12-01"})

    assert response.status_code == 200
    assert response.json()["extraction"]["fields"]["issue_date"]["effective_value"] == "2025-12-01"


async def test_invalid_correction_returns_422_and_applies_nothing(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    contract_id = await _completed_contract(client, fake_llm)

    # Um campo válido + um inválido na mesma request: atômico, nada aplica.
    response = await _patch(
        client,
        contract_id,
        {"provider.uf": "SC", "provider.cnpj": "11.111.111/1111-11"},
    )

    assert response.status_code == 422
    errors = response.json()["detail"]["fields"]
    assert "provider.cnpj" in errors

    detail = (await client.get(f"/api/v1/contracts/{contract_id}")).json()
    assert detail["extraction"]["fields"]["provider.uf"]["corrected_value"] is None


async def test_unknown_field_returns_422(client: httpx.AsyncClient, fake_llm: Any) -> None:
    contract_id = await _completed_contract(client, fake_llm)

    response = await _patch(client, contract_id, {"provider.telefone": "41 99999-0000"})

    assert response.status_code == 422
    assert response.json()["detail"]["fields"]["provider.telefone"] == "campo desconhecido"


async def test_null_removes_correction_restoring_llm_value(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    contract_id = await _completed_contract(client, fake_llm)
    await _patch(client, contract_id, {"provider.cidade": "Joinville"})

    response = await _patch(client, contract_id, {"provider.cidade": None})

    field_state = response.json()["extraction"]["fields"]["provider.cidade"]
    assert field_state["corrected_value"] is None
    assert field_state["effective_value"] == "Curitiba"  # valor do LLM de volta


async def test_contract_type_correction_must_be_in_enum(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    contract_id = await _completed_contract(client, fake_llm)

    invalid = await _patch(client, contract_id, {"contract_type": "Consultoria"})
    assert invalid.status_code == 422

    valid = await _patch(client, contract_id, {"contract_type": "Cloud"})
    assert valid.status_code == 200
    assert valid.json()["extraction"]["fields"]["contract_type"]["effective_value"] == "Cloud"


async def test_empty_string_on_free_text_field_returns_422(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    contract_id = await _completed_contract(client, fake_llm)

    response = await _patch(client, contract_id, {"provider.razao_social": "   "})

    assert response.status_code == 422


async def test_patch_while_processing_returns_409(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    contract = Contract(
        original_filename="c.pdf", mime_type="application/pdf", stored_path="/tmp/c.pdf"
    )
    db_session.add(contract)
    await db_session.commit()

    response = await _patch(client, contract.id, {"provider.uf": "SC"})

    assert response.status_code == 409


async def test_patch_unknown_contract_returns_404(client: httpx.AsyncClient) -> None:
    response = await _patch(client, "00000000-0000-0000-0000-000000000000", {"provider.uf": "SC"})
    assert response.status_code == 404
