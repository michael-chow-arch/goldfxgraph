from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from goldfxgraph.api.errors import (
    ForecastNotFoundError,
    PersistenceApiError,
    ResearchRunNotFoundError,
    ResearchStatusNotFoundError,
)
from goldfxgraph.schemas.forecast import (
    DailyBar,
    ForecastHistoryItem,
    ForecastResult,
    ResearchRunResult,
    SchedulerRunStatus,
)

router = APIRouter()


@router.get("/forecast/latest", response_model=ForecastResult)
async def get_latest_forecast(request: Request) -> ForecastResult:
    repository = _repository(request)
    forecast = await repository.get_latest_forecast()
    if forecast is None:
        raise ForecastNotFoundError()
    return forecast


@router.get("/research-status/latest", response_model=SchedulerRunStatus)
async def get_latest_research_status(request: Request) -> SchedulerRunStatus:
    repository = _repository(request)
    status = await repository.get_latest_scheduler_run()
    if status is None:
        raise ResearchStatusNotFoundError()
    return status


@router.get("/forecast/history", response_model=list[ForecastHistoryItem])
async def get_forecast_history(request: Request, limit: int = 30) -> list[ForecastHistoryItem]:
    repository = _repository(request)
    settings = request.app.state.settings
    history = await repository.get_daily_forecast_history(
        limit=limit,
        timezone_name=settings.eod_backfill_timezone,
        cutoff_hour=settings.eod_backfill_cutoff_hour,
        cutoff_minute=settings.eod_backfill_cutoff_minute,
    )
    return history


@router.get("/market-data/bars", response_model=list[DailyBar])
async def get_market_data_bars(
    request: Request,
    symbol: str = "XAUUSD",
    limit: int = Query(default=60, ge=1, le=180),
) -> list[DailyBar]:
    repository = _repository(request)
    bars = await repository.get_recent_market_bars(symbol=symbol, limit=limit)
    return bars


@router.get("/research-runs/{run_id}", response_model=ResearchRunResult)
async def get_research_run(run_id: int, request: Request) -> ResearchRunResult:
    repository = _repository(request)
    run = await repository.get_research_run(run_id)
    if run is None:
        raise ResearchRunNotFoundError()
    return run


def _repository(request: Request) -> Any:
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise PersistenceApiError("Forecast repository is not available")
    return repository
