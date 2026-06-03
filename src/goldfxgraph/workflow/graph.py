from __future__ import annotations

from collections.abc import Hashable

from langgraph.graph import END, StateGraph

from goldfxgraph.workflow.nodes import (
    WorkflowState,
    agent_alt_data_analysis,
    agent_bear_final_position,
    agent_bear_opening_case,
    agent_bear_rebuttal,
    agent_bull_final_position,
    agent_bull_opening_case,
    agent_bull_rebuttal,
    agent_macro_analysis,
    agent_market_sentiment_analysis,
    agent_news_analysis,
    agent_repair_committee_decision,
    agent_risk_analysis,
    agent_technical_analysis,
    agent_trading_committee_chair,
    node_build_evidence_package,
    node_persist_forecast,
    node_validate_committee_decision,
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
    tool_fetch_polymarket_inputs,
    tool_load_forecast_feedback_history,
    tool_load_market_data,
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
    "tool_fetch_polymarket_inputs",
    "agent_news_analysis",
    "tool_load_forecast_feedback_history",
    "tool_fetch_market_sentiment_inputs",
    "tool_fetch_alt_data_inputs",
    "agent_market_sentiment_analysis",
    "agent_alt_data_analysis",
    "agent_risk_analysis",
    "node_build_evidence_package",
    "agent_bull_opening_case",
    "agent_bear_opening_case",
    "agent_bull_rebuttal",
    "agent_bear_rebuttal",
    "agent_bull_final_position",
    "agent_bear_final_position",
    "agent_trading_committee_chair",
    "node_validate_committee_decision",
    "agent_repair_committee_decision",
    "node_persist_forecast",
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
    graph.add_node("tool_fetch_polymarket_inputs", tool_fetch_polymarket_inputs)
    graph.add_node("agent_news_analysis", agent_news_analysis)
    graph.add_node("tool_load_forecast_feedback_history", tool_load_forecast_feedback_history)
    graph.add_node("tool_fetch_market_sentiment_inputs", tool_fetch_market_sentiment_inputs)
    graph.add_node("tool_fetch_alt_data_inputs", tool_fetch_alt_data_inputs)
    graph.add_node("agent_market_sentiment_analysis", agent_market_sentiment_analysis)
    graph.add_node("agent_alt_data_analysis", agent_alt_data_analysis)
    graph.add_node("agent_risk_analysis", agent_risk_analysis)
    graph.add_node("node_build_evidence_package", node_build_evidence_package)
    graph.add_node("agent_bull_opening_case", agent_bull_opening_case)
    graph.add_node("agent_bear_opening_case", agent_bear_opening_case)
    graph.add_node("agent_bull_rebuttal", agent_bull_rebuttal)
    graph.add_node("agent_bear_rebuttal", agent_bear_rebuttal)
    graph.add_node("agent_bull_final_position", agent_bull_final_position)
    graph.add_node("agent_bear_final_position", agent_bear_final_position)
    graph.add_node("agent_trading_committee_chair", agent_trading_committee_chair)
    graph.add_node("node_validate_committee_decision", node_validate_committee_decision)
    graph.add_node("agent_repair_committee_decision", agent_repair_committee_decision)
    graph.add_node("node_persist_forecast", node_persist_forecast)
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
    graph.add_edge("tool_load_forecast_feedback_history", "tool_fetch_polymarket_inputs")
    graph.add_edge("tool_fetch_polymarket_inputs", "tool_fetch_market_sentiment_inputs")
    graph.add_edge("tool_fetch_market_sentiment_inputs", "tool_fetch_alt_data_inputs")
    graph.add_edge("tool_fetch_alt_data_inputs", "agent_market_sentiment_analysis")
    graph.add_edge("agent_market_sentiment_analysis", "agent_alt_data_analysis")
    graph.add_edge("agent_alt_data_analysis", "agent_risk_analysis")

    graph.add_edge("agent_risk_analysis", "node_build_evidence_package")
    graph.add_edge("node_build_evidence_package", "agent_bull_opening_case")
    graph.add_edge("node_build_evidence_package", "agent_bear_opening_case")
    graph.add_edge("agent_bull_opening_case", "agent_bull_rebuttal")
    graph.add_edge("agent_bull_opening_case", "agent_bear_rebuttal")
    graph.add_edge("agent_bear_opening_case", "agent_bull_rebuttal")
    graph.add_edge("agent_bear_opening_case", "agent_bear_rebuttal")
    graph.add_edge("agent_bull_rebuttal", "agent_bull_final_position")
    graph.add_edge("agent_bull_rebuttal", "agent_bear_final_position")
    graph.add_edge("agent_bear_rebuttal", "agent_bull_final_position")
    graph.add_edge("agent_bear_rebuttal", "agent_bear_final_position")
    graph.add_edge("agent_bull_final_position", "agent_trading_committee_chair")
    graph.add_edge("agent_bear_final_position", "agent_trading_committee_chair")
    graph.add_edge("agent_trading_committee_chair", "node_validate_committee_decision")
    graph.add_conditional_edges(
        "node_validate_committee_decision",
        _route_committee_validation,
        {
            "repair": "agent_repair_committee_decision",
            "persist": "node_persist_forecast",
        },
    )
    graph.add_edge("agent_repair_committee_decision", "node_validate_committee_decision")
    graph.add_edge("node_persist_forecast", "router_finalize_result")
    graph.add_edge("router_finalize_result", END)
    return graph


def _route_committee_validation(state: WorkflowState) -> Hashable:
    validation_status = state.get("validation_status")
    if validation_status is None:
        return "persist"

    is_valid = getattr(validation_status, "is_valid", None)
    validation_attempts = int(state.get("committee_validation_attempts") or 0)
    if is_valid is False and validation_attempts < 3:
        return "repair"
    return "persist"
