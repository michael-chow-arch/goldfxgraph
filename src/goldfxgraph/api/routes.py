from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from goldfxgraph.api.errors import (
    ApiError,
    ForecastNotFoundError,
    PersistenceApiError,
    ResearchRunNotFoundError,
)
from goldfxgraph.market_data.csv_loader import CsvValidationError
from goldfxgraph.market_data.current_quote import QuoteProviderError
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import ForecastResult, ResearchRunResult
from goldfxgraph.workflow.nodes import (
    WorkflowState,
    agent_forecast_planning,
    agent_macro_analysis,
    agent_news_analysis,
    agent_risk_analysis,
    agent_technical_analysis,
    router_finalize_result,
    router_validate_request,
    tool_compute_indicators,
    tool_fetch_current_gold_quote,
    tool_load_market_data,
    tool_persist_forecast,
)

router = APIRouter()


@router.get("/forecast/latest", response_model=ForecastResult)
async def get_latest_forecast(request: Request) -> ForecastResult:
    repository = _repository(request)
    forecast = await repository.get_latest_forecast()
    if forecast is None:
        raise ForecastNotFoundError()
    return forecast


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
        await _mark_failed(repository, run_id, "Current quote provider is not configured")
        raise ApiError(
            type="quote_provider_unconfigured" if "not configured" in str(exc) else "quote_provider_error",
            message="Current quote provider is not configured"
            if "not configured" in str(exc)
            else "Current quote provider request failed",
            status_code=503,
        ) from exc
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
        raise PersistenceApiError("Research run could not be loaded after workflow completion")
    if state.get("result") is None or result_run.forecast is None:
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
    state = router_validate_request(state)
    state = tool_load_market_data(state)
    state = tool_fetch_current_gold_quote(state)
    state = tool_compute_indicators(state)
    state = agent_technical_analysis(state)
    state = agent_macro_analysis(state)
    state = agent_news_analysis(state)
    state = agent_risk_analysis(state)
    state = agent_forecast_planning(state)
    state = await tool_persist_forecast(state)
    return router_finalize_result(state)


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
