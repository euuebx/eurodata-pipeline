"""FastAPI service exposing stored ECB observations."""
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import create_tables, get_db
from .models import ExchangeRate


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield

app = FastAPI(title="EuroData API", version="1.0.0",
              description="A small data platform for genuine ECB daily exchange-rate observations.",
              lifespan=lifespan)


class RateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    currency: str
    base_currency: str
    observation_date: date
    rate: float
    source: str


class HealthOut(BaseModel):
    status: str
    database: str


@app.get("/health", response_model=HealthOut, tags=["operations"])
def health(db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(select(func.count()).select_from(ExchangeRate)).scalar_one()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return HealthOut(status="ok", database="connected")


@app.get("/v1/rates", response_model=list[RateOut], tags=["exchange rates"])
def list_rates(
    currency: str | None = Query(default=None, min_length=3, max_length=3, description="e.g. USD"),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ExchangeRate]:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    stmt = select(ExchangeRate)
    if currency:
        stmt = stmt.where(ExchangeRate.currency == currency.upper())
    if start_date:
        stmt = stmt.where(ExchangeRate.observation_date >= start_date)
    if end_date:
        stmt = stmt.where(ExchangeRate.observation_date <= end_date)
    stmt = stmt.order_by(ExchangeRate.observation_date.desc(), ExchangeRate.currency).offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


@app.get("/v1/rates/latest", response_model=list[RateOut], tags=["exchange rates"])
def latest_rates(db: Session = Depends(get_db)) -> list[ExchangeRate]:
    latest_dates = select(ExchangeRate.currency, func.max(ExchangeRate.observation_date).label("latest_date")).group_by(ExchangeRate.currency).subquery()
    stmt = select(ExchangeRate).join(latest_dates, (ExchangeRate.currency == latest_dates.c.currency) &
                                     (ExchangeRate.observation_date == latest_dates.c.latest_date)).order_by(ExchangeRate.currency)
    return list(db.scalars(stmt).all())


@app.get("/v1/summary", tags=["analytics"])
def summary(db: Session = Depends(get_db)) -> dict:
    total = db.scalar(select(func.count()).select_from(ExchangeRate)) or 0
    currencies = list(db.scalars(select(ExchangeRate.currency).distinct().order_by(ExchangeRate.currency)).all())
    first = db.scalar(select(func.min(ExchangeRate.observation_date)))
    last = db.scalar(select(func.max(ExchangeRate.observation_date)))
    return {"observation_count": total, "currencies": currencies,
            "first_observation_date": first, "last_observation_date": last}
