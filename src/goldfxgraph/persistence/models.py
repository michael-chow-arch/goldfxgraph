from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from goldfxgraph.persistence.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ResearchRunModel(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    forecast: Mapped[ForecastModel | None] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )


class ForecastModel(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), default="XAUUSD", nullable=False)
    reference_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_source: Mapped[str] = mapped_column(String(255), nullable=False)
    current_price: Mapped[float] = mapped_column(nullable=False)
    daily_open: Mapped[float] = mapped_column(nullable=False)
    daily_high: Mapped[float] = mapped_column(nullable=False)
    daily_low: Mapped[float] = mapped_column(nullable=False)
    daily_close: Mapped[float] = mapped_column(nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    entry_price: Mapped[float | None] = mapped_column(nullable=True)
    take_profit_price: Mapped[float | None] = mapped_column(nullable=True)
    stop_loss_price: Mapped[float | None] = mapped_column(nullable=True)
    holding_period: Mapped[str] = mapped_column(String(255), nullable=False)
    intraday_action: Mapped[str] = mapped_column(Text, nullable=False)
    long_term_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    technical_summary: Mapped[str] = mapped_column(Text, nullable=False)
    macro_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    news_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_summary: Mapped[str] = mapped_column(Text, nullable=False)
    agent_votes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    risk_notes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)

    run: Mapped[ResearchRunModel] = relationship(back_populates="forecast")
