from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from goldfxgraph.backfill.eod_backfill import _latest_completed_trading_day
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.timeframes import trading_day_for_timestamp
from goldfxgraph.workflow.nodes import evaluate_forecast_performance


@dataclass(slots=True)
class ForecastEvaluationBatchResult:
    target_date: date
    evaluated_forecast_ids: list[int]
    skipped_forecast_ids: list[int]
    written: bool
    status: str
    settlement_bar_date: date | None
    summaries: list[str]


async def run_eod_forecast_evaluation(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    now: datetime | None = None,
) -> ForecastEvaluationBatchResult:
    target_date = _latest_completed_trading_day(
        now=now or datetime.now(UTC),
        timezone_name=settings.eod_backfill_timezone,
        cutoff_hour=settings.eod_backfill_cutoff_hour,
        cutoff_minute=settings.eod_backfill_cutoff_minute,
    )
    settlement_bar = await repository.get_market_bars_for_date("XAUUSD", target_date)
    if settlement_bar is None:
        return ForecastEvaluationBatchResult(
            target_date=target_date,
            evaluated_forecast_ids=[],
            skipped_forecast_ids=[],
            written=False,
            status="no-op",
            settlement_bar_date=None,
            summaries=[],
        )

    history = await repository.get_daily_forecast_history(
        limit=500,
        timezone_name=settings.eod_backfill_timezone,
        cutoff_hour=settings.eod_backfill_cutoff_hour,
        cutoff_minute=settings.eod_backfill_cutoff_minute,
    )
    candidates = []
    for item in history:
        forecast_trading_day = trading_day_for_timestamp(
            item.forecast.reference_time,
            timezone_name=settings.eod_backfill_timezone,
            cutoff_hour=settings.eod_backfill_cutoff_hour,
            cutoff_minute=settings.eod_backfill_cutoff_minute,
        )
        if forecast_trading_day > target_date:
            continue
        if item.evaluation is None and item.forecast.reference_time <= (now or datetime.now(UTC)):
            candidates.append(item)
    if not candidates:
        return ForecastEvaluationBatchResult(
            target_date=target_date,
            evaluated_forecast_ids=[],
            skipped_forecast_ids=[],
            written=False,
            status="no-op",
            settlement_bar_date=settlement_bar.date,
            summaries=[],
        )

    evaluated_forecast_ids: list[int] = []
    skipped_forecast_ids: list[int] = []
    summaries: list[str] = []
    last_settlement_date: date | None = None
    for item in candidates:
        forecast_id = item.forecast.id
        if forecast_id is None:
            skipped_forecast_ids.append(-1)
            continue

        forecast_trading_day = trading_day_for_timestamp(
            item.forecast.reference_time,
            timezone_name=settings.eod_backfill_timezone,
            cutoff_hour=settings.eod_backfill_cutoff_hour,
            cutoff_minute=settings.eod_backfill_cutoff_minute,
        )
        settlement_bar_for_day = await repository.get_market_bars_for_date("XAUUSD", forecast_trading_day)
        if settlement_bar_for_day is None:
            skipped_forecast_ids.append(forecast_id)
            continue

        evaluation = evaluate_forecast_performance(
            item.forecast,
            settlement_bar_for_day,
            evaluated_at=now or datetime.now(UTC),
        )
        await repository.save_forecast_evaluation(forecast_id, evaluation)
        evaluated_forecast_ids.append(forecast_id)
        summaries.append(evaluation.summary)
        last_settlement_date = settlement_bar_for_day.date

    return ForecastEvaluationBatchResult(
        target_date=target_date,
        evaluated_forecast_ids=evaluated_forecast_ids,
        skipped_forecast_ids=skipped_forecast_ids,
        written=bool(evaluated_forecast_ids),
        status="written" if evaluated_forecast_ids else "no-op",
        settlement_bar_date=last_settlement_date or settlement_bar.date,
        summaries=summaries,
    )
