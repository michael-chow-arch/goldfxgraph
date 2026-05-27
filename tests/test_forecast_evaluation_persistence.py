from datetime import UTC, datetime, timedelta

import pytest

from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import (
    AgentVote,
    ForecastDirection,
    ForecastEvaluationResult,
    ForecastResult,
)

pytestmark = pytest.mark.asyncio


def _forecast(
    *,
    reference_time: datetime,
    direction: ForecastDirection = ForecastDirection.bullish,
) -> ForecastResult:
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
            AgentVote(
                agent="technical",
                direction=direction,
                confidence=0.7,
                rationale="trend",
            )
        ],
        risk_notes=["仅供研究"],
    )


def _evaluation(
    *,
    forecast_id: int,
    run_id: int,
    evaluated_at: datetime,
    pnl_points: float,
    summary: str,
) -> ForecastEvaluationResult:
    return ForecastEvaluationResult(
        forecast_id=forecast_id,
        run_id=run_id,
        evaluated_at=evaluated_at,
        evaluation_window_end=evaluated_at,
        result="win" if pnl_points > 0 else "loss",
        direction_hit=pnl_points > 0,
        pnl_points=pnl_points,
        settlement_price=2055 + pnl_points,
        summary=summary,
        feedback_notes=["结论已回写"],
        signal_coverage={"price": "covered", "sentiment": "unavailable"},
    )


async def test_repository_saves_evaluation_and_links_forecast() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    forecast = await repo.save_forecast(run.id, _forecast(reference_time=datetime.now(UTC)))
    evaluation = await repo.save_forecast_evaluation(
        forecast.id,
        _evaluation(
            forecast_id=forecast.id,
            run_id=run.id,
            evaluated_at=datetime.now(UTC),
            pnl_points=12.5,
            summary="多头命中止盈，表现正向。",
        ),
    )
    await repo.mark_run_success(run.id)

    loaded_run = await repo.get_research_run(run.id)
    evaluations = await repo.get_forecast_evaluations(forecast.id)
    history = await repo.get_forecast_history()

    assert evaluation.id is not None
    assert evaluations == [evaluation]
    assert loaded_run is not None
    assert loaded_run.forecast is not None
    assert loaded_run.forecast.id == forecast.id
    assert loaded_run.evaluation == evaluation
    assert history[0].forecast.id == forecast.id
    assert history[0].evaluation == evaluation
    await session_factory.engine.dispose()


async def test_repository_orders_history_by_latest_evaluation() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    older_run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "tag": "older"})
    older_forecast = await repo.save_forecast(
        older_run.id,
        _forecast(reference_time=datetime.now(UTC) - timedelta(days=1)),
    )
    await repo.save_forecast_evaluation(
        older_forecast.id,
        _evaluation(
            forecast_id=older_forecast.id,
            run_id=older_run.id,
            evaluated_at=datetime.now(UTC) - timedelta(hours=2),
            pnl_points=-8.0,
            summary="较早的 forecast 收盘后止损。",
        ),
    )

    newer_run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "tag": "newer"})
    newer_forecast = await repo.save_forecast(
        newer_run.id,
        _forecast(reference_time=datetime.now(UTC)),
    )
    await repo.save_forecast_evaluation(
        newer_forecast.id,
        _evaluation(
            forecast_id=newer_forecast.id,
            run_id=newer_run.id,
            evaluated_at=datetime.now(UTC),
            pnl_points=15.0,
            summary="较新的 forecast 命中止盈。",
        ),
    )

    history = await repo.get_forecast_history()

    assert len(history) == 2
    assert history[0].forecast.run_id == newer_run.id
    assert history[0].evaluation is not None
    assert history[0].evaluation.pnl_points == 15.0
    assert history[1].forecast.run_id == older_run.id
    assert history[1].evaluation is not None
    assert history[1].evaluation.pnl_points == -8.0
    await session_factory.engine.dispose()


async def test_repository_returns_latest_evaluation_summaries() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    forecast = await repo.save_forecast(run.id, _forecast(reference_time=datetime.now(UTC)))
    await repo.save_forecast_evaluation(
        forecast.id,
        _evaluation(
            forecast_id=forecast.id,
            run_id=run.id,
            evaluated_at=datetime.now(UTC),
            pnl_points=10.0,
            summary="第一条评估摘要。",
        ),
    )

    assert await repo.get_latest_evaluation_summary() == ["第一条评估摘要。"]
    await session_factory.engine.dispose()


async def test_repository_rejects_mismatched_evaluation_run_id() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    forecast = await repo.save_forecast(run.id, _forecast(reference_time=datetime.now(UTC)))

    with pytest.raises(ValueError, match="does not match"):
        await repo.save_forecast_evaluation(
            forecast.id,
            _evaluation(
                forecast_id=forecast.id,
                run_id=run.id + 1,
                evaluated_at=datetime.now(UTC),
                pnl_points=5.0,
                summary="run_id 不匹配。",
            ),
        )
    await session_factory.engine.dispose()
