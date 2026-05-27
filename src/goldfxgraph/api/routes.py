from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Query, Request

from goldfxgraph.api.errors import (
    ApiError,
    ForecastNotFoundError,
    PersistenceApiError,
    ResearchRunNotFoundError,
)
from goldfxgraph.market_data.csv_loader import CsvValidationError
from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import DailyBar, ForecastHistoryItem, ForecastResult, ResearchRunResult
from goldfxgraph.workflow.graph import build_forecast_graph
from goldfxgraph.workflow.nodes import MarketDataFreshnessError, WorkflowState

router = APIRouter()


@router.get("/forecast/latest", response_model=ForecastResult)
async def get_latest_forecast(request: Request) -> ForecastResult:
    repository = _repository(request)
    forecast = await repository.get_latest_forecast()
    if forecast is None:
        raise ForecastNotFoundError()
    return forecast


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


@router.post("/research-runs", response_model=ResearchRunResult)
async def create_research_run(request: Request) -> ResearchRunResult:
    repository = _repository(request)

    try:
        run = await repository.create_research_run({"symbol": "XAUUSD", "entrypoint": "api"})
        run_id = int(run.id)
    except Exception as exc:
        raise PersistenceApiError() from exc

    try:
        state = await _run_forecast_workflow(request, repository, run_id)
        result_run = await repository.get_research_run(run_id)
    except QuoteProviderError as exc:
        message = _quote_provider_message(exc)
        await _mark_failed(repository, run_id, message)
        raise ApiError(type="quote_provider_error", message=message, status_code=503) from exc
    except MarketDataFreshnessError as exc:
        message = _market_data_freshness_message(exc)
        await _mark_failed(repository, run_id, message)
        raise ApiError(type="market_data_error", message=message, status_code=503) from exc
    except CsvValidationError as exc:
        await _mark_failed(repository, run_id, "Market data validation failed")
        raise ApiError(
            type="market_data_error",
            message="Market data could not be loaded or validated",
            status_code=422,
        ) from exc
    except ValueError as exc:
        await _mark_failed(repository, run_id, "Workflow failed")
        raise ApiError(type="workflow_error", message="Forecast workflow failed", status_code=502) from exc
    except Exception as exc:
        await _mark_failed(repository, run_id, "Persistence operation failed")
        raise PersistenceApiError() from exc

    if result_run is None:
        await _mark_failed(repository, run_id, "Workflow did not return a research run")
        raise PersistenceApiError("Research run could not be loaded after workflow completion")
    if state.get("result") is None or result_run.forecast is None:
        await _mark_failed(repository, run_id, "Workflow did not produce a forecast result")
        raise ApiError(type="workflow_error", message="Forecast workflow did not produce a result", status_code=502)
    return result_run


@router.get("/research-runs/{run_id}", response_model=ResearchRunResult)
async def get_research_run(run_id: int, request: Request) -> ResearchRunResult:
    repository = _repository(request)
    run = await repository.get_research_run(run_id)
    if run is None:
        raise ResearchRunNotFoundError()
    return run


async def _run_forecast_workflow(
    request: Request,
    repository: ForecastRepository,
    run_id: int,
) -> WorkflowState:
    state = WorkflowState(
        settings=request.app.state.settings,
        repository=repository,
        run_id=run_id,
    )
    graph = _compiled_forecast_graph(request)
    result = await graph.ainvoke(state)
    return cast(WorkflowState, result)


async def _mark_failed(repository: ForecastRepository, run_id: int, message: str) -> None:
    try:
        await repository.mark_run_failed(run_id, message)
    except Exception:
        # 原始错误应该优先返回；失败状态落库失败会由后续持久化监控处理。
        return


def _repository(request: Request) -> Any:
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        raise PersistenceApiError("Forecast repository is not available")
    return repository


def _quote_provider_message(exc: QuoteProviderError) -> str:
    message = str(exc).strip()
    if not message:
        return "Current quote provider request failed"
    return message


def _market_data_freshness_message(exc: MarketDataFreshnessError) -> str:
    message = str(exc).strip()
    if not message:
        return "Market data freshness preflight failed"
    return message


def _compiled_forecast_graph(request: Request) -> Any:
    graph = getattr(request.app.state, "compiled_forecast_graph", None)
    if graph is None:
        graph = build_forecast_graph().compile()
        request.app.state.compiled_forecast_graph = graph
    return graph
