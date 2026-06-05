from __future__ import annotations

from typing import Any, cast

import httpx

from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.workflow.graph import build_forecast_graph
from goldfxgraph.workflow.nodes import WorkflowState


async def run_forecast_workflow(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    run_id: int,
    scheduler_run_id: int | None = None,
    agent_http_transport: httpx.BaseTransport | None = None,
    signal_http_transport: httpx.BaseTransport | None = None,
    quote_provider: Any | None = None,
) -> WorkflowState:
    state = WorkflowState(
        settings=settings,
        repository=repository,
        run_id=run_id,
    )
    if scheduler_run_id is not None:
        state["scheduler_run_id"] = scheduler_run_id
    if agent_http_transport is not None:
        state["agent_http_transport"] = agent_http_transport
    if signal_http_transport is not None:
        state["signal_http_transport"] = signal_http_transport
    if quote_provider is not None:
        state["quote_provider"] = quote_provider
    graph = build_forecast_graph().compile()
    result = await graph.ainvoke(state)
    return cast(WorkflowState, result)
