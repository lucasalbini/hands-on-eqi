from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app import db
from app.config import settings
from app.db import Base, get_session
from app.main import create_app


class FakeLLM:
    """Substitui o AsyncOpenAI atrás de structured_completion, sem rede.

    Devolve os conteúdos na ordem; a última entrada repete se houver mais chamadas.
    """

    def __init__(self, contents: list[str | None]) -> None:
        self.calls: list[dict[str, Any]] = []
        self._contents = contents
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        content = self._contents[min(len(self.calls) - 1, len(self._contents) - 1)]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(contents: list[str | None]) -> FakeLLM:
        fake = FakeLLM(contents)
        monkeypatch.setattr("app.llm.client.get_client", lambda: fake)
        return fake

    return install


@pytest.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    # StaticPool: mesma conexão compartilhada — necessário para SQLite in-memory
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(
    test_engine: AsyncEngine,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "upload_dir", tmp_path_factory.mktemp("uploads"))

    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    # O pipeline (BackgroundTask) abre a própria sessão via db.session_factory.
    monkeypatch.setattr(db, "session_factory", factory)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
