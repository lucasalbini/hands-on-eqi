"""Orquestração do pipeline parse → extract → analyze.

Roda em BackgroundTask com sessão própria (não a da request). Falha em
qualquer estágio grava status=failed + current_stage + error_message —
o erro fica visível para a UI em vez de sumir num log.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app import db
from app.config import settings
from app.models import Analysis, Contract, ContractStatus, ExtractedField, Extraction, PipelineStage
from app.observability import (
    field_validation_failures_total,
    get_logger,
    pipeline_runs_total,
    pipeline_stage_duration_seconds,
    pipeline_stage_failures_total,
)
from app.pipeline.analysis import run_analysis
from app.pipeline.extraction import build_extracted_fields, flatten_extraction, run_extraction
from app.pipeline.parsing import parse_document

logger = get_logger(__name__)


@asynccontextmanager
async def _timed_stage(stage: PipelineStage) -> AsyncIterator[None]:
    """Mede a duração do estágio e loga início/fim; falha incrementa a métrica."""
    logger.info("stage_started", stage=stage.value)
    start = time.perf_counter()
    try:
        yield
    except Exception:
        pipeline_stage_failures_total.labels(stage=stage.value).inc()
        raise
    finally:
        pipeline_stage_duration_seconds.labels(stage=stage.value).observe(
            time.perf_counter() - start
        )
    logger.info("stage_finished", stage=stage.value)


async def run_pipeline(contract_id: str) -> None:
    structlog.contextvars.bind_contextvars(contract_id=contract_id)
    try:
        async with db.session_factory() as session:
            contract = await session.get(Contract, contract_id)
            if contract is None:
                logger.error("pipeline_aborted", reason="contract_not_found")
                return

            try:
                await _stage_parse(session, contract)
                extraction = await _stage_extract(session, contract)
                await _stage_analyze(session, contract, extraction)
            except Exception as exc:
                await _fail(session, contract, exc)
                return

            pipeline_runs_total.labels(status="completed").inc()
            logger.info("pipeline_completed")
    finally:
        structlog.contextvars.unbind_contextvars("contract_id")


async def _stage_parse(session: AsyncSession, contract: Contract) -> None:
    async with _timed_stage(PipelineStage.PARSE):
        contract.current_stage = PipelineStage.PARSE
        await session.commit()

        text = parse_document(Path(contract.stored_path), contract.mime_type)
        contract.raw_text = text
        await session.commit()


async def _stage_extract(session: AsyncSession, contract: Contract) -> Extraction:
    async with _timed_stage(PipelineStage.EXTRACT):
        contract.current_stage = PipelineStage.EXTRACT
        await session.commit()

        assert contract.raw_text is not None  # garantido pelo estágio de parse
        result, prompt_version = await run_extraction(contract.raw_text)

        fields = build_extracted_fields(flatten_extraction(result))
        _record_validation_failures(fields)

        extraction = Extraction(
            contract_id=contract.id,
            prompt_version=prompt_version,
            model=settings.extraction_model,
            raw_llm_output=result.model_dump(mode="json"),
            fields=fields,
        )
        session.add(extraction)
        # Persistido antes da análise: falha posterior não perde a extração.
        contract.current_stage = PipelineStage.ANALYZE
        await session.commit()
        return extraction


async def _stage_analyze(session: AsyncSession, contract: Contract, extraction: Extraction) -> None:
    async with _timed_stage(PipelineStage.ANALYZE):
        assert contract.raw_text is not None
        # Só valores confiáveis entram no contexto da análise: corrigido/normalizado,
        # ou bruto válido. Campo inválido ou ausente fica de fora.
        metadata = {
            field.field_name: field.effective_value
            for field in extraction.fields
            if field.effective_value is not None
        }
        result, prompt_version = await run_analysis(contract.raw_text, metadata)

        session.add(
            Analysis(
                contract_id=contract.id,
                prompt_version=prompt_version,
                model=settings.analysis_model,
                summary=result.summary,
                ai_analysis=result.ai_analysis.model_dump(mode="json"),
            )
        )
        contract.status = ContractStatus.COMPLETED
        contract.current_stage = None
        await session.commit()


def _record_validation_failures(fields: list[ExtractedField]) -> None:
    for field in fields:
        if not field.is_valid:
            field_validation_failures_total.labels(field_name=field.field_name).inc()
            logger.warning(
                "field_validation_failed",
                field_name=field.field_name,
                error=field.validation_error,
            )


async def _fail(session: AsyncSession, contract: Contract, exc: Exception) -> None:
    await session.rollback()  # transação pode ter morrido junto com o estágio
    stage = contract.current_stage.value if contract.current_stage else "desconhecido"
    logger.error("pipeline_failed", stage=stage, error=str(exc))
    pipeline_runs_total.labels(status="failed").inc()
    contract.status = ContractStatus.FAILED
    contract.error_message = str(exc)
    await session.commit()
