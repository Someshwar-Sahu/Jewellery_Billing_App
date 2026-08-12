import pytest
import os
from datetime import date
from sqlmodel import SQLModel, Session, create_engine
from starlette.testclient import TestClient
from app.main import app
from app.database import get_session
from app.models.shop import ShopSettings, FinancialYear, User
from app.models.products import Product, ProductGroup
from app.models.parties import Party

TEST_DB_URL = "sqlite:///./test_suite.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    SQLModel.metadata.drop_all(test_engine)
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)
    if os.path.exists("./test_suite.db"):
        try:
            os.remove("./test_suite.db")
        except Exception:
            pass

@pytest.fixture
def session():
    with Session(test_engine) as session:
        yield session

@pytest.fixture
def client(session):
    def get_test_session():
        yield session

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as test_client:
        # Mock authenticated session cookie
        with test_client.websocket_connect if hasattr(test_client, "websocket_connect") else session:
            pass
        yield test_client
    app.dependency_overrides.clear()
