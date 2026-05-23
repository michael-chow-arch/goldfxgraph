from __future__ import annotations

from langgraph.graph import END, StateGraph

from goldfxgraph.workflow.nodes import (
    WorkflowState,
    agent_forecast_planning,
    agent_macro_analysis,
    agent_news_analysis,
    agent_risk_analysis,
    agent_technical_analysis,
    router_finalize_result,
    router_validate_request,
    tool_compute_indicators,
    tool_fetch_current_gold_quote,
    tool_load_market_data,
    tool_persist_forecast,
    tool_persist_research_run,
)

REQUIRED_NODE_NAMES = (
    "router_validate_request",
    "tool_load_market_data",
    "tool_fetch_current_gold_quote",
    "tool_compute_indicators",
    "agent_technical_analysis",
    "agent_macro_analysis",
    "agent_news_analysis",
    "agent_risk_analysis",
    "agent_forecast_planning",
    "tool_persist_research_run",
    "tool_persist_forecast",
    "router_finalize_result",
)


def build_forecast_graph() -> StateGraph[WorkflowState]:
    graph = StateGraph(WorkflowState)
    graph.add_node("router_validate_request", router_validate_request)
    graph.add_node("tool_load_market_data", tool_load_market_data)
    graph.add_node("tool_fetch_current_gold_quote", tool_fetch_current_gold_quote)
    graph.add_node("tool_compute_indicators", tool_compute_indicators)
    graph.add_node("agent_technical_analysis", agent_technical_analysis)
    graph.add_node("agent_macro_analysis", agent_macro_analysis)
    graph.add_node("agent_news_analysis", agent_news_analysis)
    graph.add_node("agent_risk_analysis", agent_risk_analysis)
    graph.add_node("agent_forecast_planning", agent_forecast_planning)
    graph.add_node("tool_persist_research_run", tool_persist_research_run)
    graph.add_node("tool_persist_forecast", tool_persist_forecast)
    graph.add_node("router_finalize_result", router_finalize_result)

    graph.set_entry_point("router_validate_request")
    graph.add_edge("router_validate_request", "tool_load_market_data")
    graph.add_edge("tool_load_market_data", "tool_fetch_current_gold_quote")
    graph.add_edge("tool_fetch_current_gold_quote", "tool_compute_indicators")
    graph.add_edge("tool_compute_indicators", "agent_technical_analysis")
    graph.add_edge("agent_technical_analysis", "agent_macro_analysis")
    graph.add_edge("agent_macro_analysis", "agent_news_analysis")
    graph.add_edge("agent_news_analysis", "agent_risk_analysis")
    graph.add_edge("agent_risk_analysis", "agent_forecast_planning")
    graph.add_edge("agent_forecast_planning", "tool_persist_research_run")
    graph.add_edge("tool_persist_research_run", "tool_persist_forecast")
    graph.add_edge("tool_persist_forecast", "router_finalize_result")
    graph.add_edge("router_finalize_result", END)
    return graph
