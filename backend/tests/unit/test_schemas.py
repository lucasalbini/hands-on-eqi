import pytest
from pydantic import ValidationError

from app.schemas import (
    AiAnalysis,
    AnalysisResult,
    ExtractionResult,
    Obligation,
    Risk,
)


class TestExtractionResult:
    def test_all_fields_absent_defaults_to_none(self) -> None:
        result = ExtractionResult()
        assert result.contract_type is None
        assert result.issue_date is None
        assert result.provider.cnpj is None
        assert result.customer.razao_social is None

    def test_contract_type_outside_enum_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExtractionResult.model_validate({"contract_type": "Consultoria"})

    def test_valid_payload_parses(self) -> None:
        result = ExtractionResult.model_validate(
            {
                "contract_type": "Cloud",
                "issue_date": "11/11/2025",
                "provider": {"razao_social": "ACME LTDA", "uf": "SP"},
                "customer": {"cnpj": "12.345.678/0001-90"},
            }
        )
        assert result.contract_type == "Cloud"
        assert result.provider.uf == "SP"


class TestAnalysisResult:
    def test_severity_outside_enum_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Risk(title="t", description="d", severity="critica")  # type: ignore[arg-type]

    def test_obligation_party_outside_enum_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Obligation(party="terceiro", description="d")  # type: ignore[arg-type]

    def test_valid_analysis_parses_with_empty_lists(self) -> None:
        result = AnalysisResult(
            summary="Resumo.",
            ai_analysis=AiAnalysis(overall_assessment="Contrato equilibrado."),
        )
        assert result.ai_analysis.risks == []
        assert result.ai_analysis.attention_points == []

    def test_missing_overall_assessment_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalysisResult.model_validate({"summary": "s", "ai_analysis": {"risks": []}})
