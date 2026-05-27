from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from goldfxgraph.backfill.eod_backfill import BackfillResult, run_eod_backfill
from goldfxgraph.backfill.eod_evaluation import ForecastEvaluationBatchResult, run_eod_forecast_evaluation
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.repositories import ForecastRepository


@dataclass(slots=True)
class EodMaintenanceResult:
    backfill: BackfillResult
    evaluation: ForecastEvaluationBatchResult
    status: str

    @property
    def wrote_anything(self) -> bool:
        return self.backfill.written or self.evaluation.written


async def run_eod_maintenance(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    now: datetime | None = None,
) -> EodMaintenanceResult:
    resolved_now = now or datetime.now(UTC)
    backfill_result = await run_eod_backfill(
        settings=settings,
        repository=repository,
        now=resolved_now,
    )
    evaluation_result = await run_eod_forecast_evaluation(
        settings=settings,
        repository=repository,
        now=resolved_now,
    )
    if getattr(backfill_result, "failed", False) or evaluation_result.status == "failed":
        status = "failed"
    elif backfill_result.written or evaluation_result.written:
        status = "written"
    else:
        status = "no-op"
    return EodMaintenanceResult(
        backfill=backfill_result,
        evaluation=evaluation_result,
        status=status,
    )
