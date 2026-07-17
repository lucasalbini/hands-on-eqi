import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.contracts import router as contracts_router
from app.config import settings
from app.db import create_tables, engine
from app.observability import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    await create_tables(engine)
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Contract Analyzer", lifespan=lifespan)
    app.include_router(contracts_router)

    # /metrics com latência e contagem HTTP por rota/status.
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    @app.middleware("http")
    async def bind_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=str(uuid.uuid4()))
        response: Response = await call_next(request)
        return response

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
