from pathlib import Path
from typing import Annotated

import anyio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Contract
from app.pipeline.runner import run_pipeline
from app.schemas import ContractCreated, ContractListItem, ContractStatusResponse

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


@router.get("", response_model=list[ContractListItem])
async def list_contracts(session: SessionDep) -> list[ContractListItem]:
    contracts = (
        (await session.execute(select(Contract).order_by(Contract.created_at.desc())))
        .scalars()
        .all()
    )
    return [
        ContractListItem(
            id=c.id,
            original_filename=c.original_filename,
            status=c.status,
            current_stage=c.current_stage,
            contract_type=None,  # preenchido quando a extração existir (issue #10)
            created_at=c.created_at,
        )
        for c in contracts
    ]


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
