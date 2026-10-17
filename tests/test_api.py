from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from eurodata_pipeline.api import app
from eurodata_pipeline.db import Base, get_db
from eurodata_pipeline.models import ExchangeRate


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    with TestingSession() as db:
        db.add_all([
            ExchangeRate(currency="USD", base_currency="EUR", observation_date=date(2024, 1, 2), rate=1.09, source="ECB"),
            ExchangeRate(currency="GBP", base_currency="EUR", observation_date=date(2024, 1, 2), rate=0.86, source="ECB"),
        ])
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_filter_rates_by_currency(client):
    response = client.get("/v1/rates", params={"currency": "usd"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["currency"] == "USD"


def test_latest_rates_returns_each_currency(client):
    response = client.get("/v1/rates/latest")
    assert response.status_code == 200
    assert {row["currency"] for row in response.json()} == {"USD", "GBP"}


def test_invalid_date_range_is_rejected(client):
    response = client.get("/v1/rates", params={"start_date": "2024-02-01", "end_date": "2024-01-01"})
    assert response.status_code == 422
