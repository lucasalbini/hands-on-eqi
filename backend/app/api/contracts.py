from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import anyio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import get_session
from app.models import Analysis, Contract, ContractStatus, Extraction
from app.pipeline.extraction import FIELD_VALIDATORS
from app.pipeline.runner import run_pipeline
from app.schemas import (
    AnalysisDetail,
    ContractCreated,
    ContractDetail,
    ContractListItem,
    ContractStatusResponse,
    ExtractionDetail,
    FieldState,
    PatchFieldsRequest,
)

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ContractCreated)
async def upload_contract(
    file: UploadFile, background_tasks: BackgroundTasks, session: SessionDep
) -> ContractCreated:
    extension = ALLOWED_MIME_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo não suportado: {file.content_type}. Envie PDF ou DOCX.",
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Arquivo acima do limite de 20 MB.",
        )

    contract = Contract(
        original_filename=file.filename or f"contrato{extension}",
        mime_type=file.content_type or "",
        stored_path="",
    )
    session.add(contract)
    await session.flush()  # materializa o id gerado por default

    # Arquivo armazenado com nome UUID, nunca com o nome original (segurança).
    stored_path = Path(settings.upload_dir) / f"{contract.id}{extension}"
    contract.stored_path = str(stored_path)
    await anyio.Path(stored_path).write_bytes(data)

    await session.commit()

    background_tasks.add_task(run_pipeline, contract.id)
    return ContractCreated(id=contract.id, status=contract.status)


def _latest_extraction(contract: Contract) -> Extraction | None:
    return max(contract.extractions, key=lambda e: e.id, default=None)


def _effective_contract_type(contract: Contract) -> str | None:
    extraction = _latest_extraction(contract)
    if extraction is None:
        return None
    field = next((f for f in extraction.fields if f.field_name == "contract_type"), None)
    return field.effective_value if field else None


@router.get("", response_model=list[ContractListItem])
async def list_contracts(session: SessionDep) -> list[ContractListItem]:
    contracts = (
        (
            await session.execute(
                select(Contract)
                .options(selectinload(Contract.extractions).selectinload(Extraction.fields))
                .order_by(Contract.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        ContractListItem(
            id=c.id,
            original_filename=c.original_filename,
            status=c.status,
            current_stage=c.current_stage,
            contract_type=_effective_contract_type(c),
            created_at=c.created_at,
        )
        for c in contracts
    ]


@router.get("/{contract_id}", response_model=ContractDetail)
async def get_contract(contract_id: str, session: SessionDep) -> ContractDetail:
    contract = (
        await session.execute(
            select(Contract)
            .where(Contract.id == contract_id)
            .options(
                selectinload(Contract.extractions).selectinload(Extraction.fields),
                selectinload(Contract.analyses),
            )
        )
    ).scalar_one_or_none()
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contrato não encontrado.")

    extraction = _latest_extraction(contract)
    analysis = max(contract.analyses, key=lambda a: a.id, default=None)
    return ContractDetail(
        id=contract.id,
        original_filename=contract.original_filename,
        status=contract.status,
        current_stage=contract.current_stage,
        error_message=contract.error_message,
        created_at=contract.created_at,
        extraction=_extraction_detail(extraction) if extraction else None,
        analysis=_analysis_detail(analysis) if analysis else None,
    )


def _extraction_detail(extraction: Extraction) -> ExtractionDetail:
    return ExtractionDetail(
        prompt_version=extraction.prompt_version,
        model=extraction.model,
        fields={f.field_name: FieldState.model_validate(f) for f in extraction.fields},
    )


def _analysis_detail(analysis: Analysis) -> AnalysisDetail:
    return AnalysisDetail(
        prompt_version=analysis.prompt_version,
        model=analysis.model,
        summary=analysis.summary,
        ai_analysis=analysis.ai_analysis,
    )


@router.patch("/{contract_id}/fields", response_model=ContractDetail)
async def patch_fields(
    contract_id: str, payload: PatchFieldsRequest, session: SessionDep
) -> ContractDetail:
    contract = (
        await session.execute(
            select(Contract)
            .where(Contract.id == contract_id)
            .options(selectinload(Contract.extractions).selectinload(Extraction.fields))
        )
    ).scalar_one_or_none()
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contrato não encontrado.")
    if contract.status is ContractStatus.PROCESSING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Contrato ainda em processamento; aguarde para corrigir.",
        )
    extraction = _latest_extraction(contract)
    if extraction is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Contrato sem extração para corrigir.")

    fields_by_name = {f.field_name: f for f in extraction.fields}

    # Validação atômica: qualquer campo inválido → 422 e nada é aplicado.
    errors: dict[str, str] = {}
    corrections: dict[str, str | None] = {}
    for field_name, value in payload.fields.items():
        field = fields_by_name.get(field_name)
        if field is None:
            errors[field_name] = "campo desconhecido"
            continue
        if value is None:
            corrections[field_name] = None  # remove a correção (volta ao valor do LLM)
            continue
        validator = FIELD_VALIDATORS.get(field_name)
        if validator is None:
            if not value.strip():
                errors[field_name] = "valor não pode ser vazio; use null para limpar a correção"
            else:
                corrections[field_name] = value.strip()
            continue
        outcome = validator(value)
        if not outcome.is_valid:
            errors[field_name] = outcome.error or "valor inválido"
        else:
            corrections[field_name] = outcome.normalized

    if errors:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"fields": errors})

    now = datetime.now(UTC)
    for field_name, corrected in corrections.items():
        field = fields_by_name[field_name]
        # llm_value original nunca é tocado — auditoria/comparação na UI.
        field.corrected_value = corrected
        field.corrected_at = now if corrected is not None else None
    await session.commit()

    return await get_contract(contract_id, session)


@router.get("/{contract_id}/status", response_model=ContractStatusResponse)
async def get_contract_status(contract_id: str, session: SessionDep) -> ContractStatusResponse:
    contract = await session.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contrato não encontrado.")
    return ContractStatusResponse(
        id=contract.id,
        status=contract.status,
        current_stage=contract.current_stage,
        error_message=contract.error_message,
    )
