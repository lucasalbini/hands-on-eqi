from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Analysis, Contract, ContractStatus, ExtractedField, Extraction, PipelineStage


def _make_contract() -> Contract:
    return Contract(
        original_filename="contrato.pdf",
        mime_type="application/pdf",
        stored_path="/data/uploads/abc.pdf",
    )


async def test_contract_defaults_to_processing_with_generated_uuid(
    db_session: AsyncSession,
) -> None:
    contract = _make_contract()
    db_session.add(contract)
    await db_session.commit()

    saved = (await db_session.execute(select(Contract))).scalar_one()
    assert saved.status is ContractStatus.PROCESSING
    assert saved.current_stage is None
    assert len(saved.id) == 36


async def test_extraction_round_trip_preserves_fields_and_raw_output(
    db_session: AsyncSession,
) -> None:
    contract = _make_contract()
    extraction = Extraction(
        contract=contract,
        prompt_version="extraction_v1",
        model="extraction-model",
        raw_llm_output={"provider": {"cnpj": "12.345.678/0001-90"}},
        fields=[
            ExtractedField(
                field_name="provider.cnpj",
                llm_value="12.345.678/0001-90",
                normalized_value="12.345.678/0001-90",
                is_valid=True,
            )
        ],
    )
    db_session.add(extraction)
    await db_session.commit()
    db_session.expunge_all()

    saved = (await db_session.execute(select(Extraction))).scalar_one()
    assert saved.raw_llm_output == {"provider": {"cnpj": "12.345.678/0001-90"}}
    field = (await db_session.execute(select(ExtractedField))).scalar_one()
    assert field.field_name == "provider.cnpj"
    assert field.is_valid is True


async def test_analysis_round_trip_preserves_json(db_session: AsyncSession) -> None:
    analysis = Analysis(
        contract=_make_contract(),
        prompt_version="analysis_v1",
        model="analysis-model",
        summary="Resumo executivo.",
        ai_analysis={"overall_assessment": "ok", "risks": []},
    )
    db_session.add(analysis)
    await db_session.commit()
    db_session.expunge_all()

    saved = (await db_session.execute(select(Analysis))).scalar_one()
    assert saved.ai_analysis["overall_assessment"] == "ok"


async def test_contract_stage_and_status_transitions_persist(db_session: AsyncSession) -> None:
    contract = _make_contract()
    db_session.add(contract)
    await db_session.commit()

    contract.status = ContractStatus.FAILED
    contract.current_stage = PipelineStage.EXTRACT
    contract.error_message = "boom"
    await db_session.commit()
    db_session.expunge_all()

    saved = (await db_session.execute(select(Contract))).scalar_one()
    assert saved.status is ContractStatus.FAILED
    assert saved.current_stage is PipelineStage.EXTRACT
    assert saved.error_message == "boom"


class TestEffectiveValue:
    def test_correction_wins_over_everything(self) -> None:
        field = ExtractedField(
            field_name="issue_date",
            llm_value="11/11/2025",
            normalized_value="2025-11-11",
            is_valid=True,
            corrected_value="2025-12-01",
        )
        assert field.effective_value == "2025-12-01"

    def test_normalized_wins_over_llm_value(self) -> None:
        field = ExtractedField(
            field_name="issue_date",
            llm_value="11/11/2025",
            normalized_value="2025-11-11",
            is_valid=True,
        )
        assert field.effective_value == "2025-11-11"

    def test_invalid_field_without_normalization_has_no_effective_value(self) -> None:
        field = ExtractedField(
            field_name="provider.cnpj",
            llm_value="00.000.000/0000-00",
            normalized_value=None,
            is_valid=False,
            validation_error="dígito verificador inválido",
        )
        assert field.effective_value is None

    def test_valid_field_without_normalizer_falls_back_to_llm_value(self) -> None:
        field = ExtractedField(
            field_name="provider.razao_social",
            llm_value="ACME LTDA",
            normalized_value=None,
            is_valid=True,
        )
        assert field.effective_value == "ACME LTDA"
