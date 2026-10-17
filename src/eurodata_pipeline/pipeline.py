"""Download, validate, and idempotently upsert ECB exchange-rate data."""
import logging
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ExchangeRate

logger = logging.getLogger(__name__)
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD+GBP+JPY+CHF.EUR.SP00.A"
REQUIRED_COLUMNS = {"CURRENCY", "CURRENCY_DENOM", "TIME_PERIOD", "OBS_VALUE"}


class DataSourceError(RuntimeError):
    """Raised when the upstream ECB response cannot be used."""


def fetch_ecb_data(start_date: str = "2020-01-01", end_date: str | None = None,
                   timeout: int = 30) -> pd.DataFrame:
    """Fetch daily EUR exchange rates for USD, GBP, JPY and CHF from the ECB API."""
    params: dict[str, str] = {"startPeriod": start_date, "format": "csvdata"}
    if end_date:
        params["endPeriod"] = end_date
    try:
        response = requests.get(ECB_URL, params=params, timeout=timeout,
                               headers={"User-Agent": "eurodata-pipeline/1.0 (educational project)"})
        response.raise_for_status()
        from io import StringIO
        frame = pd.read_csv(StringIO(response.text))
    except (requests.RequestException, pd.errors.ParserError, ValueError) as exc:
        raise DataSourceError(f"Could not retrieve/parse ECB data: {exc}") from exc
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise DataSourceError(f"ECB response is missing expected columns: {sorted(missing)}")
    if frame.empty:
        logger.warning("ECB returned no observations for the requested period")
        return pd.DataFrame(columns=["currency", "base_currency", "observation_date", "rate"])
    frame = frame.rename(columns={"CURRENCY": "currency", "CURRENCY_DENOM": "base_currency",
                                  "TIME_PERIOD": "observation_date", "OBS_VALUE": "rate"})
    frame = frame[["currency", "base_currency", "observation_date", "rate"]].copy()
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce").dt.date
    frame["rate"] = pd.to_numeric(frame["rate"], errors="coerce")
    frame = frame.dropna(subset=["currency", "base_currency", "observation_date", "rate"])
    frame["currency"] = frame["currency"].astype(str).str.upper()
    frame["base_currency"] = frame["base_currency"].astype(str).str.upper()
    frame = frame[(frame["base_currency"] == "EUR") & (frame["rate"] > 0)]
    frame = frame.drop_duplicates(subset=["currency", "observation_date"], keep="last")
    if not frame.empty and not frame["currency"].isin(["USD", "GBP", "JPY", "CHF"]).all():
        raise DataSourceError("ECB returned an unexpected currency in the response")
    return frame.sort_values(["currency", "observation_date"]).reset_index(drop=True)


def upsert_observations(db: Session, frame: pd.DataFrame) -> dict[str, int]:
    """Insert new observations and update revised observations; safe to rerun."""
    inserted = updated = skipped = 0
    for row in frame.to_dict(orient="records"):
        currency = str(row["currency"]).upper()
        obs_date = row["observation_date"]
        rate = float(row["rate"])
        if not currency or rate <= 0:
            skipped += 1
            continue
        existing = db.scalar(select(ExchangeRate).where(
            ExchangeRate.currency == currency,
            ExchangeRate.observation_date == obs_date,
        ))
        if existing is None:
            db.add(ExchangeRate(currency=currency, base_currency=str(row["base_currency"]),
                               observation_date=obs_date, rate=rate, source="ECB"))
            inserted += 1
        elif existing.rate != rate or existing.base_currency != str(row["base_currency"]):
            existing.rate = rate
            existing.base_currency = str(row["base_currency"])
            existing.ingested_at = datetime.now(UTC)
            updated += 1
        else:
            skipped += 1
    db.commit()
    return {"received": len(frame), "inserted": inserted, "updated": updated, "unchanged_or_skipped": skipped}


def run_pipeline(db: Session, start_date: str = "2020-01-01", end_date: str | None = None,
                 timeout: int = 30) -> dict[str, Any]:
    """Run a single end-to-end extraction and load."""
    frame = fetch_ecb_data(start_date=start_date, end_date=end_date, timeout=timeout)
    counts = upsert_observations(db, frame)
    counts["currencies"] = sorted(frame["currency"].unique().tolist()) if not frame.empty else []
    counts["date_min"] = str(frame["observation_date"].min()) if not frame.empty else None
    counts["date_max"] = str(frame["observation_date"].max()) if not frame.empty else None
    logger.info("ECB pipeline finished: %s", counts)
    return counts
