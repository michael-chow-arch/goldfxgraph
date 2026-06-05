"""LangGraph workflow package."""

from goldfxgraph.workflow.graph import REQUIRED_NODE_NAMES, build_forecast_graph
from goldfxgraph.workflow.nodes import WorkflowState, create_research_forecast_from_inputs

__all__ = [
    "REQUIRED_NODE_NAMES",
    "WorkflowState",
    "build_forecast_graph",
    "create_research_forecast_from_inputs",
]
