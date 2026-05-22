from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class ApiError(Exception):
    type: str
    message: str
    status_code: int = 400


class ForecastNotFoundError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            type="forecast_not_found",
            message="Latest forecast was not found",
            status_code=404,
        )


class ResearchRunNotFoundError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            type="research_run_not_found",
            message="Research run was not found",
            status_code=404,
        )


class PersistenceApiError(ApiError):
    def __init__(self, message: str = "Persistence operation failed") -> None:
        super().__init__(type="persistence_error", message=message, status_code=503)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return api_error_response(exc)


def api_error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"type": error.type, "message": error.message}},
    )
