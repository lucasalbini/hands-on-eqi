"""Orquestração do pipeline parse → extract → analyze.

Roda em BackgroundTask com sessão própria (não a da request). Falha em
qualquer estágio grava status=failed + current_stage + error_message —
o erro fica visível para a UI em vez de sumir num log.
"""

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app import db
from app.config import settings
from app.models import Contract, ContractStatus, Extraction, PipelineStage
from app.pipeline.extraction import build_extracted_fields, flatten_extraction, run_extraction
from app.pipeline.parsing import parse_document

logger = logging.getLogger(__name__)


async def run_pipeline(contract_id: str) -> None:
    async with db.session_factory() as session:
        contract = await session.get(Contract, contract_id)
        if contract is None:
            logger.error("Pipeline abortado: contrato %s não existe", contract_id)
            return

        try:
            await _stage_parse(session, contract)
            await _stage_extract(session, contract)
        except Exception as exc:
            await _fail(session, contract, exc)
            return

        # Estágio de análise entra na issue #10; contrato segue em processing.


async def _stage_parse(session: AsyncSession, contract: Contract) -> None:
    contract.current_stage = PipelineStage.PARSE
    await session.commit()

    text = parse_document(Path(contract.stored_path), contract.mime_type)
    contract.raw_text = text
    await session.commit()


async def _stage_extract(session: AsyncSession, contract: Contract) -> None:
    contract.current_stage = PipelineStage.EXTRACT
    await session.commit()

    assert contract.raw_text is not None  # garantido pelo estágio de parse
    result, prompt_version = await run_extraction(contract.raw_text)

    extraction = Extraction(
        contract_id=contract.id,
        prompt_version=prompt_version,
        model=settings.extraction_model,
        raw_llm_output=result.model_dump(mode="json"),
        fields=build_extracted_fields(flatten_extraction(result)),
    )
    session.add(extraction)
    # Persistido antes da análise: falha posterior não perde a extração.
    contract.current_stage = PipelineStage.ANALYZE
    await session.commit()


async def _fail(session: AsyncSession, contract: Contract, exc: Exception) -> None:
    await session.rollback()  # transação pode ter morrido junto com o estágio
    stage = contract.current_stage.value if contract.current_stage else "desconhecido"
    logger.exception("Pipeline falhou no estágio %s (contrato %s)", stage, contract.id)
    contract.status = ContractStatus.FAILED
    contract.error_message = str(exc)
    await session.commit()
