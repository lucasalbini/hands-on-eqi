import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ContractStatus(enum.StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStage(enum.StrEnum):
    PARSE = "parse"
    EXTRACT = "extract"
    ANALYZE = "analyze"


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    stored_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[ContractStatus] = mapped_column(
        Enum(ContractStatus, values_callable=lambda e: [m.value for m in e]),
        default=ContractStatus.PROCESSING,
    )
    current_stage: Mapped[PipelineStage | None] = mapped_column(
        Enum(PipelineStage, values_callable=lambda e: [m.value for m in e]), default=None
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    raw_text: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    extractions: Mapped[list["Extraction"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"))
    prompt_version: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    raw_llm_output: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contract: Mapped[Contract] = relationship(back_populates="extractions")
    fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="extraction", cascade="all, delete-orphan"
    )


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    extraction_id: Mapped[int] = mapped_column(ForeignKey("extractions.id"))
    # Path plano do campo: "contract_type", "issue_date", "provider.cnpj", ...
    field_name: Mapped[str] = mapped_column(String(100))
    llm_value: Mapped[str | None] = mapped_column(Text, default=None)
    normalized_value: Mapped[str | None] = mapped_column(Text, default=None)
    is_valid: Mapped[bool] = mapped_column(default=True)
    validation_error: Mapped[str | None] = mapped_column(Text, default=None)
    corrected_value: Mapped[str | None] = mapped_column(Text, default=None)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    extraction: Mapped[Extraction] = relationship(back_populates="fields")

    @property
    def effective_value(self) -> str | None:
        """Correção humana > valor normalizado > valor bruto do LLM (se válido)."""
        if self.corrected_value is not None:
            return self.corrected_value
        if self.normalized_value is not None:
            return self.normalized_value
        return self.llm_value if self.is_valid else None


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("contracts.id"))
    prompt_version: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    ai_analysis: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contract: Mapped[Contract] = relationship(back_populates="analyses")
