import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import JSON

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models import Base


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "synthetic"


@pytest.fixture()
def db_engine(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(Base.metadata, "before_create")
    def _sqlite_jsonb_compat(metadata, connection, **kw):  # noqa: ARG001
        if connection.dialect.name == "sqlite":
            for table in metadata.tables.values():
                for column in table.columns:
                    if isinstance(column.type, JSONB):
                        column.type = JSON()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def storage_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raw_path = tmp_path / "raw"
    processed_path = tmp_path / "processed"
    raw_path.mkdir()
    processed_path.mkdir()
    monkeypatch.setattr(settings, "evidence_storage_path", raw_path)
    monkeypatch.setattr(settings, "processed_storage_path", processed_path)
    return raw_path, processed_path


@pytest.fixture()
def client(db_session: Session, storage_paths) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
