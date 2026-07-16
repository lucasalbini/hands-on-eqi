import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import ContractStatus, PipelineStage

# --- Schemas do output do LLM (extração) ---


class ContractType(enum.StrEnum):
    DESENVOLVIMENTO_DE_SOFTWARE = "Desenvolvimento de Software"
    CLOUD = "Cloud"
    SUPORTE = "Suporte"
    CIBERSEGURANCA = "Cibersegurança"
    APP_MOBILE = "App Mobile"
    OUTRO = "Outro"


class Party(BaseModel):
    """Dados de uma parte do contrato, exatamente como escritos no documento."""

    razao_social: str | None = None
    cnpj: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    uf: str | None = None
    representante_nome: str | None = None
    representante_cargo: str | None = None


class ExtractionResult(BaseModel):
    """Candidato devolvido pela chamada LLM de extração literal."""

    contract_type: ContractType | None = None
    contract_object: str | None = None
    issue_date: str | None = None
    provider: Party = Field(default_factory=Party)
    customer: Party = Field(default_factory=Party)


# --- Schemas do output do LLM (análise) ---


class RiskSeverity(enum.StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class PartyRole(enum.StrEnum):
    PROVIDER = "provider"
    CUSTOMER = "customer"


class Risk(BaseModel):
    title: str
    description: str
    severity: RiskSeverity
    clause_ref: str | None = None


class Obligation(BaseModel):
    party: PartyRole
    description: str
    clause_ref: str | None = None


class AttentionPoint(BaseModel):
    description: str
    clause_ref: str | None = None


class AiAnalysis(BaseModel):
    overall_assessment: str
    risks: list[Risk] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    attention_points: list[AttentionPoint] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Candidato devolvido pela chamada LLM de resumo + análise."""

    summary: str
    ai_analysis: AiAnalysis


# --- Schemas da API ---


class ContractCreated(BaseModel):
    id: str
    status: ContractStatus


class ContractStatusResponse(BaseModel):
    id: str
    status: ContractStatus
    current_stage: PipelineStage | None
    error_message: str | None


class ContractListItem(BaseModel):
    id: str
    original_filename: str
    status: ContractStatus
    current_stage: PipelineStage | None
    contract_type: str | None
    created_at: datetime


class FieldState(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    llm_value: str | None
    normalized_value: str | None
    is_valid: bool
    validation_error: str | None
    corrected_value: str | None
    effective_value: str | None


class ExtractionDetail(BaseModel):
    prompt_version: str
    model: str
    fields: dict[str, FieldState]


class AnalysisDetail(BaseModel):
    prompt_version: str
    model: str
    summary: str
    ai_analysis: dict[str, Any]


class ContractDetail(BaseModel):
    id: str
    original_filename: str
    status: ContractStatus
    current_stage: PipelineStage | None
    error_message: str | None
    created_at: datetime
    extraction: ExtractionDetail | None
    analysis: AnalysisDetail | None


class PatchFieldsRequest(BaseModel):
    # Valor null remove a correção (volta ao valor do LLM).
    fields: dict[str, str | None]
