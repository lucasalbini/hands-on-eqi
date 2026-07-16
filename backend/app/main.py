from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.contracts import router as contracts_router
from app.config import settings
from app.db import create_tables, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    await create_tables(engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Contract Analyzer", lifespan=lifespan)
    app.include_router(contracts_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
