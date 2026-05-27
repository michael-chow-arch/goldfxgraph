from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from goldfxgraph.api.errors import register_error_handlers
from goldfxgraph.api.routes import router
from goldfxgraph.backfill.maintenance import run_eod_maintenance
from goldfxgraph.backfill.scheduler import EodMaintenanceSchedulerHandle, start_eod_maintenance_scheduler
from goldfxgraph.diagnostics.agent_health import format_agent_health_check_report, run_agent_health_check
from goldfxgraph.packages.common.settings import GoldFXGraphSettings, get_settings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import DailyBar, ForecastResult, ResearchRunResult

LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)

logger = logging.getLogger(__name__)


def create_app(
    *,
    testing: bool = False,
    settings: GoldFXGraphSettings | None = None,
    repository: ForecastRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.testing = testing
        session_factory = None
        maintenance_handle: EodMaintenanceSchedulerHandle | None = None
        if repository is not None:
            app.state.repository = repository
        elif testing:
            app.state.repository = InMemoryForecastRepository()
        else:
            session_factory = create_session_factory(resolved_settings.database_url)
            await init_models(session_factory.engine)
            app.state.session_factory = session_factory
            app.state.repository = ForecastRepository(session_factory)

        if not testing:
            startup_maintenance = await run_eod_maintenance(
                settings=resolved_settings,
                repository=app.state.repository,
                now=datetime.now(UTC),
            )
            if startup_maintenance.status == "failed":
                raise RuntimeError(
                    "EOD maintenance failed: "
                    f"backfill={startup_maintenance.backfill.status} "
                    f"evaluation={startup_maintenance.evaluation.status} "
                    f"reason={startup_maintenance.backfill.failure_reason or 'unknown'}"
                )
            try:
                app.state.agent_health_report = await run_agent_health_check(
                    settings=resolved_settings,
                    repository=app.state.repository,
                )
                logger.info(
                    "agent health check completed:\n%s",
                    format_agent_health_check_report(app.state.agent_health_report),
                )
            except Exception:  # noqa: BLE001
                logger.exception("agent health check failed")
            maintenance_handle = start_eod_maintenance_scheduler(
                settings=resolved_settings,
                repository=app.state.repository,
            )
            app.state.eod_maintenance_scheduler = maintenance_handle

        try:
            yield
        finally:
            if maintenance_handle is not None:
                maintenance_handle.stop_event.set()
                maintenance_handle.task.cancel()
                try:
                    await maintenance_handle.task
                except asyncio.CancelledError:
                    pass
            if session_factory is not None:
                await session_factory.engine.dispose()

    app = FastAPI(title="GoldFXGraph API", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.testing = testing
    if repository is not None:
        app.state.repository = repository
    elif testing:
        app.state.repository = InMemoryForecastRepository()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOCAL_FRONTEND_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")
    register_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


class InMemoryForecastRepository:
    """测试专用 repository，避免 API factory 在 testing 模式依赖 PostgreSQL。"""

    def __init__(self) -> None:
        self._next_run_id = 1
        self._next_forecast_id = 1
        self.runs: dict[int, ResearchRunResult] = {}
        self.forecasts: dict[int, ForecastResult] = {}
        self.market_bars: dict[tuple[str, date], DailyBar] = {}

    async def create_research_run(self, input_summary: dict[str, object]) -> Any:
        run_id = self._next_run_id
        self._next_run_id += 1
        self.runs[run_id] = ResearchRunResult(
            id=run_id,
            status="running",
            started_at=datetime.now(UTC),
            input_summary=dict(input_summary),
        )
        return type("ResearchRunRecord", (), {"id": run_id})()

    async def mark_run_success(self, run_id: int) -> None:
        run = self.runs[run_id]
        self.runs[run_id] = run.model_copy(update={"status": "success", "completed_at": datetime.now(UTC)})

    async def mark_run_failed(self, run_id: int, error_message: str) -> None:
        run = self.runs[run_id]
        self.runs[run_id] = run.model_copy(
            update={"status": "failed", "completed_at": datetime.now(UTC), "error_message": error_message}
        )

    async def save_forecast(self, run_id: int, forecast: ForecastResult) -> ForecastResult:
        forecast_id = self._next_forecast_id
        self._next_forecast_id += 1
        saved = forecast.model_copy(update={"id": forecast_id, "run_id": run_id})
        self.forecasts[forecast_id] = saved
        self.runs[run_id] = self.runs[run_id].model_copy(update={"forecast": saved})
        return saved

    async def upsert_market_bars(self, bars: list[DailyBar]) -> int:
        for bar in bars:
            self.market_bars[(bar.symbol.upper(), bar.date)] = bar
        return len(bars)

    async def get_latest_market_bar(self, symbol: str = "XAUUSD") -> DailyBar | None:
        symbol_key = symbol.strip().upper()
        bars = [bar for (bar_symbol, _), bar in self.market_bars.items() if bar_symbol == symbol_key]
        if not bars:
            return None
        return sorted(bars, key=lambda bar: (bar.date, bar.symbol))[::-1][0]

    async def get_market_bars_between(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[DailyBar]:
        symbol_key = symbol.strip().upper()
        bars = [
            bar
            for (bar_symbol, bar_date), bar in self.market_bars.items()
            if bar_symbol == symbol_key and start_date <= bar_date <= end_date
        ]
        return sorted(bars, key=lambda bar: (bar.date, bar.symbol))

    async def get_market_bars_for_date(self, symbol: str, target_date: date) -> DailyBar | None:
        return self.market_bars.get((symbol.strip().upper(), target_date))

    async def get_market_bars_count(self, symbol: str = "XAUUSD") -> int:
        symbol_key = symbol.strip().upper()
        return sum(1 for (bar_symbol, _) in self.market_bars if bar_symbol == symbol_key)

    async def get_latest_forecast(self) -> ForecastResult | None:
        if not self.forecasts:
            return None
        return self.forecasts[max(self.forecasts)]

    async def get_research_run(self, run_id: int) -> ResearchRunResult | None:
        return self.runs.get(run_id)
