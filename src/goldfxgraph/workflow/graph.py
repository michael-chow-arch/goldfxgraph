from __future__ import annotations

from langgraph.graph import END, StateGraph

from goldfxgraph.workflow.nodes import (
    WorkflowState,
    agent_alt_data_analysis,
    agent_forecast_planning,
    agent_macro_analysis,
    agent_market_sentiment_analysis,
    agent_news_analysis,
    agent_risk_analysis,
    agent_technical_analysis,
    router_finalize_result,
    router_validate_request,
    tool_compute_indicators,
    tool_ensure_market_data_freshness,
    tool_fetch_alt_data_inputs,
    tool_fetch_current_gold_quote,
    tool_fetch_macro_inputs,
    tool_fetch_market_sentiment_inputs,
    tool_fetch_newsflow_inputs,
    tool_fetch_pizza_index_inputs,
    tool_load_forecast_feedback_history,
    tool_load_market_data,
    tool_persist_forecast,
    tool_persist_research_run,
)

REQUIRED_NODE_NAMES = (
    "router_validate_request",
    "tool_ensure_market_data_freshness",
    "tool_load_market_data",
    "tool_fetch_current_gold_quote",
    "tool_compute_indicators",
    "tool_fetch_macro_inputs",
    "agent_technical_analysis",
    "agent_macro_analysis",
    "tool_fetch_newsflow_inputs",
    "tool_fetch_pizza_index_inputs",
    "agent_news_analysis",
    "tool_load_forecast_feedback_history",
    "tool_fetch_market_sentiment_inputs",
    "tool_fetch_alt_data_inputs",
    "agent_market_sentiment_analysis",
    "agent_alt_data_analysis",
    "agent_risk_analysis",
    "agent_forecast_planning",
    "tool_persist_research_run",
    "tool_persist_forecast",
    "router_finalize_result",
)


def build_forecast_graph() -> StateGraph[WorkflowState]:
    graph = StateGraph(WorkflowState)
    graph.add_node("router_validate_request", router_validate_request)
    graph.add_node("tool_ensure_market_data_freshness", tool_ensure_market_data_freshness)
    graph.add_node("tool_load_market_data", tool_load_market_data)
    graph.add_node("tool_fetch_current_gold_quote", tool_fetch_current_gold_quote)
    graph.add_node("tool_compute_indicators", tool_compute_indicators)
    graph.add_node("tool_fetch_macro_inputs", tool_fetch_macro_inputs)
    graph.add_node("agent_technical_analysis", agent_technical_analysis)
    graph.add_node("agent_macro_analysis", agent_macro_analysis)
    graph.add_node("tool_fetch_newsflow_inputs", tool_fetch_newsflow_inputs)
    graph.add_node("tool_fetch_pizza_index_inputs", tool_fetch_pizza_index_inputs)
    graph.add_node("agent_news_analysis", agent_news_analysis)
    graph.add_node("tool_load_forecast_feedback_history", tool_load_forecast_feedback_history)
    graph.add_node("tool_fetch_market_sentiment_inputs", tool_fetch_market_sentiment_inputs)
    graph.add_node("tool_fetch_alt_data_inputs", tool_fetch_alt_data_inputs)
    graph.add_node("agent_market_sentiment_analysis", agent_market_sentiment_analysis)
    graph.add_node("agent_alt_data_analysis", agent_alt_data_analysis)
    graph.add_node("agent_risk_analysis", agent_risk_analysis)
    graph.add_node("agent_forecast_planning", agent_forecast_planning)
    graph.add_node("tool_persist_research_run", tool_persist_research_run)
    graph.add_node("tool_persist_forecast", tool_persist_forecast)
    graph.add_node("router_finalize_result", router_finalize_result)

    graph.set_entry_point("router_validate_request")
    graph.add_edge("router_validate_request", "tool_ensure_market_data_freshness")
    graph.add_edge("tool_ensure_market_data_freshness", "tool_load_market_data")
    graph.add_edge("tool_load_market_data", "tool_fetch_current_gold_quote")
    graph.add_edge("tool_fetch_current_gold_quote", "tool_compute_indicators")
    graph.add_edge("tool_compute_indicators", "agent_technical_analysis")
    graph.add_edge("agent_technical_analysis", "tool_fetch_macro_inputs")
    graph.add_edge("tool_fetch_macro_inputs", "agent_macro_analysis")
    graph.add_edge("agent_macro_analysis", "tool_fetch_newsflow_inputs")
    graph.add_edge("tool_fetch_newsflow_inputs", "agent_news_analysis")
    graph.add_edge("agent_news_analysis", "tool_fetch_pizza_index_inputs")
    graph.add_edge("tool_fetch_pizza_index_inputs", "tool_load_forecast_feedback_history")
    graph.add_edge("tool_load_forecast_feedback_history", "tool_fetch_market_sentiment_inputs")
    graph.add_edge("tool_fetch_market_sentiment_inputs", "tool_fetch_alt_data_inputs")
    graph.add_edge("tool_fetch_alt_data_inputs", "agent_market_sentiment_analysis")
    graph.add_edge("agent_market_sentiment_analysis", "agent_alt_data_analysis")
    graph.add_edge("agent_alt_data_analysis", "agent_risk_analysis")
    graph.add_edge("agent_risk_analysis", "agent_forecast_planning")
    graph.add_edge("agent_forecast_planning", "tool_persist_research_run")
    graph.add_edge("tool_persist_research_run", "tool_persist_forecast")
    graph.add_edge("tool_persist_forecast", "router_finalize_result")
    graph.add_edge("router_finalize_result", END)
    return graph
