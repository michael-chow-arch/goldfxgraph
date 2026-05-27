from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from goldfxgraph.backfill.maintenance import run_eod_maintenance
from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.repositories import ForecastRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EodMaintenanceSchedulerHandle:
    stop_event: asyncio.Event
    task: asyncio.Task[None]


def calculate_next_run_at(
    *,
    now: datetime,
    timezone_name: str,
    cutoff_hour: int,
    cutoff_minute: int,
) -> datetime:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    candidate = local_now.replace(
        hour=cutoff_hour,
        minute=cutoff_minute,
        second=0,
        microsecond=0,
    )
    if local_now >= candidate:
        candidate = candidate + timedelta(days=1)
        candidate = candidate.replace(
            hour=cutoff_hour,
            minute=cutoff_minute,
            second=0,
            microsecond=0,
        )
    if candidate.weekday() == 5:
        candidate += timedelta(days=1)
        candidate = candidate.replace(
            hour=cutoff_hour,
            minute=cutoff_minute,
            second=0,
            microsecond=0,
        )
    return candidate.astimezone(UTC)


async def run_eod_maintenance_loop(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    stop_event: asyncio.Event,
) -> None:
    await _run_maintenance_cycle(settings=settings, repository=repository)

    while not stop_event.is_set():
        now = datetime.now(UTC)
        next_run_at = calculate_next_run_at(
            now=now,
            timezone_name=settings.eod_backfill_timezone,
            cutoff_hour=settings.eod_backfill_cutoff_hour,
            cutoff_minute=settings.eod_backfill_cutoff_minute,
        )
        delay_seconds = max(0.0, (next_run_at - now).total_seconds())
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay_seconds)
            break
        except TimeoutError:
            pass

        await _run_maintenance_cycle(settings=settings, repository=repository)


async def _run_maintenance_cycle(*, settings: GoldFXGraphSettings, repository: ForecastRepository) -> None:
    try:
        result = await run_eod_maintenance(settings=settings, repository=repository, now=datetime.now(UTC))
        if result.status == "failed":
            logger.error(
                "eod maintenance failed: backfill=%s evaluation=%s latest_db=%s target=%s missing=%s reason=%s",
                result.backfill.status,
                result.evaluation.status,
                result.backfill.latest_existing_date,
                result.backfill.target_date,
                ",".join(item.isoformat() for item in result.backfill.missing_dates) or "-",
                result.backfill.failure_reason or "unknown",
            )
        else:
            logger.info(
                "eod maintenance completed: status=%s backfill=%s evaluation=%s latest_db=%s target=%s missing=%s",
                result.status,
                result.backfill.status,
                result.evaluation.status,
                result.backfill.latest_existing_date,
                result.backfill.target_date,
                ",".join(item.isoformat() for item in result.backfill.missing_dates) or "-",
            )
    except Exception:  # noqa: BLE001
        logger.exception("eod maintenance failed")


def start_eod_maintenance_scheduler(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
) -> EodMaintenanceSchedulerHandle:
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_eod_maintenance_loop(
            settings=settings,
            repository=repository,
            stop_event=stop_event,
        )
    )
    return EodMaintenanceSchedulerHandle(stop_event=stop_event, task=task)
