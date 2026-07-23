"""
pytest 共享 fixtures
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.ai_provider import AiProvider
import app.models  # noqa: F401  — register all models with Base.metadata

@pytest.fixture(scope="session")
def test_engine(tmp_path_factory):
    database_path = tmp_path_factory.mktemp("database") / "test.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(test_engine):
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def disable_external_ai_providers(db_session):
    """Keep unit tests deterministic when earlier tests create Provider records."""
    db_session.execute(update(AiProvider).values(status="inactive"))
    db_session.commit()
    yield
    db_session.execute(update(AiProvider).values(status="inactive"))
    db_session.commit()


@pytest.fixture(autouse=True)
def enable_test_registration():
    original_value = settings.TESTING
    settings.TESTING = True
    yield
    settings.TESTING = original_value

@pytest.fixture
def client(db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
