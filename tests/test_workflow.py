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
from goldfxgraph.schemas.forecast import AgentVote, CurrentQuote, DailyBar, ForecastDirection
from goldfxgraph.workflow.graph import REQUIRED_NODE_NAMES, build_forecast_graph
from goldfxgraph.workflow.nodes import (
    MarketDataFreshnessError,
    WorkflowState,
    agent_alt_data_analysis,
    agent_forecast_planning,
    agent_macro_analysis,
    agent_market_sentiment_analysis,
    agent_news_analysis,
    agent_technical_analysis,
    create_research_forecast_from_inputs,
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

    assert result is state
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

    state = agent_macro_analysis(state)

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

    state = tool_fetch_macro_inputs(state)
    state = agent_macro_analysis(state)

    assert state.get("unavailable_signals", []) == []
    assert "美元指数 104.32" in state.get("macro_summary", "")
    assert "实际利率 2.45%" in state.get("macro_summary", "")
    assert state.get("macro_summary", "").startswith("宏观面围绕美元指数与实际利率解读")


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

    state = agent_technical_analysis(state)

    assert called is False
    assert state.get("technical_summary", "").startswith("当前报价")
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

    state = agent_forecast_planning(state)
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
    state = agent_technical_analysis(state)

    assert state.get("technical_summary", "").startswith("当前报价")
    agent_votes = state.get("agent_votes")
    assert agent_votes is not None
    assert agent_votes[0].agent == "technical"
    assert agent_votes[0].direction == ForecastDirection.bullish
    assert state.get("agent_diagnostics") is not None
    assert state["agent_diagnostics"][0]["agent"] == "technical"
    assert state["agent_diagnostics"][0]["message"] == (
        "OpenAI-compatible technical agent 调用失败，已回退到 deterministic workflow 输出。"
    )
    assert "OpenAI-compatible response returned invalid JSON for technical" in caplog.text
    assert state["agent_diagnostics"][0]["detail"] == "OpenAI-compatible response returned invalid JSON for technical"


def test_sentiment_and_alt_data_nodes_fallback_to_structured_summaries_without_openai() -> None:
    bars = _bars()
    quote = _quote()
    state = WorkflowState(
        settings=GoldFXGraphSettings(openai_base_url=None, openai_model=None),
        latest_bar=bars[-1],
        quote=quote,
        indicators=compute_technical_indicators(bars),
        forecast_feedback_history=["上一轮看多后回撤偏大"],
    )

    state = tool_fetch_market_sentiment_inputs(state)
    state = tool_fetch_alt_data_inputs(state)
    state = agent_market_sentiment_analysis(state)
    state = agent_alt_data_analysis(state)

    assert state.get("market_sentiment_summary", "").startswith("市场情绪按")
    assert "披萨指数" in state.get("alt_data_summary", "")
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

    state = tool_fetch_market_sentiment_inputs(state)
    state = tool_fetch_alt_data_inputs(state)
    state = agent_market_sentiment_analysis(state)
    state = agent_alt_data_analysis(state)

    unavailable = state.get("unavailable_signals", [])
    assert "cftc_commitments" not in unavailable
    assert "positioning" in state["market_sentiment_inputs"]["available_signals"]
    assert state["market_sentiment_inputs"]["cftc_commitments"]["net_noncommercial"] == 159833
    assert state["market_sentiment_inputs"]["cftc_commitments"]["positioning_bias"] == "bullish"
    assert state["alt_data_inputs"]["dollar_index"]["status"] == "available"
    assert state["alt_data_inputs"]["real_rates"]["status"] == "available"
    assert "美元指数" in state["alt_data_summary"]
    assert "实际利率" in state["alt_data_summary"]
    assert "CFTC" in state["market_sentiment_summary"] or "净多头" in state["market_sentiment_summary"]


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

    state = tool_fetch_polymarket_inputs(state)
    state = tool_fetch_market_sentiment_inputs(state)
    state = agent_market_sentiment_analysis(state)

    polymarket_inputs = state.get("polymarket_inputs")
    assert polymarket_inputs is not None
    assert polymarket_inputs["status"] == "available"
    assert polymarket_inputs["gold_related_market_count"] >= 2
    assert "polymarket" in state.get("market_sentiment_inputs", {}).get("available_signals", [])
    assert "Polymarket" in state.get("market_sentiment_summary", "")
    assert "黄金" in state.get("market_sentiment_summary", "")


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

    state = tool_fetch_newsflow_inputs(state)
    state = agent_news_analysis(state)

    newsflow_inputs = state.get("newsflow_inputs")
    assert newsflow_inputs is not None
    assert newsflow_inputs["status"] == "available"
    assert newsflow_inputs["headline_count"] >= 3
    assert "newsflow" not in state.get("unavailable_signals", [])
    assert "新闻流已从" in state.get("news_summary", "")
    assert "美联储" in state.get("news_summary", "")
    assert "黄金" in state.get("news_summary", "")
    assert "Gold edges higher" not in state.get("news_summary", "")


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

    state = tool_fetch_pizza_index_inputs(state)
    state = tool_fetch_alt_data_inputs(state)
    state = agent_alt_data_analysis(state)

    pizza_index_inputs = state.get("pizza_index_inputs")
    assert pizza_index_inputs is not None
    assert pizza_index_inputs["status"] == "available"
    assert pizza_index_inputs["doughcon_level"] == 3
    assert pizza_index_inputs["source_count"] == 2
    assert pizza_index_inputs["top_locations"][0]["name"] == "EXTREME PIZZA"
    assert pizza_index_inputs["top_locations"][0]["spike_pct"] == 270
    assert "pizza_index" not in state.get("unavailable_signals", [])
    assert "五角大楼披萨指数" in state.get("alt_data_summary", "")
    assert state.get("alt_data_summary", "").splitlines()[0] == "另类数据维度以保守处理为主。"


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

    state = tool_fetch_market_sentiment_inputs(state)
    state = agent_market_sentiment_analysis(state)

    assert state.get("market_sentiment_summary", "").startswith("市场情绪按")
    assert state["market_sentiment_summary"].strip() != ""


def test_forecast_planning_carries_remote_agent_fallback_diagnostics_into_risk_notes() -> None:
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
            "OpenAI-compatible technical agent 调用失败，已回退到 deterministic workflow 输出。",
        ],
    )

    planned = agent_forecast_planning(state)
    forecast = planned.get("forecast")

    assert forecast is not None
    assert "已有风险提示" in forecast.risk_notes
    assert "OpenAI-compatible technical agent 调用失败，已回退到 deterministic workflow 输出。" in forecast.risk_notes


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
