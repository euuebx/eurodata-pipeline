from datetime import date

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from eurodata_pipeline.db import Base
from eurodata_pipeline.models import ExchangeRate
from eurodata_pipeline.pipeline import upsert_observations


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_upsert_inserts_and_is_idempotent():
    with make_session() as db:
        frame = pd.DataFrame([
            {"currency": "USD", "base_currency": "EUR", "observation_date": date(2024, 1, 2), "rate": 1.09},
            {"currency": "GBP", "base_currency": "EUR", "observation_date": date(2024, 1, 2), "rate": 0.86},
        ])
        first = upsert_observations(db, frame)
        second = upsert_observations(db, frame)
        assert first["inserted"] == 2
        assert second["inserted"] == 0
        assert second["unchanged_or_skipped"] == 2
        assert db.scalar(select(ExchangeRate).where(ExchangeRate.currency == "USD")).rate == 1.09


def test_upsert_updates_revised_observation():
    with make_session() as db:
        day = date(2024, 1, 2)
        upsert_observations(db, pd.DataFrame([{"currency": "USD", "base_currency": "EUR", "observation_date": day, "rate": 1.09}]))
        result = upsert_observations(db, pd.DataFrame([{"currency": "USD", "base_currency": "EUR", "observation_date": day, "rate": 1.10}]))
        assert result["updated"] == 1
        assert db.scalar(select(ExchangeRate).where(ExchangeRate.currency == "USD")).rate == 1.10
