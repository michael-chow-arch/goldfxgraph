import json
from datetime import UTC, date, datetime

import httpx
import pytest
from pydantic import SecretStr

from goldfxgraph.indicators.technical import compute_technical_indicators
from goldfxgraph.llm.openai_client import OpenAIAgentResult
from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.persistence.seed_prompt_templates import seed_default_committee_prompt_templates
from goldfxgraph.schemas.forecast import (
    Actionability,
    AgentVote,
    CommitteeDecision,
    CurrentQuote,
    DailyBar,
    DebateCase,
    DebateRebuttal,
    DebateSide,
    DebateStance,
    DecisionValidationResult,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceToolStatus,
    FinalBias,
    FinalDebatePosition,
    ForecastDirection,
    LongPlan,
    RangePlan,
    ShortPlan,
)
from goldfxgraph.workflow.graph import REQUIRED_NODE_NAMES, _route_committee_validation, build_forecast_graph
from goldfxgraph.workflow.nodes import (
    MarketDataFreshnessError,
    WorkflowState,
    agent_alt_data_analysis,
    agent_bear_final_position,
    agent_bear_opening_case,
    agent_bear_rebuttal,
    agent_bull_final_position,
    agent_bull_opening_case,
    agent_bull_rebuttal,
    agent_forecast_planning,
    agent_macro_analysis,
    agent_market_sentiment_analysis,
    agent_news_analysis,
    agent_repair_committee_decision,
    agent_technical_analysis,
    agent_trading_committee_chair,
    create_research_forecast_from_inputs,
    node_build_evidence_package,
    node_persist_forecast,
    node_validate_committee_decision,
    tool_ensure_market_data_freshness,
    tool_fetch_alt_data_inputs,
    tool_fetch_current_gold_quote,
    tool_fetch_macro_inputs,
    tool_fetch_market_sentiment_inputs,
    tool_fetch_newsflow_inputs,
    tool_fetch_pizza_index_inputs,
    tool_fetch_polymarket_inputs,
    tool_persist_forecast,
    tool_persist_research_run,
)


def _merge_state(state: dict[str, object], delta: dict[str, object]) -> dict[str, object]:
    merged = dict(state)
    merged.update(delta)
    return merged


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
        data_source="TradingView",
        data_timestamp=datetime.now(UTC),
    )


def _committee_validation_state(
    *,
    final_bias: FinalBias = FinalBias.bullish,
    actionability: Actionability = Actionability.trade_candidate,
    confidence_score: float = 0.68,
    evidence_tool_status: EvidenceToolStatus = EvidenceToolStatus.ok,
    include_long_plan: bool = True,
    include_short_plan: bool = False,
    include_range_plan: bool = False,
    wait_conditions: list[str] | None = None,
    long_plan_risk_reward: float = 2.0,
    short_plan_risk_reward: float = 2.0,
    range_plan_risk_reward: float = 1.8,
) -> WorkflowState:
    evidence_package = EvidencePackage(
        symbol="XAUUSD",
        reference_time=datetime.now(UTC),
        data_timestamp=datetime.now(UTC),
        data_source="TradingView",
        summary="证据包摘要",
        items=[
            EvidencePackageItem(
                item_id="technical",
                specialist_name="technical",
                category="price_action",
                signal="bullish",
                confidence=0.7,
                key_evidence=["技术面偏多"],
                risk_factors=["波动可控"],
                invalidation_conditions=["跌破关键支撑"],
                important_levels=["2050-2060"],
                data_freshness="latest_bar: fresh",
                tool_status=evidence_tool_status,
                degraded_reason="数据源降级" if evidence_tool_status != EvidenceToolStatus.ok else None,
                evidence_refs=["technical_summary"],
            )
        ],
        notes=["仅供研究"],
    )
    bull_opening_case = DebateCase(
        side=DebateSide.bull,
        thesis="看多开场",
        evidence_item_refs=["technical"],
        entry_zone="2050-2055",
        stop_loss_or_invalidation="2040",
        target_zone="2075-2080",
        risk_reward=2.0,
        weakness_acknowledged=["仍需承认回撤风险"],
        supporting_arguments=["技术面偏多"],
        confidence=0.66,
    )
    bear_opening_case = DebateCase(
        side=DebateSide.bear,
        thesis="看空开场",
        evidence_item_refs=["technical"],
        entry_zone="2055-2060",
        stop_loss_or_invalidation="2068",
        target_zone="2035-2040",
        risk_reward=2.0,
        weakness_acknowledged=["反方仍有趋势延续可能"],
        supporting_arguments=["反向情景存在"],
        confidence=0.58,
    )
    bull_rebuttal = DebateRebuttal(
        side=DebateSide.bull,
        responds_to_side=DebateSide.bear,
        rebutted_points=["空方对阻力位的强调"],
        accepted_points=["空方承认波动仍存在"],
        plan_adjustments=["上移入场确认条件"],
        confidence_trend="flat",
        confidence_change=0.0,
        evidence_item_refs=["technical"],
    )
    bear_rebuttal = DebateRebuttal(
        side=DebateSide.bear,
        responds_to_side=DebateSide.bull,
        rebutted_points=["多方对趋势延续的强调"],
        accepted_points=["多方承认失效条件清晰"],
        plan_adjustments=["收紧止损确认"],
        confidence_trend="flat",
        confidence_change=0.0,
        evidence_item_refs=["technical"],
    )
    bull_final_position = FinalDebatePosition(
        side=DebateSide.bull,
        stance=DebateStance.maintain,
        confidence=0.69,
        confidence_change=0.01,
        adopted_arguments=["趋势仍有延续空间"],
        rejected_arguments=["空方对短线阻力的放大"],
        plan_adjustments=["等待回踩确认"],
        abandon_conditions=["有效跌破 2040"],
        evidence_item_refs=["technical"],
    )
    bear_final_position = FinalDebatePosition(
        side=DebateSide.bear,
        stance=DebateStance.soften,
        confidence=0.55,
        confidence_change=-0.01,
        adopted_arguments=["上方阻力仍然存在"],
        rejected_arguments=["追空性价比不足"],
        plan_adjustments=["仅观察反弹质量"],
        abandon_conditions=["放量突破 2068"],
        evidence_item_refs=["technical"],
    )

    long_plan = (
        LongPlan(
            entry_zone="2050-2055",
            stop_loss="2040",
            invalidation_level="2038",
            target_zone="2075-2080",
            risk_reward=long_plan_risk_reward,
            conditions_to_enter=["回踩后重新站稳 2050"],
            conditions_to_abort=["跌破 2040"],
            evidence_item_refs=["technical"],
        )
        if include_long_plan
        else None
    )
    short_plan = (
        ShortPlan(
            entry_zone="2055-2060",
            stop_loss="2068",
            invalidation_level="2070",
            target_zone="2035-2040",
            risk_reward=short_plan_risk_reward,
            conditions_to_enter=["反弹失败后承压"],
            conditions_to_abort=["突破 2068"],
            evidence_item_refs=["technical"],
        )
        if include_short_plan
        else None
    )
    range_plan = (
        RangePlan(
            upper_sell_zone="2060-2068",
            lower_buy_zone="2042-2048",
            upper_stop="2072",
            lower_stop="2036",
            midline_target="2052",
            breakout_confirmation_level="2072",
            breakdown_confirmation_level="2036",
            range_invalidated_if="突破 2072 或跌破 2036",
            risk_reward=range_plan_risk_reward,
            conditions_to_enter=["区间边缘出现反转确认"],
            conditions_to_abort=["突破或跌破区间"],
            evidence_item_refs=["technical"],
        )
        if include_range_plan
        else None
    )

    committee_decision = CommitteeDecision(
        evidence_package=evidence_package,
        bull_opening_case=bull_opening_case,
        bear_opening_case=bear_opening_case,
        bull_rebuttal=bull_rebuttal,
        bear_rebuttal=bear_rebuttal,
        bull_final_position=bull_final_position,
        bear_final_position=bear_final_position,
        final_bias=final_bias,
        actionability=actionability,
        winning_side=DebateSide.bull,
        adopted_arguments=["趋势延续"],
        rejected_arguments=["盲目追涨"],
        long_plan=long_plan,
        short_plan=short_plan,
        range_plan=range_plan,
        wait_conditions=
        (
            ["等待方向确认"]
            if wait_conditions is None and final_bias == FinalBias.cautious
            else (wait_conditions or [])
        ),
        confidence_score=confidence_score,
        decision_summary="委员会决策摘要",
        risk_notes=["仅供研究"],
        evidence_item_refs=["technical"],
    )

    return WorkflowState(
        latest_bar=_bars()[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(_bars()),
        evidence_package=evidence_package,
        bull_opening_case=bull_opening_case,
        bear_opening_case=bear_opening_case,
        bull_rebuttal=bull_rebuttal,
        bear_rebuttal=bear_rebuttal,
        bull_final_position=bull_final_position,
        bear_final_position=bear_final_position,
        committee_decision=committee_decision,
        validation_errors=[],
        validation_warnings=[],
        committee_validation_attempts=0,
        committee_repair_attempts=0,
    )


def test_graph_contains_required_node_names() -> None:
    graph = build_forecast_graph()

    assert set(REQUIRED_NODE_NAMES).issubset(set(graph.nodes))
    assert {
        "tool_ensure_market_data_freshness",
        "tool_fetch_market_sentiment_inputs",
        "tool_fetch_alt_data_inputs",
        "tool_fetch_newsflow_inputs",
        "tool_fetch_pizza_index_inputs",
        "tool_fetch_polymarket_inputs",
        "agent_market_sentiment_analysis",
        "agent_alt_data_analysis",
    }.issubset(set(graph.nodes))


@pytest.mark.asyncio
async def test_tool_ensure_market_data_freshness_triggers_backfill_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_backfill(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return type("Result", (), {"status": "written", "failure_reason": None})()

    monkeypatch.setattr("goldfxgraph.workflow.nodes.run_eod_backfill", fake_backfill)

    state = WorkflowState(
        settings=GoldFXGraphSettings(),
        repository=ForecastRepository(create_session_factory("sqlite+aiosqlite:///:memory:")),
        run_id=1,
    )

    result = await tool_ensure_market_data_freshness(state)

    assert result == {}
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_tool_ensure_market_data_freshness_raises_when_backfill_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_backfill(**kwargs: object) -> object:
        return type(
            "Result",
            (),
            {"status": "failed", "failure_reason": "TradingView history unavailable"},
        )()

    monkeypatch.setattr("goldfxgraph.workflow.nodes.run_eod_backfill", fake_backfill)

    state = WorkflowState(
        settings=GoldFXGraphSettings(),
        repository=ForecastRepository(create_session_factory("sqlite+aiosqlite:///:memory:")),
        run_id=1,
    )

    with pytest.raises(MarketDataFreshnessError, match="TradingView history unavailable"):
        await tool_ensure_market_data_freshness(state)


@pytest.mark.asyncio
async def test_workflow_stops_before_market_data_loading_when_freshness_preflight_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_backfill(**kwargs: object) -> object:
        return type(
            "Result",
            (),
            {"status": "failed", "failure_reason": "TradingView history unavailable"},
        )()

    load_called = False

    async def fake_load_market_data(state: WorkflowState) -> WorkflowState:
        nonlocal load_called
        load_called = True
        return state

    monkeypatch.setattr("goldfxgraph.workflow.nodes.run_eod_backfill", fake_backfill)
    monkeypatch.setattr("goldfxgraph.workflow.graph.tool_load_market_data", fake_load_market_data)

    graph = build_forecast_graph().compile()
    state = WorkflowState(
        settings=GoldFXGraphSettings(),
        repository=ForecastRepository(create_session_factory("sqlite+aiosqlite:///:memory:")),
        run_id=1,
    )

    with pytest.raises(MarketDataFreshnessError, match="TradingView history unavailable"):
        await graph.ainvoke(state)

    assert load_called is False


def test_forecast_planning_output_is_structured() -> None:
    bars = _bars()

    forecast = create_research_forecast_from_inputs(
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
    )

    assert forecast.direction in {ForecastDirection.bullish, ForecastDirection.bearish, ForecastDirection.neutral}
    assert [item.window_label for item in forecast.window_directions] == ["0-3天", "3-5天", "6-15天", "15天后"]
    assert forecast.entry_price is not None and forecast.entry_price > 0
    assert forecast.take_profit_price is not None and forecast.take_profit_price > 0
    assert forecast.stop_loss_price is not None and forecast.stop_loss_price > 0
    assert forecast.agent_votes
    assert forecast.risk_notes
    assert "不构成金融建议" in forecast.disclaimer


def test_forecast_planning_uses_range_for_neutral_direction() -> None:
    bars = _bars()
    indicators = compute_technical_indicators(bars)
    neutral_indicators = indicators.model_copy(
        update={"sma_20": bars[-1].close, "ema_12": bars[-1].close, "rsi_14": 50.0}
    )
    quote = CurrentQuote(
        current_price=bars[-1].close,
        data_source="TradingView",
        data_timestamp=datetime.now(UTC),
    )

    forecast = create_research_forecast_from_inputs(
        latest_bar=bars[-1],
        quote=quote,
        indicators=neutral_indicators,
    )

    assert forecast.direction == ForecastDirection.neutral
    assert forecast.entry_price_low is not None
    assert forecast.entry_price_high is not None
    assert forecast.entry_price_low < forecast.entry_price_high
    assert "震荡区间" in forecast.intraday_action
    assert "聪明钱" in forecast.technical_summary


def test_tool_fetch_current_gold_quote_uses_tradingview_source(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    expected_quote = CurrentQuote(
        symbol="XAUUSD",
        current_price=2051.75,
        data_source="TradingView",
        data_timestamp=datetime.now(UTC),
    )
    monkeypatch.setattr(
        "goldfxgraph.workflow.nodes.CurrentQuoteProvider.fetch",
        lambda self: expected_quote,
    )

    state = WorkflowState(
        settings=GoldFXGraphSettings(),
        latest_bar=bars[-1],
        bars=bars,
    )

    result = tool_fetch_current_gold_quote(state)

    assert result["quote"].data_source == "TradingView"
    assert result["quote"].current_price == 2051.75
    assert result["quote"].symbol == "XAUUSD"


def test_tool_fetch_current_gold_quote_rejects_non_tradingview_source(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    monkeypatch.setattr(
        "goldfxgraph.workflow.nodes.CurrentQuoteProvider.fetch",
        lambda self: CurrentQuote(
            symbol="XAUUSD",
            current_price=2051.75,
            data_source="legacy-quote-api",
            data_timestamp=datetime.now(UTC),
        ),
    )

    state = WorkflowState(
        settings=GoldFXGraphSettings(),
        latest_bar=bars[-1],
        bars=bars,
    )

    with pytest.raises(QuoteProviderError, match="non-TradingView data source"):
        tool_fetch_current_gold_quote(state)


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
    state = WorkflowState(
        settings=settings,
        agent_http_transport=httpx.MockTransport(handler),
        macro_inputs={
            "dollar_index": {"status": "available"},
            "real_rates": {"status": "available"},
        },
    )

    state = _merge_state(state, agent_macro_analysis(state))

    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://agent.example.test/v1/chat/completions"
    body = json.loads(request.content.decode())
    assert body["model"] == "gpt-4.1-mini"
    assert body["response_format"] == {"type": "json_object"}
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert "macro" in body["messages"][0]["content"]
    assert "简体中文" in body["messages"][0]["content"]
    assert body["messages"][1]["role"] == "user"
    user_message = json.loads(body["messages"][1]["content"])
    assert user_message["agent_name"] == "macro"
    assert user_message["payload"]["agent"] == "macro"
    assert user_message["payload"]["symbol"] == "XAUUSD"
    assert user_message["payload"]["macro_inputs"]["dollar_index"]["status"] == "available"
    assert user_message["payload"]["macro_inputs"]["real_rates"]["status"] == "available"
    agent_votes = state.get("agent_votes")
    assert state.get("macro_summary") == "远程宏观摘要：美元与实际利率压力偏空。"
    assert agent_votes is not None
    assert agent_votes[0].direction == ForecastDirection.bearish
    assert agent_votes[0].confidence == 0.62
    assert "secret-token" not in str(state)


def test_macro_node_uses_real_macro_inputs_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    state = WorkflowState(
        settings=GoldFXGraphSettings(
            openai_base_url=None,
            openai_model="gpt-4.1-mini",
            openai_api_key=SecretStr("secret-token"),
        ),
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
    )

    monkeypatch.setattr(
        "goldfxgraph.workflow.nodes._fetch_dollar_index",
        lambda transport: (
            {
                "status": "available",
                "source": "fred",
                "value": 104.32,
                "change": -0.18,
            },
            None,
        ),
    )
    monkeypatch.setattr(
        "goldfxgraph.workflow.nodes._fetch_real_rates",
        lambda transport: (
            {
                "status": "available",
                "source": "fred",
                "value": 2.45,
                "change": -0.05,
            },
            None,
        ),
    )

    state = _merge_state(state, tool_fetch_macro_inputs(state))
    state = _merge_state(state, agent_macro_analysis(state))

    assert state.get("unavailable_signals", []) == []
    assert state.get("macro_summary", "").startswith("失败：macro agent")
    assert state.get("macro_inputs", {}).get("dollar_index", {}).get("status") == "available"
    assert state.get("macro_inputs", {}).get("real_rates", {}).get("status") == "available"


def test_agent_node_uses_failure_summary_without_agent_api() -> None:
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

    state = _merge_state(state, agent_technical_analysis(state))

    assert called is False
    agent_votes = state.get("agent_votes")
    technical_summary = state.get("technical_summary")
    assert technical_summary is not None
    assert technical_summary.startswith("失败：technical agent")
    assert agent_votes is not None
    assert agent_votes[0].agent == "technical"
    assert agent_votes[0].confidence == 0.0


def test_agent_node_uses_failure_summary_without_complete_openai_config() -> None:
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

    state = _merge_state(state, agent_technical_analysis(state))

    assert called is False
    assert state.get("technical_summary", "").startswith("失败：technical agent")
    agent_votes = state.get("agent_votes")
    assert agent_votes is not None
    assert agent_votes[0].direction == ForecastDirection.neutral
    assert agent_votes[0].confidence == 0.0


def test_agent_node_reports_placeholder_secret_as_unconfigured() -> None:
    bars = _bars()
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        raise AssertionError("OpenAI-compatible client should not be called with placeholder key")

    state = WorkflowState(
        settings=GoldFXGraphSettings(
            openai_base_url="https://agent.example.test/v1",
            openai_model="gpt-4.1-mini",
            openai_api_key=SecretStr("change_me"),
        ),
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
        agent_http_transport=httpx.MockTransport(handler),
    )

    state = _merge_state(state, agent_technical_analysis(state))

    assert called is False
    assert state.get("technical_summary", "").startswith("失败：technical agent")
    assert state.get("agent_diagnostics") is not None
    assert state["agent_diagnostics"][0]["agent"] == "technical"
    assert "未配置有效 base_url/model/API Key" in state["agent_diagnostics"][0]["message"]


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

    state = _merge_state(state, agent_forecast_planning(state))
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


def test_forecast_planning_includes_recent_feedback_history() -> None:
    bars = _bars()
    quote = _quote()
    indicators = compute_technical_indicators(bars)
    state = WorkflowState(
        latest_bar=bars[-1],
        quote=quote,
        indicators=indicators,
        agent_votes=[
            AgentVote(agent="technical", direction=ForecastDirection.bullish, confidence=0.72, rationale="技术看多"),
            AgentVote(agent="macro", direction=ForecastDirection.neutral, confidence=0.35, rationale="宏观中性"),
        ],
        technical_summary="技术看多",
        macro_summary="宏观中性",
        risk_summary="风险中性",
        forecast_feedback_history=["最近一次看多后止损", "上一轮偏多但收益有限"],
    )

    state = _merge_state(state, agent_forecast_planning(state))
    forecast = state.get("forecast")

    assert forecast is not None
    assert any("最近评估反馈" in note for note in forecast.risk_notes)
    assert "最近评估反馈" in forecast.risk_summary


def test_agent_node_falls_back_deterministically_when_openai_response_is_invalid(
    caplog: pytest.LogCaptureFixture,
) -> None:
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

    caplog.set_level("WARNING")
    state = _merge_state(state, agent_technical_analysis(state))

    assert state.get("technical_summary", "").startswith("失败：technical agent")
    agent_votes = state.get("agent_votes")
    assert agent_votes is not None
    assert agent_votes[0].agent == "technical"
    assert agent_votes[0].direction == ForecastDirection.neutral
    assert agent_votes[0].confidence == 0.0
    assert state.get("agent_diagnostics") is not None
    assert state["agent_diagnostics"][0]["agent"] == "technical"
    assert state["agent_diagnostics"][0]["message"] == (
        "OpenAI-compatible technical agent 调用失败，已标记为失败，不生成兜底输出。"
    )
    assert "OpenAI-compatible response returned invalid JSON for technical" in caplog.text
    assert state["agent_diagnostics"][0]["detail"] == "OpenAI-compatible response returned invalid JSON for technical"


def test_sentiment_and_alt_data_nodes_fail_without_openai() -> None:
    bars = _bars()
    quote = _quote()
    state = WorkflowState(
        settings=GoldFXGraphSettings(openai_base_url=None, openai_model=None),
        latest_bar=bars[-1],
        quote=quote,
        indicators=compute_technical_indicators(bars),
        forecast_feedback_history=["上一轮看多后回撤偏大"],
    )

    state = _merge_state(state, tool_fetch_market_sentiment_inputs(state))
    state = _merge_state(state, tool_fetch_alt_data_inputs(state))
    state = _merge_state(state, agent_market_sentiment_analysis(state))
    state = _merge_state(state, agent_alt_data_analysis(state))

    assert state.get("market_sentiment_summary", "").startswith("失败：market_sentiment agent")
    assert state.get("alt_data_summary", "").startswith("失败：alt_data agent")
    assert state.get("market_sentiment_votes")
    assert state.get("alt_data_votes")
    assert any(vote.agent == "market_sentiment" for vote in state.get("agent_votes", []))
    assert any(vote.agent == "alt_data" for vote in state.get("agent_votes", []))


def test_sentiment_and_alt_data_nodes_use_external_signals_when_available() -> None:
    bars = _bars()
    quote = _quote()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "DTWEXBGS" in url:
            return httpx.Response(
                200,
                text="observation_date,DTWEXBGS\n2026-05-23,98.1254\n2026-05-22,98.0345\n",
                request=request,
            )
        if "DFII10" in url:
            return httpx.Response(
                200,
                text="observation_date,DFII10\n2026-05-23,2.145\n2026-05-22,2.158\n",
                request=request,
            )
        if request.url.host == "publicreporting.cftc.gov":
            return httpx.Response(
                200,
                text=(
                    '"report_date_as_yyyy_mm_dd","commodity_name","open_interest_all",'
                    '"noncomm_positions_long_all","noncomm_positions_short_all",'
                    '"comm_positions_long_all","comm_positions_short_all"\n'
                    '"2026-05-19T00:00:00.000","GOLD","379325","211018","51185","69520","261149"\n'
                    '"2026-05-12T00:00:00.000","GOLD","378000","209000","53000","69000","260000"\n'
                ),
                request=request,
            )
        raise AssertionError(f"unexpected request url: {request.url}")

    state = WorkflowState(
        settings=GoldFXGraphSettings(openai_base_url=None, openai_model=None),
        latest_bar=bars[-1],
        quote=quote,
        indicators=compute_technical_indicators(bars),
        forecast_feedback_history=["上一轮看多后回撤偏大"],
        signal_http_transport=httpx.MockTransport(handler),
    )

    state = _merge_state(state, tool_fetch_market_sentiment_inputs(state))
    state = _merge_state(state, tool_fetch_alt_data_inputs(state))
    state = _merge_state(state, agent_market_sentiment_analysis(state))
    state = _merge_state(state, agent_alt_data_analysis(state))

    unavailable = state.get("unavailable_signals", [])
    assert "cftc_commitments" not in unavailable
    assert "positioning" in state["market_sentiment_inputs"]["available_signals"]
    assert state["market_sentiment_inputs"]["cftc_commitments"]["net_noncommercial"] == 159833
    assert state["market_sentiment_inputs"]["cftc_commitments"]["positioning_bias"] == "bullish"
    assert state["alt_data_inputs"]["dollar_index"]["status"] == "available"
    assert state["alt_data_inputs"]["real_rates"]["status"] == "available"
    assert state["alt_data_summary"].startswith("失败：alt_data agent")
    assert state["market_sentiment_summary"].startswith("失败：market_sentiment agent")


def test_polymarket_inputs_feed_market_sentiment_summary() -> None:
    bars = _bars()
    quote = _quote()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "polymarket.com":
            payload = json.dumps(
                {
                    "props": {
                        "pageProps": {
                            "markets": [
                                {
                                    "question": "Will gold price rise above $4500 by June?",
                                    "slug": "gold-4500",
                                    "yesPrice": 0.63,
                                    "liquidity": 120000,
                                    "volume": 300000,
                                    "endDate": "2026-06-30T00:00:00Z",
                                },
                                {
                                    "question": "Will the Fed cut rates in June?",
                                    "slug": "fed-cut",
                                    "yesPrice": 0.58,
                                    "liquidity": 90000,
                                    "volume": 200000,
                                    "endDate": "2026-06-30T00:00:00Z",
                                },
                                {
                                    "question": "Will the local baseball team win?",
                                    "slug": "sports",
                                    "yesPrice": 0.4,
                                },
                            ]
                        }
                    }
                },
                ensure_ascii=False,
            )
            return httpx.Response(
                200,
                text=(
                    "<!doctype html><html><head>"
                    "<script id='__NEXT_DATA__' type='application/json'>"
                    f"{payload}"
                    "</script></head><body></body></html>"
                ),
                request=request,
            )
        if request.url.host == "publicreporting.cftc.gov":
            return httpx.Response(
                200,
                text=(
                    '"report_date_as_yyyy_mm_dd","commodity_name","open_interest_all",'
                    '"noncomm_positions_long_all","noncomm_positions_short_all",'
                    '"comm_positions_long_all","comm_positions_short_all"\n'
                    '"2026-05-19T00:00:00.000","GOLD","379325","211018","51185","69520","261149"\n'
                    '"2026-05-12T00:00:00.000","GOLD","378000","209000","53000","69000","260000"\n'
                ),
                request=request,
            )
        raise AssertionError(f"unexpected request url: {request.url}")

    state = WorkflowState(
        settings=GoldFXGraphSettings(openai_base_url=None, openai_model=None),
        latest_bar=bars[-1],
        quote=quote,
        indicators=compute_technical_indicators(bars),
        forecast_feedback_history=["上一轮看多后回撤偏大"],
        signal_http_transport=httpx.MockTransport(handler),
        newsflow_inputs={
            "status": "available",
            "headline_count": 2,
            "source_count": 1,
            "sentiment": "bullish",
            "topics": ["Gold"],
        },
    )

    state = _merge_state(state, tool_fetch_polymarket_inputs(state))
    state = _merge_state(state, tool_fetch_market_sentiment_inputs(state))
    state = _merge_state(state, agent_market_sentiment_analysis(state))

    polymarket_inputs = state.get("polymarket_inputs")
    assert polymarket_inputs is not None
    assert polymarket_inputs["status"] == "available"
    assert polymarket_inputs["gold_related_market_count"] >= 2
    assert "polymarket" in state.get("market_sentiment_inputs", {}).get("available_signals", [])
    assert state.get("market_sentiment_summary", "").startswith("失败：market_sentiment agent")


def test_newsflow_node_uses_mainstream_media_rss_when_available() -> None:
    bars = _bars()
    quote = _quote()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "cnbc.com" in url:
            return httpx.Response(
                200,
                text=(
                    "<?xml version='1.0' encoding='UTF-8'?>"
                    "<rss version='2.0'><channel><title>CNBC</title>"
                    "<item><title>Gold edges higher as Fed cut bets firm</title>"
                    "<link>https://example.com/cnbc-1</link>"
                    "<pubDate>Mon, 20 May 2026 12:00:00 GMT</pubDate></item>"
                    "<item><title>Dollar slips on softer inflation data</title>"
                    "<link>https://example.com/cnbc-2</link>"
                    "<pubDate>Mon, 20 May 2026 13:00:00 GMT</pubDate></item>"
                    "</channel></rss>"
                ),
                request=request,
            )
        if "marketwatch.com" in url:
            return httpx.Response(
                200,
                text=(
                    "<?xml version='1.0' encoding='UTF-8'?>"
                    "<rss version='2.0'><channel><title>MarketWatch</title>"
                    "<item><title>Gold prices rebound as traders watch rates</title>"
                    "<link>https://example.com/mw-1</link>"
                    "<pubDate>Mon, 20 May 2026 14:00:00 GMT</pubDate></item>"
                    "</channel></rss>"
                ),
                request=request,
            )
        if "news.google.com" in url:
            return httpx.Response(
                200,
                text=(
                    "<?xml version='1.0' encoding='UTF-8'?>"
                    "<rss version='2.0'><channel><title>Google News</title>"
                    "<item><title>Reuters: Gold holds near record highs</title>"
                    "<link>https://example.com/gn-1</link>"
                    "<source>Reuters</source>"
                    "<pubDate>Mon, 20 May 2026 15:00:00 GMT</pubDate></item>"
                    "</channel></rss>"
                ),
                request=request,
            )
        raise AssertionError(f"unexpected request url: {request.url}")

    state = WorkflowState(
        settings=GoldFXGraphSettings(openai_base_url=None, openai_model=None),
        latest_bar=bars[-1],
        quote=quote,
        indicators=compute_technical_indicators(bars),
        signal_http_transport=httpx.MockTransport(handler),
    )

    state = _merge_state(state, tool_fetch_newsflow_inputs(state))
    state = _merge_state(state, agent_news_analysis(state))

    newsflow_inputs = state.get("newsflow_inputs")
    assert newsflow_inputs is not None
    assert newsflow_inputs["status"] == "available"
    assert newsflow_inputs["headline_count"] >= 3
    assert "newsflow" not in state.get("unavailable_signals", [])
    assert state.get("news_summary", "").startswith("失败：news agent")


def test_pizza_index_node_uses_public_dashboard_snapshot_when_available() -> None:
    bars = _bars()
    quote = _quote()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "pizzint.watch" in url:
            return httpx.Response(
                200,
                text=(
                    "<!doctype html><html><body>"
                    "<div class='text-4xl sm:text-5xl lg:text-6xl font-bold "
                    "text-yellow-400 leading-none -mb-1'>DOUGHCON 3</div>"
                    "<div class='text-xs sm:text-sm text-yellow-400 opacity-80 "
                    "leading-tight flex flex-wrap items-center gap-1'>"
                    "<span>ROUND HOUSE</span><span class='opacity-60'>•</span>"
                    "<span>INCREASE IN FORCE READINESS</span></div>"
                    "<div data-place-id='ChIJI6ACK7q2t4kRFcPtFhUuYhU'>"
                    "<h3>DOMINO&#x27;S PIZZA</h3>"
                    "<span class='text-red-300 font-bold'>178<!-- -->% SPIKE</span>"
                    "<div class='text-xs text-gray-400 font-mono'>1.4 mi</div></div>"
                    "<div data-place-id='ChIJcYireCe3t4kR4d9trEbGYjc'>"
                    "<h3>EXTREME PIZZA</h3>"
                    "<span class='text-red-300 font-bold'>270<!-- -->% SPIKE</span>"
                    "<div class='text-xs text-gray-400 font-mono'>1.0 mi</div></div>"
                    "</body></html>"
                ),
                request=request,
            )
        if "DTWEXBGS" in url:
            return httpx.Response(
                200,
                text="observation_date,DTWEXBGS\n2026-05-23,98.1254\n2026-05-22,98.0345\n",
                request=request,
            )
        if "DFII10" in url:
            return httpx.Response(
                200,
                text="observation_date,DFII10\n2026-05-23,2.145\n2026-05-22,2.158\n",
                request=request,
            )
        raise AssertionError(f"unexpected request url: {request.url}")

    state = WorkflowState(
        settings=GoldFXGraphSettings(openai_base_url=None, openai_model=None),
        latest_bar=bars[-1],
        quote=quote,
        indicators=compute_technical_indicators(bars),
        signal_http_transport=httpx.MockTransport(handler),
    )

    state = _merge_state(state, tool_fetch_pizza_index_inputs(state))
    state = _merge_state(state, tool_fetch_alt_data_inputs(state))
    state = _merge_state(state, agent_alt_data_analysis(state))

    pizza_index_inputs = state.get("pizza_index_inputs")
    assert pizza_index_inputs is not None
    assert pizza_index_inputs["status"] == "available"
    assert pizza_index_inputs["doughcon_level"] == 3
    assert pizza_index_inputs["source_count"] == 2
    assert pizza_index_inputs["top_locations"][0]["name"] == "EXTREME PIZZA"
    assert pizza_index_inputs["top_locations"][0]["spike_pct"] == 270
    assert "pizza_index" not in state.get("unavailable_signals", [])
    assert state.get("alt_data_summary", "").startswith("失败：alt_data agent")


def test_market_sentiment_agent_ignores_blank_remote_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    quote = _quote()
    state = WorkflowState(
        settings=GoldFXGraphSettings(
            openai_base_url="https://agent.example.test/v1",
            openai_model="gpt-4.1-mini",
            openai_api_key=SecretStr("secret-token"),
        ),
        latest_bar=bars[-1],
        quote=quote,
        indicators=compute_technical_indicators(bars),
        forecast_feedback_history=["上一轮看多后回撤偏大"],
    )

    monkeypatch.setattr(
        "goldfxgraph.llm.openai_client.OpenAIAgentClient.invoke_agent",
        lambda self, agent_name, payload: OpenAIAgentResult(
            summary="   ",
            direction=ForecastDirection.neutral,
            confidence=0.52,
            risk_notes=[],
        ),
    )

    state = _merge_state(state, tool_fetch_market_sentiment_inputs(state))
    state = _merge_state(state, agent_market_sentiment_analysis(state))

    assert state.get("market_sentiment_summary", "").startswith("失败：market_sentiment agent")
    assert state["market_sentiment_votes"][0].confidence == 0.0
    assert state["agent_diagnostics"][0]["status"] == "invalid_response"


def test_forecast_planning_carries_remote_agent_failure_diagnostics_into_risk_notes() -> None:
    bars = _bars()
    indicators = compute_technical_indicators(bars)
    quote = _quote()
    state = WorkflowState(
        latest_bar=bars[-1],
        quote=quote,
        indicators=indicators,
        technical_summary="当前报价 2040.00，最新完成日线收盘 2032.00，结构化方向为看多。",
        agent_votes=[
            AgentVote(
                agent="technical",
                direction=ForecastDirection.bullish,
                confidence=0.73,
                rationale="技术面回退输出",
            ),
            AgentVote(agent="macro", direction=ForecastDirection.neutral, confidence=0.35, rationale="宏观中性"),
        ],
        risk_notes=[
            "已有风险提示",
            "OpenAI-compatible technical agent 调用失败，已标记为失败，不生成兜底输出。",
        ],
    )

    planned = agent_forecast_planning(state)
    forecast = planned.get("forecast")

    assert forecast is not None
    assert "已有风险提示" in forecast.risk_notes
    assert "OpenAI-compatible technical agent 调用失败，已标记为失败，不生成兜底输出。" in forecast.risk_notes


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

    state = _merge_state(state, await tool_persist_research_run(state))
    state = _merge_state(state, await tool_persist_forecast(state))
    run_id = state.get("run_id")
    assert run_id is not None
    loaded = await repo.get_research_run(run_id)

    assert loaded is not None
    assert loaded.status == "success"
    assert loaded.forecast is not None
    assert loaded.forecast.direction == forecast.direction
    await session_factory.engine.dispose()


@pytest.mark.asyncio
async def test_node_persist_forecast_falls_back_to_current_research_forecast() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    repo = ForecastRepository(session_factory)
    bars = _bars()
    state = WorkflowState(
        repository=repo,
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=compute_technical_indicators(bars),
    )

    state = _merge_state(state, await node_persist_forecast(state))
    run_id = state.get("run_id")
    forecast = state.get("forecast")

    assert run_id is not None
    assert forecast is not None
    assert state.get("persistence_status") == "forecast_saved"
    loaded = await repo.get_research_run(run_id)
    assert loaded is not None
    assert loaded.forecast is not None
    assert loaded.forecast.direction == forecast.direction
    await session_factory.engine.dispose()


def test_node_build_evidence_package_aggregates_specialist_outputs() -> None:
    bars = _bars()
    indicators = compute_technical_indicators(bars)
    state = WorkflowState(
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=indicators,
        technical_summary="技术分析摘要",
        macro_summary="宏观分析摘要",
        news_summary="新闻分析摘要",
        market_sentiment_summary="市场情绪摘要",
        alt_data_summary="另类数据摘要",
        risk_summary="风险分析摘要",
        risk_notes=["波动区间扩大", "RSI 处于中性区域"],
        agent_votes=[
            AgentVote(agent="technical", direction=ForecastDirection.bullish, confidence=0.72, rationale="技术看多"),
            AgentVote(agent="macro", direction=ForecastDirection.neutral, confidence=0.34, rationale="宏观中性"),
            AgentVote(agent="news", direction=ForecastDirection.neutral, confidence=0.31, rationale="新闻中性"),
            AgentVote(
                agent="market_sentiment",
                direction=ForecastDirection.bearish,
                confidence=0.41,
                rationale="情绪偏空",
            ),
            AgentVote(agent="alt_data", direction=ForecastDirection.neutral, confidence=0.29, rationale="另类数据中性"),
            AgentVote(agent="risk", direction=ForecastDirection.neutral, confidence=0.55, rationale="风险中性"),
        ],
        macro_inputs={
            "dollar_index": {"status": "available", "value": 104.12, "summary": "美元指数偏强"},
            "real_rates": {"status": "available", "value": 2.31, "summary": "实际利率温和"},
            "available_signals": ["dollar_index", "real_rates"],
            "unavailable_signals": [],
        },
        newsflow_inputs={
            "status": "available",
            "summary": "新闻流保持中性。",
            "headline_count": 2,
            "source_count": 1,
            "sentiment": "neutral",
            "top_headlines": [
                {
                    "title_cn": "黄金维持震荡",
                    "source_cn": "Reuters",
                }
            ],
        },
        market_sentiment_inputs={
            "feedback_history": ["上一轮多头延续失败"],
            "feedback_signal_count": 1,
            "cftc_commitments": {"status": "available", "summary": "CFTC 持仓平衡"},
            "polymarket_summary": "市场预期偏中性。",
            "polymarket_bullish_count": 1,
            "polymarket_bearish_count": 1,
            "available_signals": ["cftc_commitments", "polymarket"],
            "unavailable_signals": [],
        },
        alt_data_inputs={
            "pizza_index": {"status": "available", "summary": "Pizza Index 正常"},
            "dollar_index": {"status": "available", "summary": "美元指数稳定"},
            "real_rates": {"status": "available", "summary": "实际利率稳定"},
            "price_context": {
                "current_price": 2040.0,
                "latest_close": 2038.0,
            },
            "available_signals": ["pizza_index", "dollar_index", "real_rates"],
            "unavailable_signals": [],
        },
    )

    result = node_build_evidence_package(state)
    package = result.get("evidence_package")

    assert package is not None
    assert package.symbol == "XAUUSD"
    assert len(package.items) == 6
    assert {item.specialist_name for item in package.items} == {
        "technical",
        "macro",
        "news",
        "market_sentiment",
        "alt_data",
        "risk",
    }
    assert package.items[0].tool_status == "ok"
    assert "仅汇总 specialist analyses" in (package.summary or "")


@pytest.mark.asyncio
async def test_committee_agent_chain_builds_prompts_and_final_forecast() -> None:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    await seed_default_committee_prompt_templates(session_factory)
    repo = ForecastRepository(session_factory)
    bars = _bars()
    indicators = compute_technical_indicators(bars)
    state = WorkflowState(
        repository=repo,
        latest_bar=bars[-1],
        quote=_quote(),
        indicators=indicators,
        technical_summary="技术分析摘要",
        macro_summary="宏观分析摘要",
        news_summary="新闻分析摘要",
        market_sentiment_summary="市场情绪摘要",
        alt_data_summary="另类数据摘要",
        risk_summary="风险分析摘要",
        risk_notes=["波动区间扩大", "RSI 处于中性区域"],
        agent_votes=[
            AgentVote(agent="technical", direction=ForecastDirection.bullish, confidence=0.72, rationale="技术看多"),
            AgentVote(agent="macro", direction=ForecastDirection.neutral, confidence=0.34, rationale="宏观中性"),
            AgentVote(agent="news", direction=ForecastDirection.neutral, confidence=0.31, rationale="新闻中性"),
            AgentVote(
                agent="market_sentiment",
                direction=ForecastDirection.bearish,
                confidence=0.41,
                rationale="情绪偏空",
            ),
            AgentVote(agent="alt_data", direction=ForecastDirection.neutral, confidence=0.29, rationale="另类数据中性"),
            AgentVote(agent="risk", direction=ForecastDirection.neutral, confidence=0.55, rationale="风险中性"),
        ],
        macro_inputs={
            "dollar_index": {"status": "available", "value": 104.12, "summary": "美元指数偏强"},
            "real_rates": {"status": "available", "value": 2.31, "summary": "实际利率温和"},
            "available_signals": ["dollar_index", "real_rates"],
            "unavailable_signals": [],
        },
        newsflow_inputs={
            "status": "available",
            "summary": "新闻流保持中性。",
            "headline_count": 2,
            "source_count": 1,
            "sentiment": "neutral",
            "top_headlines": [
                {
                    "title_cn": "黄金维持震荡",
                    "source_cn": "Reuters",
                }
            ],
        },
        market_sentiment_inputs={
            "feedback_history": ["上一轮多头延续失败"],
            "feedback_signal_count": 1,
            "cftc_commitments": {"status": "available", "summary": "CFTC 持仓平衡"},
            "polymarket_summary": "市场预期偏中性。",
            "polymarket_bullish_count": 1,
            "polymarket_bearish_count": 1,
            "available_signals": ["cftc_commitments", "polymarket"],
            "unavailable_signals": [],
        },
        alt_data_inputs={
            "pizza_index": {"status": "available", "summary": "Pizza Index 正常"},
            "dollar_index": {"status": "available", "summary": "美元指数稳定"},
            "real_rates": {"status": "available", "summary": "实际利率稳定"},
            "price_context": {
                "current_price": 2040.0,
                "latest_close": 2038.0,
            },
            "available_signals": ["pizza_index", "dollar_index", "real_rates"],
            "unavailable_signals": [],
        },
    )

    state = _merge_state(state, node_build_evidence_package(state))
    state = _merge_state(state, await agent_bull_opening_case(state))
    state = _merge_state(state, await agent_bear_opening_case(state))
    state = _merge_state(state, await agent_bull_rebuttal(state))
    state = _merge_state(state, await agent_bear_rebuttal(state))
    state = _merge_state(state, await agent_bull_final_position(state))
    state = _merge_state(state, await agent_bear_final_position(state))
    state = _merge_state(state, await agent_trading_committee_chair(state))
    state = _merge_state(state, await agent_repair_committee_decision(state))
    state = _merge_state(state, await node_persist_forecast(state))

    committee_decision = state.get("committee_decision")
    final_forecast = state.get("final_forecast")
    prompt_versions = state.get("prompt_versions") or []

    assert committee_decision is not None
    assert committee_decision.final_bias in {"bullish", "bearish", "range_bound", "cautious"}
    assert committee_decision.actionability in {
        "trade_candidate",
        "prepare_only",
        "observe_only",
        "no_trade",
    }
    assert final_forecast is not None
    assert final_forecast.final_bias == committee_decision.final_bias
    assert len(prompt_versions) >= 14
    assert state.get("persistence_status") == "forecast_saved"
    await session_factory.engine.dispose()


@pytest.mark.parametrize(
    ("case_name", "state_kwargs", "expected_error"),
    [
        (
            "bullish_requires_long_plan",
            {"final_bias": FinalBias.bullish, "actionability": Actionability.prepare_only, "include_long_plan": False},
            "bullish decisions require long_plan",
        ),
        (
            "bearish_requires_short_plan",
            {
                "final_bias": FinalBias.bearish,
                "actionability": Actionability.prepare_only,
                "include_long_plan": False,
                "include_short_plan": False,
            },
            "bearish decisions require short_plan",
        ),
        (
            "range_bound_requires_range_plan",
            {
                "final_bias": FinalBias.range_bound,
                "actionability": Actionability.observe_only,
                "include_long_plan": False,
                "include_range_plan": False,
            },
            "range_bound decisions require range_plan",
        ),
        (
            "cautious_requires_wait_conditions",
            {
                "final_bias": FinalBias.cautious,
                "actionability": Actionability.no_trade,
                "include_long_plan": False,
                "wait_conditions": [],
            },
            "cautious decisions require wait_conditions",
        ),
        (
            "trade_candidate_needs_minimum_confidence",
            {
                "final_bias": FinalBias.bullish,
                "actionability": Actionability.trade_candidate,
                "confidence_score": 0.5,
            },
            "trade_candidate confidence should be at least 0.55",
        ),
        (
            "degraded_sources_require_conservative_confidence",
            {
                "final_bias": FinalBias.bullish,
                "actionability": Actionability.trade_candidate,
                "confidence_score": 0.86,
                "evidence_tool_status": EvidenceToolStatus.degraded,
            },
            "evidence package contains degraded sources, confidence should stay conservative",
        ),
    ],
)
def test_node_validate_committee_decision_enforces_core_rules(
    case_name: str,
    state_kwargs: dict[str, object],
    expected_error: str,
) -> None:
    state = _committee_validation_state(**state_kwargs)

    result = node_validate_committee_decision(state)
    validation_status = result.get("validation_status")

    assert isinstance(validation_status, DecisionValidationResult), case_name
    assert validation_status.is_valid is False, case_name
    assert expected_error in validation_status.errors, case_name
    assert result.get("committee_validation_attempts") == 1, case_name
    assert _route_committee_validation(result) == "repair", case_name


def test_node_validate_committee_decision_accepts_valid_trade_candidate() -> None:
    state = _committee_validation_state()

    result = node_validate_committee_decision(state)
    validation_status = result.get("validation_status")

    assert isinstance(validation_status, DecisionValidationResult)
    assert validation_status.is_valid is True
    assert validation_status.errors == []
    assert _route_committee_validation(result) == "persist"


def test_committee_validation_routes_to_repair_until_attempt_limit() -> None:
    state = _committee_validation_state(include_long_plan=False)
    first_pass = node_validate_committee_decision(state)

    assert _route_committee_validation(first_pass) == "repair"
    assert _route_committee_validation({**first_pass, "committee_validation_attempts": 2}) == "repair"
    assert _route_committee_validation({**first_pass, "committee_validation_attempts": 3}) == "persist"
