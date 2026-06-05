from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import SecretStr

from goldfxgraph.diagnostics.agent_health import run_agent_health_check
from goldfxgraph.llm.openai_client import OpenAIAgentClient, OpenAIAgentResult, OpenAIClientError
from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import CurrentQuote, DailyBar, ForecastDirection
from goldfxgraph.workflow import nodes
from conftest import seed_runtime_registry


async def _repository() -> tuple[ForecastRepository, object]:
    session_factory = create_session_factory("sqlite+aiosqlite:///:memory:")
    await init_models(session_factory.engine)
    await seed_runtime_registry(session_factory)
    repository = ForecastRepository(session_factory)
    await repository.upsert_market_bars(
        [
            DailyBar(
                date=date(2024, 1, 8),
                open=2050,
                high=2065,
                low=2042,
                close=2058,
                source="unit-feed",
                symbol="XAUUSD",
            )
        ]
    )
    return repository, session_factory


def _settings() -> GoldFXGraphSettings:
    return GoldFXGraphSettings(
        openai_base_url="https://api.zhizengzeng.com/v1",
        openai_model="gpt-5.1",
        openai_api_key=SecretStr("real-key"),
    )


def _patch_real_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        nodes.TradingViewQuoteProvider,
        "fetch",
        lambda self: CurrentQuote(
            symbol="XAUUSD",
            current_price=2060.0,
            data_source="TradingView",
            data_timestamp=datetime.now(UTC),
        ),
    )
    monkeypatch.setattr(
        nodes,
        "_fetch_dollar_index",
        lambda source, transport: (
            {
                "status": "available",
                "source": "fred",
                "value": 103.21,
                "change": -0.15,
            },
            None,
        ),
    )
    monkeypatch.setattr(
        nodes,
        "_fetch_real_rates",
        lambda source, transport: (
            {
                "status": "available",
                "source": "fred",
                "value": 2.48,
                "change": -0.03,
            },
            None,
        ),
    )
    monkeypatch.setattr(
        nodes,
        "_fetch_cftc_commitments",
        lambda source, transport: (
            {
                "status": "available",
                "report_date": "2024-01-08",
                "net_noncommercial": 12345,
                "positioning_bias": "bullish",
            },
            None,
        ),
    )
    monkeypatch.setattr(
        nodes,
        "fetch_newsflow",
        lambda sources, transport: {
            "status": "available",
            "source": "mainstream-rss",
            "headline_count": 3,
            "source_count": 2,
            "headlines": [],
            "top_headlines": [
                {"source": "CNBC", "title": "Gold steady ahead of Fed decision"},
                {"source": "FT", "title": "Dollar eases as yields cool"},
            ],
            "sentiment": "neutral",
            "sentiment_score": 0,
            "topics": ["Fed", "Gold"],
            "summary": "news ok",
            "feed_statuses": [],
        },
    )
    monkeypatch.setattr(
        nodes,
        "fetch_pizza_index",
        lambda source, transport: {
            "status": "available",
            "source": "pizzint.watch",
            "doughcon_level": 3,
            "doughcon_label": "elevated",
            "doughcon_description": "elevated activity",
            "source_count": 2,
            "average_spike_pct": 16.0,
            "max_spike_pct": 33.0,
            "pizza_index_score": 61,
            "activity_bias": "neutral",
            "top_locations": [],
            "summary": "pizza ok",
        },
    )


@pytest.mark.asyncio
async def test_agent_health_check_reports_all_agents_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    repository, session_factory = await _repository()
    _patch_real_inputs(monkeypatch)

    def fake_invoke(
        self: OpenAIAgentClient,
        *,
        agent_name: str,
        messages: list[dict[str, str]],
        output_model: type[OpenAIAgentResult],
    ) -> OpenAIAgentResult:
        return OpenAIAgentResult(
            summary=f"{agent_name} ok",
            direction=ForecastDirection.neutral,
            confidence=0.88,
            risk_notes=[],
        )

    monkeypatch.setattr(OpenAIAgentClient, "invoke_messages", fake_invoke)

    try:
        report = await run_agent_health_check(settings=_settings(), repository=repository)
    finally:
        await session_factory.engine.dispose()

    assert report.all_ok is True
    assert report.quote_source == "TradingView"
    assert {probe.agent for probe in report.probes} == {
        "technical",
        "macro",
        "news",
        "market_sentiment",
        "alt_data",
        "risk",
    }
    assert all(probe.ok for probe in report.probes)


@pytest.mark.asyncio
async def test_agent_health_check_reports_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    repository, session_factory = await _repository()
    _patch_real_inputs(monkeypatch)

    def fake_invoke(
        self: OpenAIAgentClient,
        *,
        agent_name: str,
        messages: list[dict[str, str]],
        output_model: type[OpenAIAgentResult],
    ) -> OpenAIAgentResult:
        if agent_name == "news":
            raise OpenAIClientError("news failed")
        return OpenAIAgentResult(
            summary=f"{agent_name} ok",
            direction=ForecastDirection.neutral,
            confidence=0.75,
            risk_notes=[],
        )

    monkeypatch.setattr(OpenAIAgentClient, "invoke_messages", fake_invoke)

    try:
        report = await run_agent_health_check(settings=_settings(), repository=repository)
    finally:
        await session_factory.engine.dispose()

    assert report.all_ok is False
    failed_agents = {probe.agent for probe in report.probes if not probe.ok}
    assert failed_agents == {"news"}
    assert any("news failed" in (probe.error or "") for probe in report.probes)


@pytest.mark.asyncio
async def test_agent_health_check_marks_quote_unavailable_when_tradingview_quote_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, session_factory = await _repository()
    _patch_real_inputs(monkeypatch)

    monkeypatch.setattr(
        nodes.TradingViewQuoteProvider,
        "fetch",
        lambda self: (_ for _ in ()).throw(QuoteProviderError("TradingView quote request failed")),
    )

    def fake_invoke(
        self: OpenAIAgentClient,
        *,
        agent_name: str,
        messages: list[dict[str, str]],
        output_model: type[OpenAIAgentResult],
    ) -> OpenAIAgentResult:
        return OpenAIAgentResult(
            summary=f"{agent_name} ok",
            direction=ForecastDirection.neutral,
            confidence=0.88,
            risk_notes=[],
        )

    monkeypatch.setattr(OpenAIAgentClient, "invoke_messages", fake_invoke)

    try:
        report = await run_agent_health_check(settings=_settings(), repository=repository)
    finally:
        await session_factory.engine.dispose()

    assert report.quote_source == "unavailable"
    assert report.quote_warning == "TradingView quote request failed"
    assert all(not probe.ok for probe in report.probes)
    assert all("quote unavailable" in (probe.error or "") for probe in report.probes)
