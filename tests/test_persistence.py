from datetime import UTC, datetime, timedelta

import pytest

from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import AgentVote, ForecastDirection, ForecastResult

pytestmark = pytest.mark.asyncio


def _forecast(
    *,
    reference_time: datetime | None = None,
    direction: ForecastDirection = ForecastDirection.bullish,
) -> ForecastResult:
    now = reference_time or datetime.now(UTC)
    return ForecastResult(
        reference_time=now,
        data_timestamp=now,
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


async def test_repository_saves_run_and_latest_forecast() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    saved = await repo.save_forecast(run.id, _forecast())
    await repo.mark_run_success(run.id)
    latest = await repo.get_latest_forecast()
    loaded_run = await repo.get_research_run(run.id)

    assert saved.id is not None
    assert latest is not None
    assert latest.direction == ForecastDirection.bullish
    assert latest.reference_time.tzinfo is not None
    assert latest.data_timestamp.tzinfo is not None
    assert loaded_run is not None
    assert loaded_run.status == "success"
    assert loaded_run.started_at.tzinfo is not None
    assert loaded_run.forecast is not None


async def test_repository_records_failed_run() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD"})
    await repo.mark_run_failed(run.id, "CSV 缺少 low 字段")
    loaded = await repo.get_research_run(run.id)

    assert loaded is not None
    assert loaded.status == "failed"
    assert loaded.error_message == "CSV 缺少 low 字段"


async def test_repository_returns_newest_forecast_and_round_trips_json_fields() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    older_time = datetime.now(UTC) - timedelta(hours=1)
    newer_time = datetime.now(UTC)

    older_run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "window": "older"})
    await repo.save_forecast(older_run.id, _forecast(reference_time=older_time, direction=ForecastDirection.neutral))
    newer_run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "window": "newer"})
    newer = await repo.save_forecast(
        newer_run.id,
        _forecast(reference_time=newer_time, direction=ForecastDirection.bullish),
    )

    latest = await repo.get_latest_forecast()
    loaded_run = await repo.get_research_run(newer_run.id)

    assert latest is not None
    assert latest.id == newer.id
    assert latest.agent_votes == newer.agent_votes
    assert latest.risk_notes == ["仅供研究"]
    assert loaded_run is not None
    assert loaded_run.input_summary["window"] == "newer"


async def test_repository_serializes_json_safe_input_summary() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    observed_at = datetime(2024, 1, 1, 8, 30, tzinfo=UTC)

    run = await repo.create_research_run(input_summary={"symbol": "XAUUSD", "observed_at": observed_at})
    loaded_run = await repo.get_research_run(run.id)

    assert loaded_run is not None
    assert loaded_run.input_summary["observed_at"] == "2024-01-01T08:30:00Z"


async def test_repository_returns_none_for_missing_research_run() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)

    assert await repo.get_research_run(999) is None
