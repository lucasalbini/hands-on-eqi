import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, ContractStatus, ExtractedField, Extraction, PipelineStage

FIXTURES = Path(__file__).parent.parent / "fixtures"
PDF_MIME = "application/pdf"

VALID_EXTRACTION = {
    "contract_type": "Desenvolvimento de Software",
    "contract_object": "Desenvolvimento de sistema web sob demanda.",
    "issue_date": "11/11/2025",
    "provider": {
        "razao_social": "ACME SOFTWARE LTDA",
        "cnpj": "11.222.333/0001-81",
        "endereco": "Rua das Flores, 100",
        "cidade": "Curitiba",
        "uf": "PR",
        "representante_nome": "Maria Silva",
        "representante_cargo": "Diretora",
    },
    "customer": {
        "razao_social": None,
        "cnpj": None,
        "endereco": None,
        "cidade": None,
        "uf": None,
        "representante_nome": None,
        "representante_cargo": None,
    },
}


class FakeLLM:
    """Substitui o AsyncOpenAI atrás de structured_completion, sem rede."""

    def __init__(self, contents: list[str | None]) -> None:
        self.calls: list[dict[str, Any]] = []
        self._contents = contents
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        content = self._contents[min(len(self.calls) - 1, len(self._contents) - 1)]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(contents: list[str | None]) -> FakeLLM:
        fake = FakeLLM(contents)
        monkeypatch.setattr("app.llm.client.get_client", lambda: fake)
        return fake

    return install


async def _upload_fixture(client: httpx.AsyncClient, filename: str = "contrato_minimo.pdf") -> str:
    data = (FIXTURES / filename).read_bytes()
    response = await client.post("/api/v1/contracts", files={"file": (filename, data, PDF_MIME)})
    assert response.status_code == 202
    contract_id: str = response.json()["id"]
    return contract_id


async def test_pipeline_persists_raw_text_and_extraction(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    llm = fake_llm([json.dumps(VALID_EXTRACTION)])
    contract_id = await _upload_fixture(client)

    contract = await db_session.get(Contract, contract_id)
    assert contract is not None
    assert contract.status is ContractStatus.PROCESSING  # análise (#10) ainda não roda
    assert contract.current_stage is PipelineStage.ANALYZE
    assert contract.raw_text is not None and "DO OBJETO" in contract.raw_text

    extraction = (await db_session.execute(select(Extraction))).scalar_one()
    assert extraction.prompt_version == "extraction_v1"
    assert extraction.raw_llm_output["contract_type"] == "Desenvolvimento de Software"
    assert len(llm.calls) == 1


async def test_extraction_call_uses_temperature_zero_and_contract_text(
    client: httpx.AsyncClient, fake_llm: Any
) -> None:
    llm = fake_llm([json.dumps(VALID_EXTRACTION)])
    await _upload_fixture(client)

    call = llm.calls[0]
    assert call["temperature"] == 0.0
    user_message = call["messages"][1]["content"]
    assert "<contract_text>" in user_message
    assert "DO OBJETO" in user_message  # texto real do PDF entrou no prompt


async def test_valid_fields_are_normalized(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    fake_llm([json.dumps(VALID_EXTRACTION)])
    await _upload_fixture(client)

    fields = {
        f.field_name: f for f in (await db_session.execute(select(ExtractedField))).scalars().all()
    }
    assert fields["issue_date"].normalized_value == "2025-11-11"
    assert fields["provider.cnpj"].normalized_value == "11.222.333/0001-81"
    assert fields["provider.uf"].is_valid is True
    assert len(fields) == 17  # 3 gerais + 7 provider + 7 customer


async def test_invalid_cnpj_is_flagged_never_discarded(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    payload = json.loads(json.dumps(VALID_EXTRACTION))
    payload["provider"]["cnpj"] = "11.222.333/0001-80"  # DV errado
    fake_llm([json.dumps(payload)])
    await _upload_fixture(client)

    field = (
        await db_session.execute(
            select(ExtractedField).where(ExtractedField.field_name == "provider.cnpj")
        )
    ).scalar_one()
    assert field.is_valid is False
    assert field.llm_value == "11.222.333/0001-80"
    assert field.normalized_value is None
    assert field.validation_error is not None and "verificador" in field.validation_error


async def test_absent_fields_are_null_and_valid(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    fake_llm([json.dumps(VALID_EXTRACTION)])
    await _upload_fixture(client)

    field = (
        await db_session.execute(
            select(ExtractedField).where(ExtractedField.field_name == "customer.cnpj")
        )
    ).scalar_one()
    assert field.llm_value is None
    assert field.is_valid is True
    assert field.validation_error is None


async def test_malformed_llm_output_retries_then_fails_at_extract_stage(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    llm = fake_llm(["not json", "still not json"])
    contract_id = await _upload_fixture(client)

    contract = await db_session.get(Contract, contract_id)
    assert contract is not None
    assert contract.status is ContractStatus.FAILED
    assert contract.current_stage is PipelineStage.EXTRACT
    assert contract.error_message is not None
    assert len(llm.calls) == 2  # retry único
    # A extração falhou por inteiro: nada persistido pela metade.
    assert (await db_session.execute(select(Extraction))).scalar_one_or_none() is None


async def test_scanned_pdf_fails_at_parse_stage_with_ocr_message(
    client: httpx.AsyncClient, db_session: AsyncSession, fake_llm: Any
) -> None:
    llm = fake_llm([json.dumps(VALID_EXTRACTION)])
    contract_id = await _upload_fixture(client, "escaneado.pdf")

    contract = await db_session.get(Contract, contract_id)
    assert contract is not None
    assert contract.status is ContractStatus.FAILED
    assert contract.current_stage is PipelineStage.PARSE
    assert contract.error_message is not None and "OCR" in contract.error_message
    assert llm.calls == []  # nunca chegou no LLM
