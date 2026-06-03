from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from goldfxgraph.persistence.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class MarketDataBarModel(Base):
    __tablename__ = "market_data_bars"
    __table_args__ = (
        UniqueConstraint("symbol", "bar_date", name="uq_market_data_bars_symbol_bar_date"),
        CheckConstraint("open > 0", name="ck_market_data_bars_open_positive"),
        CheckConstraint("high > 0", name="ck_market_data_bars_high_positive"),
        CheckConstraint("low > 0", name="ck_market_data_bars_low_positive"),
        CheckConstraint("close > 0", name="ck_market_data_bars_close_positive"),
        CheckConstraint("volume IS NULL OR volume >= 0", name="ck_market_data_bars_volume_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), default="XAUUSD", nullable=False)
    bar_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class PromptTemplateModel(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("prompt_key", "version", name="uq_prompt_templates_prompt_key_version"),
        CheckConstraint("prompt_key <> ''", name="ck_prompt_templates_prompt_key_not_empty"),
        CheckConstraint("version <> ''", name="ck_prompt_templates_version_not_empty"),
        CheckConstraint("prompt_text_en <> ''", name="ck_prompt_templates_prompt_text_en_not_empty"),
        CheckConstraint("prompt_text_zh <> ''", name="ck_prompt_templates_prompt_text_zh_not_empty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prompt_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    node_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_text_en: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text_zh: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        default=dict,
        nullable=False,
    )
    output_schema_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class ResearchRunModel(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_summary: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    forecast: Mapped[ForecastModel | None] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )
    evaluation: Mapped[ForecastEvaluationModel | None] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )


class SchedulerRunModel(Base):
    __tablename__ = "scheduler_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_stage: Mapped[str] = mapped_column(String(128), default="scheduled", nullable=False)
    agent_statuses: Mapped[list[dict[str, str]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    agent_diagnostics: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_summary: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)


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
    window_directions: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    entry_price: Mapped[float | None] = mapped_column(nullable=True)
    entry_price_low: Mapped[float | None] = mapped_column(nullable=True)
    entry_price_high: Mapped[float | None] = mapped_column(nullable=True)
    take_profit_price: Mapped[float | None] = mapped_column(nullable=True)
    stop_loss_price: Mapped[float | None] = mapped_column(nullable=True)
    holding_period: Mapped[str] = mapped_column(String(255), nullable=False)
    intraday_action: Mapped[str] = mapped_column(Text, nullable=False)
    long_term_action: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    technical_summary: Mapped[str] = mapped_column(Text, nullable=False)
    macro_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    news_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_sentiment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_data_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_summary: Mapped[str] = mapped_column(Text, nullable=False)
    agent_votes: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )
    risk_notes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_package: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    bull_opening_case: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    bear_opening_case: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    bull_rebuttal: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    bear_rebuttal: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    bull_final_position: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    bear_final_position: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    committee_decision: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    validation_status: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    prompt_versions: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        nullable=False,
    )

    run: Mapped[ResearchRunModel] = relationship(back_populates="forecast")
    evaluation: Mapped[ForecastEvaluationModel | None] = relationship(
        back_populates="forecast",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )


class ForecastEvaluationModel(Base):
    __tablename__ = "forecast_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    forecast_id: Mapped[int] = mapped_column(
        ForeignKey("forecasts.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("research_runs.id"),
        nullable=False,
        index=True,
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    evaluation_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    direction_hit: Mapped[bool] = mapped_column(nullable=False)
    pnl_points: Mapped[float] = mapped_column(nullable=False)
    settlement_price: Mapped[float] = mapped_column(nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_notes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(JSON), default=list, nullable=False)
    signal_coverage: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), default=dict, nullable=False)

    forecast: Mapped[ForecastModel] = relationship(back_populates="evaluation")
    run: Mapped[ResearchRunModel] = relationship(back_populates="evaluation")
