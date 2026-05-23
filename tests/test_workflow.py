from datetime import UTC, date, datetime

import httpx
import pytest
from pydantic import SecretStr

from goldfxgraph.indicators.technical import compute_technical_indicators
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import AgentVote, CurrentQuote, DailyBar, ForecastDirection
from goldfxgraph.workflow.graph import REQUIRED_NODE_NAMES, build_forecast_graph
from goldfxgraph.workflow.nodes import (
    WorkflowState,
    agent_forecast_planning,
    agent_macro_analysis,
    agent_technical_analysis,
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


def test_agent_node_uses_configured_agent_api_without_leaking_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer secret-token"
        assert "secret-token" not in request.content.decode()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"远程宏观摘要：美元与实际利率压力偏空。",'
                                '"direction":"bearish","confidence":0.62}'
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    settings = GoldFXGraphSettings(
        openai_base_url="https://agent.example.test/v1",
        openai_model="gpt-4.1-mini",
        openai_api_key=SecretStr("secret-token"),
    )
    state = WorkflowState(settings=settings, agent_http_transport=httpx.MockTransport(handler))

    state = agent_macro_analysis(state)

    assert len(requests) == 1
    assert str(requests[0].url) == "https://agent.example.test/v1/chat/completions"
    agent_votes = state.get("agent_votes")
    assert state.get("macro_summary") == "远程宏观摘要：美元与实际利率压力偏空。"
    assert agent_votes is not None
    assert agent_votes[0].direction == ForecastDirection.bearish
    assert agent_votes[0].confidence == 0.62
    assert "secret-token" not in str(state)


def test_agent_node_uses_deterministic_fallback_without_agent_api() -> None:
    bars = _bars()
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        raise AssertionError("agent API should not be called without configured base URL")

    state = WorkflowState(
        settings=GoldFXGraphSettings(openai_base_url=None, openai_model="gpt-4.1-mini"),
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
        agent_http_transport=httpx.MockTransport(handler),
    )

    state = agent_technical_analysis(state)

    assert called is False
    agent_votes = state.get("agent_votes")
    technical_summary = state.get("technical_summary")
    assert technical_summary is not None
    assert technical_summary.startswith("当前报价")
    assert agent_votes is not None
    assert agent_votes[0].agent == "technical"


def test_agent_node_uses_deterministic_fallback_without_complete_openai_config() -> None:
    bars = _bars()
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        raise AssertionError("OpenAI-compatible client should not be called with incomplete config")

    state = WorkflowState(
        settings=GoldFXGraphSettings(
            openai_base_url="https://agent.example.test/v1",
            openai_model=None,
            openai_api_key=SecretStr("secret-token"),
        ),
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
        agent_http_transport=httpx.MockTransport(handler),
    )

    state = agent_technical_analysis(state)

    assert called is False
    assert state.get("technical_summary", "").startswith("当前报价")
    agent_votes = state.get("agent_votes")
    assert agent_votes is not None
    assert agent_votes[0].direction == ForecastDirection.bullish


def test_forecast_planning_aligns_direction_and_levels_with_agent_votes() -> None:
    bars = _bars()
    quote = _quote()
    indicators = compute_technical_indicators(bars)
    deterministic = create_research_forecast_from_inputs(
        latest_bar=bars[-1],
        quote=quote,
        indicators=indicators,
    )
    assert deterministic.direction == ForecastDirection.bullish

    state = WorkflowState(
        latest_bar=bars[-1],
        quote=quote,
        indicators=indicators,
        agent_votes=[
            AgentVote(agent="technical", direction=ForecastDirection.bearish, confidence=0.9, rationale="远程技术看空"),
            AgentVote(agent="macro", direction=ForecastDirection.bearish, confidence=0.8, rationale="远程宏观看空"),
            AgentVote(agent="risk", direction=ForecastDirection.neutral, confidence=0.7, rationale="风险中性"),
        ],
        technical_summary="远程技术看空",
        macro_summary="远程宏观看空",
        risk_summary="风险中性",
    )

    state = agent_forecast_planning(state)
    forecast = state.get("forecast")

    assert forecast is not None
    assert forecast.direction == ForecastDirection.bearish
    assert forecast.confidence_score == pytest.approx(0.8)
    assert forecast.entry_price is not None
    assert forecast.take_profit_price is not None
    assert forecast.stop_loss_price is not None
    assert forecast.take_profit_price < forecast.entry_price < forecast.stop_loss_price
    assert "偏空" in forecast.intraday_action
    assert "防守或空头" in forecast.long_term_action


def test_agent_node_falls_back_deterministically_when_openai_response_is_invalid() -> None:
    bars = _bars()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    state = WorkflowState(
        settings=GoldFXGraphSettings(
            openai_base_url="https://agent.example.test/v1",
            openai_model="gpt-4.1-mini",
            openai_api_key=SecretStr("secret-token"),
        ),
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
        agent_http_transport=httpx.MockTransport(handler),
    )

    state = agent_technical_analysis(state)

    assert state.get("technical_summary", "").startswith("当前报价")
    agent_votes = state.get("agent_votes")
    assert agent_votes is not None
    assert agent_votes[0].agent == "technical"
    assert agent_votes[0].direction == ForecastDirection.bullish


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
