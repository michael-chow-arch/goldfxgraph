from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from goldfxgraph.backfill.eod_evaluation import run_eod_forecast_evaluation
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import AgentVote, DailyBar, ForecastDirection, ForecastResult
from goldfxgraph.workflow.nodes import evaluate_forecast_performance

pytestmark = pytest.mark.asyncio


def _forecast(*, reference_time: datetime, direction: ForecastDirection = ForecastDirection.bullish) -> ForecastResult:
    return ForecastResult(
        reference_time=reference_time,
        data_timestamp=reference_time,
        data_source="unit",
        current_price=2050,
        daily_open=2040,
        daily_high=2060,
        daily_low=2035,
        daily_close=2048,
        direction=direction,
        entry_price=2049,
        take_profit_price=2075,
        stop_loss_price=2032,
        holding_period="1-3 days",
        intraday_action="等待回踩确认",
        long_term_action="仅适合小仓位研究观察",
        confidence_score=0.62,
        technical_summary="技术面偏强",
        macro_summary="宏观面中性",
        news_summary="新闻面中性",
        risk_summary="波动风险较高",
        agent_votes=[
            AgentVote(agent="technical", direction=direction, confidence=0.7, rationale="trend"),
        ],
        risk_notes=["仅供研究"],
    )


def _market_bars() -> list[DailyBar]:
    return [
        DailyBar(date=date(2024, 1, 1), open=2040, high=2050, low=2035, close=2046, source="unit", symbol="XAUUSD"),
        DailyBar(date=date(2024, 1, 2), open=2048, high=2078, low=2038, close=2072, source="unit", symbol="XAUUSD"),
    ]


def _settings(tmp_path: Path) -> GoldFXGraphSettings:
    return GoldFXGraphSettings(
        database_url="sqlite+aiosqlite:///:memory:",
        xauusd_csv_path=tmp_path / "unused.csv",
        eod_backfill_timezone="Asia/Shanghai",
        eod_backfill_cutoff_hour=8,
        eod_backfill_cutoff_minute=0,
        openai_api_key=SecretStr("test"),
    )


async def test_evaluate_forecast_performance_uses_conservative_loss_on_double_touch() -> None:
    forecast = _forecast(reference_time=datetime(2024, 1, 2, 15, 0, tzinfo=UTC))
    forecast.id = 1
    forecast.run_id = 1
    bar = DailyBar(
        date=date(2024, 1, 2),
        open=2048,
        high=2080,
        low=2030,
        close=2060,
        source="unit",
    )

    evaluation = evaluate_forecast_performance(forecast, bar, evaluated_at=datetime(2024, 1, 2, 23, 30, tzinfo=UTC))

    assert evaluation.result == "loss"
    assert evaluation.direction_hit is False
    assert evaluation.pnl_points < 0


async def test_run_eod_forecast_evaluation_persists_today_forecast(tmp_path: Path) -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    try:
        await repo.upsert_market_bars(_market_bars())
        run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
        forecast = await repo.save_forecast(run.id, _forecast(reference_time=datetime(2024, 1, 2, 15, 0, tzinfo=UTC)))
        await repo.mark_run_success(run.id)

        result = await run_eod_forecast_evaluation(
            settings=_settings(tmp_path),
            repository=repo,
            now=datetime(2024, 1, 2, 23, 30, tzinfo=UTC),
        )

        evaluations = await repo.get_forecast_evaluations(forecast.id)
        loaded_run = await repo.get_research_run(run.id)

        assert result.written is True
        assert result.status == "written"
        assert result.evaluated_forecast_ids == [forecast.id]
        assert len(result.summaries) == 1
        assert evaluations[0].forecast_id == forecast.id
        assert evaluations[0].pnl_points > 0
        assert loaded_run is not None
        assert loaded_run.evaluation is not None
        assert "win" in loaded_run.evaluation.result
    finally:
        await session_factory.engine.dispose()


async def test_run_eod_forecast_evaluation_records_neutral_market_move(tmp_path: Path) -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    try:
        await repo.upsert_market_bars(_market_bars())
        run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
        forecast = await repo.save_forecast(
            run.id,
            _forecast(reference_time=datetime(2024, 1, 2, 15, 0, tzinfo=UTC), direction=ForecastDirection.neutral),
        )
        await repo.mark_run_success(run.id)

        result = await run_eod_forecast_evaluation(
            settings=_settings(tmp_path),
            repository=repo,
            now=datetime(2024, 1, 2, 23, 30, tzinfo=UTC),
        )

        evaluations = await repo.get_forecast_evaluations(forecast.id)

        assert result.written is True
        assert result.status == "written"
        assert evaluations[0].result == "flat"
        assert evaluations[0].pnl_points != 0
        assert evaluations[0].pnl_points == pytest.approx(23.0)
        assert "持平/区间" in evaluations[0].summary
        assert "flat" not in evaluations[0].summary
    finally:
        await session_factory.engine.dispose()


async def test_run_eod_forecast_evaluation_matches_forecast_by_data_timestamp_when_reference_rolls_over(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    try:
        await repo.upsert_market_bars(_market_bars())
        run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
        forecast = _forecast(reference_time=datetime(2024, 1, 2, 23, 30, tzinfo=UTC))
        forecast.data_timestamp = datetime(2024, 1, 2, 21, 30, tzinfo=UTC)
        forecast = await repo.save_forecast(run.id, forecast)
        await repo.mark_run_success(run.id)

        result = await run_eod_forecast_evaluation(
            settings=_settings(tmp_path),
            repository=repo,
            now=datetime(2024, 1, 2, 23, 30, tzinfo=UTC),
        )

        evaluations = await repo.get_forecast_evaluations(forecast.id)

        assert result.written is True
        assert result.status == "written"
        assert result.evaluated_forecast_ids == [forecast.id]
        assert evaluations[0].forecast_id == forecast.id
        assert evaluations[0].pnl_points > 0
    finally:
        await session_factory.engine.dispose()


async def test_run_eod_forecast_evaluation_noops_without_forecast(tmp_path: Path) -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    try:
        await repo.upsert_market_bars(_market_bars())
        result = await run_eod_forecast_evaluation(
            settings=_settings(tmp_path),
            repository=repo,
            now=datetime(2024, 1, 2, 23, 30, tzinfo=UTC),
        )

        assert result.written is False
        assert result.status == "no-op"
        assert result.evaluated_forecast_ids == []
        assert result.summaries == []
    finally:
        await session_factory.engine.dispose()
