from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from goldfxgraph.api.errors import register_error_handlers
from goldfxgraph.api.routes import router
from goldfxgraph.packages.common.settings import GoldFXGraphSettings, get_settings
from goldfxgraph.persistence.database import create_session_factory, init_models
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import ForecastResult, ResearchRunResult

LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)


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
        if repository is not None:
            app.state.repository = repository
        elif testing:
            app.state.repository = InMemoryForecastRepository()
        else:
            session_factory = create_session_factory(resolved_settings.database_url)
            await init_models(session_factory.engine)
            app.state.session_factory = session_factory
            app.state.repository = ForecastRepository(session_factory)

        try:
            yield
        finally:
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

    async def get_latest_forecast(self) -> ForecastResult | None:
        if not self.forecasts:
            return None
        return self.forecasts[max(self.forecasts)]

    async def get_research_run(self, run_id: int) -> ResearchRunResult | None:
        return self.runs.get(run_id)
