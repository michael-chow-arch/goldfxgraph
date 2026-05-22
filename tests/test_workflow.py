from datetime import UTC, date, datetime

import pytest

from goldfxgraph.indicators.technical import compute_technical_indicators
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import CurrentQuote, DailyBar, ForecastDirection
from goldfxgraph.workflow.graph import REQUIRED_NODE_NAMES, build_forecast_graph
from goldfxgraph.workflow.nodes import (
    WorkflowState,
    create_research_forecast_from_inputs,
    tool_persist_forecast,
    tool_persist_research_run,
)


def _bars() -> list[DailyBar]:
    return [
        DailyBar(
            date=date(2024, 1, day),
            open=2000 + day,
            high=2005 + day,
            low=1995 + day,
            close=2002 + day,
        )
        for day in range(1, 31)
    ]


def _quote() -> CurrentQuote:
    return CurrentQuote(
        current_price=2040,
        data_source="unit",
        data_timestamp=datetime.now(UTC),
    )


def test_graph_contains_required_node_names() -> None:
    graph = build_forecast_graph()

    assert set(REQUIRED_NODE_NAMES).issubset(set(graph.nodes))


def test_forecast_planning_output_is_structured() -> None:
    bars = _bars()

    forecast = create_research_forecast_from_inputs(
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
    )

    assert forecast.direction in {ForecastDirection.bullish, ForecastDirection.bearish, ForecastDirection.neutral}
    assert forecast.entry_price is not None and forecast.entry_price > 0
    assert forecast.take_profit_price is not None and forecast.take_profit_price > 0
    assert forecast.stop_loss_price is not None and forecast.stop_loss_price > 0
    assert forecast.agent_votes
    assert forecast.risk_notes
    assert "不构成金融建议" in forecast.disclaimer


@pytest.mark.asyncio
async def test_persistence_nodes_save_run_and_forecast() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    bars = _bars()
    forecast = create_research_forecast_from_inputs(
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
    )
    state = WorkflowState(repository=repo, latest_bar=bars[-1], forecast=forecast)

    state = await tool_persist_research_run(state)
    state = await tool_persist_forecast(state)
    run_id = state.get("run_id")
    assert run_id is not None
    loaded = await repo.get_research_run(run_id)

    assert loaded is not None
    assert loaded.status == "success"
    assert loaded.forecast is not None
    assert loaded.forecast.direction == forecast.direction
    await session_factory.engine.dispose()
