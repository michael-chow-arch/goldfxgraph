from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ForecastDirection(StrEnum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class DailyBar(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float | None = Field(default=None, ge=0)
    source: str | None = None
    symbol: str = "XAUUSD"

    @model_validator(mode="after")
    def validate_ohlc_range(self) -> DailyBar:
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be within low/high range")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be within low/high range")
        return self


class MarketDataSet(BaseModel):
    symbol: str = "XAUUSD"
    bars: list[DailyBar]
    latest_bar: DailyBar


class CurrentQuote(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    symbol: str = "XAUUSD"
    current_price: float = Field(gt=0)
    data_source: str
    data_timestamp: datetime

    @model_validator(mode="after")
    def validate_quote(self) -> CurrentQuote:
        if not isfinite(self.current_price):
            raise ValueError("current_price must be finite")
        if not self.data_source.strip():
            raise ValueError("data_source must not be empty")
        return self


class TechnicalIndicators(BaseModel):
    sma_20: float | None = None
    ema_12: float | None = None
    rsi_14: float | None = None
    atr_14: float | None = None
    unavailable: dict[str, str] = Field(default_factory=dict)


class AgentVote(BaseModel):
    agent: str
    direction: ForecastDirection
    confidence: float = Field(ge=0, le=1)
    rationale: str


class ForecastResult(BaseModel):
    id: int | None = None
    run_id: int | None = None
    symbol: str = "XAUUSD"
    reference_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data_timestamp: datetime
    data_source: str
    current_price: float
    daily_open: float
    daily_high: float
    daily_low: float
    daily_close: float
    direction: ForecastDirection
    entry_price: float | None = None
    take_profit_price: float | None = None
    stop_loss_price: float | None = None
    holding_period: str
    intraday_action: str
    long_term_action: str
    confidence_score: float = Field(ge=0, le=1)
    technical_summary: str
    macro_summary: str | None = None
    news_summary: str | None = None
    risk_summary: str
    agent_votes: list[AgentVote] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    disclaimer: str = "本结果仅用于研究和决策支持，不构成金融建议、投资建议或交易指令。"


class ResearchRunResult(BaseModel):
    id: int | None = None
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    input_summary: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    forecast: ForecastResult | None = None
