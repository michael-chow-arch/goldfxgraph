"""Daily market data backfill and end-of-day evaluation helpers."""

from goldfxgraph.backfill.eod_backfill import BackfillResult, run_eod_backfill
from goldfxgraph.backfill.eod_evaluation import ForecastEvaluationBatchResult, run_eod_forecast_evaluation
from goldfxgraph.backfill.maintenance import EodMaintenanceResult, run_eod_maintenance
from goldfxgraph.backfill.scheduler import (
    EodMaintenanceSchedulerHandle,
    calculate_next_run_at,
    start_eod_maintenance_scheduler,
)

__all__ = [
    "BackfillResult",
    "EodMaintenanceResult",
    "EodMaintenanceSchedulerHandle",
    "ForecastEvaluationBatchResult",
    "calculate_next_run_at",
    "run_eod_maintenance",
    "run_eod_backfill",
    "run_eod_forecast_evaluation",
    "start_eod_maintenance_scheduler",
]
