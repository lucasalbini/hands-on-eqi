from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.contracts import MAX_UPLOAD_BYTES
from app.models import Contract, ContractStatus

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _upload(
    client: httpx.AsyncClient, filename: str, mime: str, data: bytes
) -> httpx.Response:
    return await client.post("/api/v1/contracts", files={"file": (filename, data, mime)})


async def test_upload_pdf_returns_202_with_processing_status(client: httpx.AsyncClient) -> None:
    response = await _upload(client, "contrato.pdf", PDF_MIME, b"%PDF-1.4 fake")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    assert len(body["id"]) == 36


async def test_upload_persists_contract_and_stores_file_with_uuid_name(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    response = await _upload(client, "contrato.pdf", PDF_MIME, b"%PDF-1.4 fake")
    contract_id = response.json()["id"]

    contract = (await db_session.execute(select(Contract))).scalar_one()
    assert contract.id == contract_id
    assert contract.original_filename == "contrato.pdf"
    assert contract.status is ContractStatus.PROCESSING

    stored = Path(contract.stored_path)
    assert stored.name == f"{contract_id}.pdf"
    assert stored.read_bytes() == b"%PDF-1.4 fake"


async def test_upload_docx_is_accepted(client: httpx.AsyncClient) -> None:
    response = await _upload(client, "contrato.docx", DOCX_MIME, b"PK fake docx")
    assert response.status_code == 202


async def test_upload_unsupported_type_returns_400(client: httpx.AsyncClient) -> None:
    response = await _upload(client, "contrato.txt", "text/plain", b"texto")
    assert response.status_code == 400
    assert "não suportado" in response.json()["detail"]


async def test_upload_above_size_limit_returns_413(client: httpx.AsyncClient) -> None:
    response = await _upload(client, "grande.pdf", PDF_MIME, b"x" * (MAX_UPLOAD_BYTES + 1))
    assert response.status_code == 413


async def test_status_of_existing_contract_returns_processing(client: httpx.AsyncClient) -> None:
    contract_id = (await _upload(client, "c.pdf", PDF_MIME, b"%PDF")).json()["id"]

    response = await client.get(f"/api/v1/contracts/{contract_id}/status")

    assert response.status_code == 200
    assert response.json() == {
        "id": contract_id,
        "status": "processing",
        "current_stage": None,
        "error_message": None,
    }


async def test_status_of_unknown_contract_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/contracts/00000000-0000-0000-0000-000000000000/status")
    assert response.status_code == 404


async def test_list_returns_contracts_newest_first(client: httpx.AsyncClient) -> None:
    first = (await _upload(client, "a.pdf", PDF_MIME, b"%PDF")).json()["id"]
    second = (await _upload(client, "b.pdf", PDF_MIME, b"%PDF")).json()["id"]

    response = await client.get("/api/v1/contracts")

    assert response.status_code == 200
    items = response.json()
    assert [i["id"] for i in items] == [second, first]
    assert items[0]["original_filename"] == "b.pdf"
    assert items[0]["contract_type"] is None


async def test_list_empty_returns_empty_array(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/contracts")
    assert response.status_code == 200
    assert response.json() == []
