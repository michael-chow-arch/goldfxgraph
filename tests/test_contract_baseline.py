from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from goldfxgraph.api.app import create_app
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import AgentVote, ForecastDirection, ForecastResult, ForecastWindowDirection
from goldfxgraph.workflow.graph import REQUIRED_NODE_NAMES, build_forecast_graph
from goldfxgraph.workflow.nodes import WorkflowState


def _forecast() -> ForecastResult:
    reference_time = datetime(2024, 1, 2, 8, 30, tzinfo=UTC)
    return ForecastResult(
        id=101,
        run_id=88,
        reference_time=reference_time,
        data_timestamp=reference_time,
        data_source="TradingView",
        current_price=2051.75,
        daily_open=2040.0,
        daily_high=2063.5,
        daily_low=2035.25,
        daily_close=2055.1,
        direction=ForecastDirection.bullish,
        window_directions=[
            ForecastWindowDirection(
                window_label="0-3天",
                direction=ForecastDirection.bullish,
                strength="moderate",
                confidence=0.68,
                reason="短线趋势延续",
            )
        ],
        entry_price=2051.0,
        entry_price_low=2048.5,
        entry_price_high=2053.5,
        take_profit_price=2078.0,
        stop_loss_price=2038.0,
        holding_period="1-3 days",
        intraday_action="回踩确认后分批观察",
        long_term_action="中线继续观察趋势延续",
        confidence_score=0.64,
        technical_summary="技术面偏多",
        macro_summary="宏观面中性偏多",
        news_summary="新闻面影响有限",
        market_sentiment_summary="市场情绪温和偏多",
        alt_data_summary="另类数据暂未出现明显背离",
        risk_summary="波动风险可控",
        agent_votes=[
            AgentVote(
                agent="technical",
                direction=ForecastDirection.bullish,
                confidence=0.7,
                rationale="趋势仍然向上",
            )
        ],
        risk_notes=["仅供研究", "请结合仓位管理"],
    )


def test_workflow_graph_retopologizes_for_committee_flow() -> None:
    graph = build_forecast_graph()

    assert set(REQUIRED_NODE_NAMES).issubset(set(graph.nodes))
    assert graph.edges == {
        ("__start__", "router_validate_request"),
        ("router_validate_request", "tool_ensure_market_data_freshness"),
        ("tool_ensure_market_data_freshness", "tool_load_market_data"),
        ("tool_load_market_data", "tool_fetch_current_gold_quote"),
        ("tool_fetch_current_gold_quote", "tool_compute_indicators"),
        ("tool_compute_indicators", "agent_technical_analysis"),
        ("agent_technical_analysis", "tool_fetch_macro_inputs"),
        ("tool_fetch_macro_inputs", "agent_macro_analysis"),
        ("agent_macro_analysis", "tool_fetch_newsflow_inputs"),
        ("tool_fetch_newsflow_inputs", "agent_news_analysis"),
        ("agent_news_analysis", "tool_fetch_pizza_index_inputs"),
        ("tool_fetch_pizza_index_inputs", "tool_load_forecast_feedback_history"),
        ("tool_load_forecast_feedback_history", "tool_fetch_polymarket_inputs"),
        ("tool_fetch_polymarket_inputs", "tool_fetch_market_sentiment_inputs"),
        ("tool_fetch_market_sentiment_inputs", "tool_fetch_alt_data_inputs"),
        ("tool_fetch_alt_data_inputs", "agent_market_sentiment_analysis"),
        ("agent_market_sentiment_analysis", "agent_alt_data_analysis"),
        ("agent_alt_data_analysis", "agent_risk_analysis"),
        ("agent_risk_analysis", "node_build_evidence_package"),
        ("node_build_evidence_package", "agent_bull_opening_case"),
        ("node_build_evidence_package", "agent_bear_opening_case"),
        ("agent_bull_opening_case", "agent_bull_rebuttal"),
        ("agent_bull_opening_case", "agent_bear_rebuttal"),
        ("agent_bear_opening_case", "agent_bull_rebuttal"),
        ("agent_bear_opening_case", "agent_bear_rebuttal"),
        ("agent_bull_rebuttal", "agent_bull_final_position"),
        ("agent_bull_rebuttal", "agent_bear_final_position"),
        ("agent_bear_rebuttal", "agent_bull_final_position"),
        ("agent_bear_rebuttal", "agent_bear_final_position"),
        ("agent_bull_final_position", "agent_trading_committee_chair"),
        ("agent_bear_final_position", "agent_trading_committee_chair"),
        ("agent_trading_committee_chair", "node_validate_committee_decision"),
        ("agent_repair_committee_decision", "node_validate_committee_decision"),
        ("node_persist_forecast", "router_finalize_result"),
        ("router_finalize_result", "__end__"),
    }
    assert "node_validate_committee_decision" in graph.branches
    assert set(graph.branches["node_validate_committee_decision"]) == {"_route_committee_validation"}

    stable_state_keys = {
        "bars",
        "latest_bar",
        "quote",
        "indicators",
        "technical_summary",
        "macro_summary",
        "news_summary",
        "market_sentiment_summary",
        "alt_data_summary",
        "risk_summary",
        "agent_votes",
        "risk_notes",
        "evidence_package",
        "bull_opening_case",
        "bear_opening_case",
        "bull_rebuttal",
        "bear_rebuttal",
        "bull_final_position",
        "bear_final_position",
        "committee_decision",
        "validation_status",
        "validation_errors",
        "validation_warnings",
        "committee_validation_attempts",
        "committee_repair_attempts",
        "final_forecast",
        "prompt_versions",
        "forecast",
        "run_id",
        "result",
    }
    assert stable_state_keys.issubset(set(WorkflowState.__annotations__))


def test_forecast_result_public_contract_remains_structured() -> None:
    field_names = set(ForecastResult.model_fields)

    assert {
        "symbol",
        "reference_time",
        "data_timestamp",
        "data_source",
        "current_price",
        "daily_open",
        "daily_high",
        "daily_low",
        "daily_close",
        "direction",
        "window_directions",
        "entry_price",
        "entry_price_low",
        "entry_price_high",
        "take_profit_price",
        "stop_loss_price",
        "holding_period",
        "intraday_action",
        "long_term_action",
        "confidence_score",
        "technical_summary",
        "macro_summary",
        "news_summary",
        "market_sentiment_summary",
        "alt_data_summary",
        "risk_summary",
        "agent_votes",
        "risk_notes",
        "disclaimer",
    }.issubset(field_names)
    assert {direction.value for direction in ForecastDirection} == {"bullish", "bearish", "neutral"}
    assert "不构成金融建议" in str(ForecastResult.model_fields["disclaimer"].default)


@pytest.mark.asyncio
async def test_forecast_repository_preserves_current_contract_fields() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repository = ForecastRepository(session_factory)

    run = await repository.create_research_run(input_summary={"symbol": "XAUUSD", "contract": "baseline"})
    saved = await repository.save_forecast(run.id, _forecast())
    latest = await repository.get_latest_forecast()
    loaded_run = await repository.get_research_run(run.id)

    assert saved.id is not None
    assert latest is not None
    assert latest.market_sentiment_summary == "市场情绪温和偏多"
    assert latest.alt_data_summary == "另类数据暂未出现明显背离"
    assert latest.window_directions[0].window_label == "0-3天"
    assert latest.agent_votes[0].agent == "technical"
    assert latest.risk_notes == ["仅供研究", "请结合仓位管理"]
    assert loaded_run is not None
    assert loaded_run.forecast is not None
    assert loaded_run.forecast.disclaimer.startswith("本结果仅用于研究和决策支持")


class _LatestForecastRepository:
    def __init__(self, forecast: ForecastResult | None) -> None:
        self._forecast = forecast

    async def get_latest_forecast(self) -> ForecastResult | None:
        return self._forecast


def test_latest_forecast_api_returns_structured_contract() -> None:
    repository = _LatestForecastRepository(_forecast())
    client = TestClient(create_app(testing=True, repository=cast(ForecastRepository, repository)))

    response = client.get("/api/v1/forecast/latest")

    assert response.status_code == 200
    body = response.json()
    assert body["direction"] == "bullish"
    assert body["current_price"] == 2051.75
    assert body["data_source"] == "TradingView"
    assert body["market_sentiment_summary"] == "市场情绪温和偏多"
    assert body["alt_data_summary"] == "另类数据暂未出现明显背离"
    assert body["risk_notes"] == ["仅供研究", "请结合仓位管理"]
    assert body["disclaimer"].startswith("本结果仅用于研究和决策支持")
    assert body["agent_votes"][0]["agent"] == "technical"
    assert body["window_directions"][0]["window_label"] == "0-3天"


def test_frontend_contract_binds_current_api_and_dashboard_fields() -> None:
    service_source = Path("apps/web/src/services/forecastApi.ts").read_text(encoding="utf-8")
    type_source = Path("apps/web/src/types/forecast.ts").read_text(encoding="utf-8")
    page_source = Path("apps/web/src/pages/GoldForecastDashboard.vue").read_text(encoding="utf-8")

    assert "/api/v1/forecast/latest" in service_source
    assert "/api/v1/forecast/history?limit=" in service_source
    assert "/api/v1/research-status/latest" in service_source
    assert "/api/v1/market-data/bars?symbol=" in service_source
    assert "VITE_API_BASE_URL" in service_source
    assert "FinalForecast" in service_source
    assert "CommitteeDecision" in type_source
    assert "PromptVersionMetadata" in type_source
    assert "final_bias?: FinalBias | null;" in type_source
    assert "committee_decision?: CommitteeDecision | null;" in type_source
    assert "validation_status?: ValidationResult | null;" in type_source
    assert "prompt_versions?: PromptVersionMetadata[];" in type_source
    assert "bull_opening_case?: DebateCase | null;" in type_source

    assert "market_sentiment_summary?: string | null;" in type_source
    assert "alt_data_summary?: string | null;" in type_source
    assert "risk_notes: string[];" in type_source
    assert "disclaimer: string;" in type_source
    assert "direction: ForecastDirection;" in type_source

    for snippet in (
        "委员会证据包",
        "两轮对抗式辩论",
        "主席仲裁与验证",
        "Graph Execution Trace",
        "committeeBiasLabel",
        "committeePromptVersions",
        "committeeTraceNodes",
        "forecast.value.entry_price_low",
        "forecast.value.entry_price_high",
        "forecast.value.take_profit_price",
        "forecast.value.stop_loss_price",
        "forecast.holding_period",
        "market_sentiment_summary",
        "alt_data_summary",
        "forecast.value.risk_notes",
        "forecast.disclaimer",
        "forecast.agent_votes",
        "committeeDecision?.decision_summary",
        "committeeValidationErrors",
        "committeeTradePlanRows",
    ):
        assert snippet in page_source
