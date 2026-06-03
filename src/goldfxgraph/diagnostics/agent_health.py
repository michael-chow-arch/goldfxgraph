from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

from goldfxgraph.llm.openai_client import OpenAIAgentClient, OpenAIClientError
from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.packages.common.settings import GoldFXGraphSettings, get_settings
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.workflow.nodes import (
    WorkflowState,
    _agent_payload,
    tool_compute_indicators,
    tool_fetch_alt_data_inputs,
    tool_fetch_current_gold_quote,
    tool_fetch_macro_inputs,
    tool_fetch_market_sentiment_inputs,
    tool_fetch_newsflow_inputs,
    tool_fetch_pizza_index_inputs,
    tool_load_forecast_feedback_history,
    tool_load_market_data,
)

AGENT_HEALTH_PROBE_NAMES = (
    "technical",
    "macro",
    "news",
    "market_sentiment",
    "alt_data",
    "risk",
)


def _merge_state(state: WorkflowState, delta: dict[str, object]) -> WorkflowState:
    merged = dict(state)
    merged.update(delta)
    return merged


@dataclass(slots=True)
class AgentHealthProbeResult:
    agent: str
    ok: bool
    summary: str | None = None
    direction: str | None = None
    confidence: float | None = None
    error: str | None = None


@dataclass(slots=True)
class AgentHealthCheckReport:
    checked_at: datetime
    latest_bar_date: date
    latest_bar_source: str | None
    quote_source: str
    quote_warning: str | None
    probes: list[AgentHealthProbeResult]

    @property
    def all_ok(self) -> bool:
        return all(probe.ok for probe in self.probes)


async def run_agent_health_check(
    *,
    settings: GoldFXGraphSettings | None = None,
    repository: ForecastRepository,
    agent_http_transport: httpx.BaseTransport | None = None,
    signal_http_transport: httpx.BaseTransport | None = None,
) -> AgentHealthCheckReport:
    resolved_settings = settings or get_settings()
    state = await _build_probe_state(
        settings=resolved_settings,
        repository=repository,
        signal_http_transport=signal_http_transport,
    )
    probes = await _probe_agents(
        settings=resolved_settings,
        state=state,
        agent_http_transport=agent_http_transport,
    )

    latest_bar = state["latest_bar"]
    quote = state.get("quote")
    quote_warning = state.get("quote_warning")
    return AgentHealthCheckReport(
        checked_at=datetime.now(UTC),
        latest_bar_date=latest_bar.date,
        latest_bar_source=latest_bar.source,
        quote_source=quote.data_source if quote is not None else "unavailable",
        quote_warning=quote_warning,
        probes=probes,
    )


def format_agent_health_check_report(report: AgentHealthCheckReport) -> str:
    lines = [
        "agent health check:",
        f"- checked_at: {report.checked_at.isoformat()}",
        f"- latest_bar_date: {report.latest_bar_date.isoformat()}",
        f"- latest_bar_source: {report.latest_bar_source or '-'}",
        f"- quote_source: {report.quote_source}",
    ]
    if report.quote_warning:
        lines.append(f"- quote_warning: {report.quote_warning}")
    for probe in report.probes:
        status = "ok" if probe.ok else "fail"
        parts = [f"- {probe.agent}: {status}"]
        if probe.direction:
            parts.append(f"direction={probe.direction}")
        if probe.confidence is not None:
            parts.append(f"confidence={probe.confidence:.2f}")
        if probe.error:
            parts.append(f"error={probe.error}")
        lines.append(" ".join(parts))
    lines.append(f"- all_ok: {report.all_ok}")
    return "\n".join(lines)


async def _build_probe_state(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    signal_http_transport: httpx.BaseTransport | None,
) -> WorkflowState:
    state = WorkflowState(settings=settings, repository=repository, signal_http_transport=signal_http_transport)
    state = _merge_state(state, await tool_load_market_data(state))
    state = _merge_state(state, tool_compute_indicators(state))
    quote_warning = None
    try:
        state = _merge_state(state, tool_fetch_current_gold_quote(state))
    except QuoteProviderError as exc:
        quote_warning = str(exc).strip() or "Current quote provider failed"
        state = {**state, "quote_warning": quote_warning}
    else:
        state = _merge_state(state, tool_fetch_macro_inputs(state))
        state = _merge_state(state, tool_fetch_newsflow_inputs(state))
        state = _merge_state(state, tool_fetch_pizza_index_inputs(state))
        state = _merge_state(state, await tool_load_forecast_feedback_history(state))
        state = _merge_state(state, tool_fetch_market_sentiment_inputs(state))
        state = _merge_state(state, tool_fetch_alt_data_inputs(state))
    if quote_warning:
        state["quote_warning"] = quote_warning
    return state


async def _probe_agents(
    *,
    settings: GoldFXGraphSettings,
    state: WorkflowState,
    agent_http_transport: httpx.BaseTransport | None,
) -> list[AgentHealthProbeResult]:
    if state.get("quote") is None:
        error = state.get("quote_warning") or "TradingView quote unavailable"
        return [
            AgentHealthProbeResult(agent=agent, ok=False, error=f"{error}; quote unavailable")
            for agent in AGENT_HEALTH_PROBE_NAMES
        ]

    if not settings.openai_base_url or not settings.openai_model or not settings.openai_api_key:
        error = "未配置有效 base_url/model/API Key"
        return [AgentHealthProbeResult(agent=agent, ok=False, error=error) for agent in AGENT_HEALTH_PROBE_NAMES]

    client = OpenAIAgentClient(
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        api_key=settings.openai_api_key.get_secret_value(),
        transport=agent_http_transport,
    )
    probes: list[AgentHealthProbeResult] = []
    for agent in AGENT_HEALTH_PROBE_NAMES:
        try:
            result = client.invoke_agent(agent, _agent_payload(state, agent))
        except OpenAIClientError as exc:
            probes.append(AgentHealthProbeResult(agent=agent, ok=False, error=str(exc).strip() or "agent call failed"))
            continue

        probes.append(
            AgentHealthProbeResult(
                agent=agent,
                ok=True,
                summary=result.summary,
                direction=result.direction.value,
                confidence=result.confidence,
            )
        )

    return probes
