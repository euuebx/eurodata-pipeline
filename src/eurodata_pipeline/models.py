"""Relational schema for ingested ECB observations."""
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("currency", "observation_date", name="uq_currency_observation_date"),
        Index("ix_exchange_rates_date", "observation_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    observation_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="ECB")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
