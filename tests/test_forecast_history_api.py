from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

from fastapi.testclient import TestClient

from goldfxgraph.api.app import create_app
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import (
    AgentVote,
    ForecastDirection,
    ForecastEvaluationResult,
    ForecastHistoryItem,
    ForecastResult,
    ResearchRunResult,
)
from goldfxgraph.timeframes import trading_day_for_timestamp


class HistoryInMemoryForecastRepository:
    def __init__(self) -> None:
        self.history: list[ForecastHistoryItem] = []

    async def get_forecast_history(self, limit: int = 50) -> list[ForecastHistoryItem]:
        return self.history[:limit]

    async def get_daily_forecast_history(
        self,
        limit: int = 50,
        *,
        timezone_name: str,
        cutoff_hour: int,
        cutoff_minute: int,
    ) -> list[ForecastHistoryItem]:
        daily_history: list[ForecastHistoryItem] = []
        seen_days: set[date] = set()
        for item in self.history:
            trading_day = trading_day_for_timestamp(
                item.forecast.reference_time,
                timezone_name=timezone_name,
                cutoff_hour=cutoff_hour,
                cutoff_minute=cutoff_minute,
            )
            if trading_day in seen_days:
                continue
            seen_days.add(trading_day)
            daily_history.append(
                ForecastHistoryItem(
                    forecast=item.forecast,
                    evaluation=item.evaluation,
                    trading_day=trading_day,
                )
            )
            if len(daily_history) >= limit:
                break
        return daily_history

    async def get_latest_forecast(self) -> ForecastResult | None:
        if not self.history:
            return None
        return self.history[0].forecast

    async def get_research_run(self, run_id: int) -> ResearchRunResult | None:
        return None


def test_history_endpoint_returns_empty_list_when_no_history_exists() -> None:
    client = TestClient(
        create_app(testing=True, repository=cast(ForecastRepository, HistoryInMemoryForecastRepository()))
    )

    response = client.get("/api/v1/forecast/history")

    assert response.status_code == 200
    assert response.json() == []


def test_history_endpoint_returns_structured_history_items() -> None:
    repository = HistoryInMemoryForecastRepository()
    repository.history = [
        _history_item(reference_time=datetime(2024, 1, 2, 13, 0, tzinfo=UTC), forecast_id=2, pnl_points=12.5),
        _history_item(reference_time=datetime(2024, 1, 2, 8, 30, tzinfo=UTC), forecast_id=1, pnl_points=-8.0),
        _history_item(reference_time=datetime(2024, 1, 1, 9, 30, tzinfo=UTC), forecast_id=3, pnl_points=6.0),
    ]
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, repository)))

    response = client.get("/api/v1/forecast/history?limit=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["forecast"]["id"] == 2
    assert body[0]["forecast"]["symbol"] == "XAUUSD"
    assert body[0]["forecast"]["direction"] == "bullish"
    assert body[0]["evaluation"]["pnl_points"] == 12.5
    assert body[0]["evaluation"]["result"] == "win"
    assert "market_sentiment_summary" in body[0]["forecast"]


def _history_item(*, reference_time: datetime, forecast_id: int, pnl_points: float) -> ForecastHistoryItem:
    forecast = ForecastResult(
        id=forecast_id,
        run_id=forecast_id + 10,
        reference_time=reference_time,
        data_timestamp=reference_time,
        data_source="unit-test",
        current_price=2050.25,
        daily_open=2040,
        daily_high=2060,
        daily_low=2030,
        daily_close=2048,
        direction=ForecastDirection.bullish,
        entry_price=2050.25,
        take_profit_price=2080,
        stop_loss_price=2035,
        holding_period="1-3 个交易日",
        intraday_action="仅用于研究观察",
        long_term_action="继续观察日线确认",
        confidence_score=0.64,
        technical_summary="技术面偏多",
        macro_summary="宏观面中性",
        news_summary="新闻面中性",
        market_sentiment_summary="市场情绪中性",
        alt_data_summary="另类数据不可用",
        risk_summary="波动风险可控",
        agent_votes=[
            AgentVote(
                agent="technical",
                direction=ForecastDirection.bullish,
                confidence=0.7,
                rationale="趋势偏多",
            )
        ],
        risk_notes=["仅供研究"],
    )
    evaluation = ForecastEvaluationResult(
        forecast_id=forecast.id or 1,
        run_id=forecast.run_id or 1,
        evaluated_at=reference_time,
        evaluation_window_end=reference_time,
        result="win" if pnl_points > 0 else "loss",
        direction_hit=pnl_points > 0,
        pnl_points=pnl_points,
        settlement_price=forecast.entry_price + pnl_points,
        summary="历史评估摘要",
        feedback_notes=["收盘复盘"],
        signal_coverage={"sentiment": "covered", "alt_data": "unavailable"},
    )
    return ForecastHistoryItem(forecast=forecast, evaluation=evaluation)
