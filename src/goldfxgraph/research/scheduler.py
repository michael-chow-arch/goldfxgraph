from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from goldfxgraph.packages.common.settings import GoldFXGraphSettings
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import SchedulerRunStatus
from goldfxgraph.workflow.executor import run_forecast_workflow

logger = logging.getLogger(__name__)

DEFAULT_RESEARCH_SCHEDULER_INTERVAL_SECONDS = 15 * 60


@dataclass(slots=True)
class ResearchScheduler:
    settings: GoldFXGraphSettings
    repository: ForecastRepository
    interval_seconds: int = DEFAULT_RESEARCH_SCHEDULER_INTERVAL_SECONDS
    latest_status: SchedulerRunStatus | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def run_once(self) -> SchedulerRunStatus:
        async with self._lock:
            scheduler_run = await self.repository.create_scheduler_run(
                {
                    "symbol": "XAUUSD",
                    "entrypoint": "scheduler",
                    "interval_seconds": self.interval_seconds,
                }
            )
            await self.repository.update_scheduler_run_stage(
                scheduler_run.id,
                current_stage="router_validate_request",
                agent_statuses=_pending_agent_statuses(),
                status="running",
            )

            try:
                run = await self.repository.create_research_run(
                    {
                        "symbol": "XAUUSD",
                        "entrypoint": "scheduler",
                        "scheduler_run_id": scheduler_run.id,
                    }
                )
                workflow_state = await run_forecast_workflow(
                    settings=self.settings,
                    repository=self.repository,
                    run_id=int(run.id),
                    scheduler_run_id=scheduler_run.id,
                )
                await self.repository.update_scheduler_run_stage(
                    scheduler_run.id,
                    current_stage="persist_result",
                    agent_statuses=_success_agent_statuses(),
                    agent_diagnostics=list(workflow_state.get("agent_diagnostics") or []),
                    status="success",
                    completed_at=datetime.now(UTC),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("research scheduler cycle failed")
                await self.repository.update_scheduler_run_stage(
                    scheduler_run.id,
                    current_stage="failed",
                    agent_statuses=_failed_agent_statuses(),
                    agent_diagnostics=[],
                    status="failed",
                    last_error=str(exc) or "Research scheduler failed",
                    completed_at=datetime.now(UTC),
                )
            finally:
                self.latest_status = await self.repository.get_latest_scheduler_run()

            if self.latest_status is None:
                raise RuntimeError("research scheduler status could not be loaded")
            return self.latest_status

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        await self.run_once()

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.interval_seconds)
                break
            except TimeoutError:
                pass

            try:
                await self.run_once()
            except Exception:  # noqa: BLE001
                # 失败已经写入 scheduler_runs，循环继续等待下一次 tick。
                continue


@dataclass(slots=True)
class ResearchSchedulerHandle:
    stop_event: asyncio.Event
    task: asyncio.Task[None]
    scheduler: ResearchScheduler

    @property
    def latest_status(self) -> SchedulerRunStatus | None:
        return self.scheduler.latest_status


def build_research_scheduler(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    interval_seconds: int = DEFAULT_RESEARCH_SCHEDULER_INTERVAL_SECONDS,
) -> ResearchScheduler:
    return ResearchScheduler(
        settings=settings,
        repository=repository,
        interval_seconds=interval_seconds,
    )


def start_research_scheduler(
    *,
    settings: GoldFXGraphSettings,
    repository: ForecastRepository,
    interval_seconds: int = DEFAULT_RESEARCH_SCHEDULER_INTERVAL_SECONDS,
) -> ResearchSchedulerHandle:
    stop_event = asyncio.Event()
    scheduler = build_research_scheduler(
        settings=settings,
        repository=repository,
        interval_seconds=interval_seconds,
    )
    task = asyncio.create_task(scheduler.run_forever(stop_event))
    return ResearchSchedulerHandle(stop_event=stop_event, task=task, scheduler=scheduler)


def _pending_agent_statuses() -> list[dict[str, str]]:
    return [
        {"agent": "technical", "status": "pending"},
        {"agent": "macro", "status": "pending"},
        {"agent": "news", "status": "pending"},
        {"agent": "market_sentiment", "status": "pending"},
        {"agent": "alt_data", "status": "pending"},
        {"agent": "risk", "status": "pending"},
        {"agent": "forecast", "status": "pending"},
    ]


def _success_agent_statuses() -> list[dict[str, str]]:
    return [
        {"agent": "technical", "status": "success"},
        {"agent": "macro", "status": "success"},
        {"agent": "news", "status": "success"},
        {"agent": "market_sentiment", "status": "success"},
        {"agent": "alt_data", "status": "success"},
        {"agent": "risk", "status": "success"},
        {"agent": "forecast", "status": "success"},
    ]


def _failed_agent_statuses() -> list[dict[str, str]]:
    return [
        {"agent": "technical", "status": "failed"},
        {"agent": "macro", "status": "failed"},
        {"agent": "news", "status": "failed"},
        {"agent": "market_sentiment", "status": "failed"},
        {"agent": "alt_data", "status": "failed"},
        {"agent": "risk", "status": "failed"},
        {"agent": "forecast", "status": "failed"},
    ]
