from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


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


class ResearchStatusNotFoundError(ApiError):
    def __init__(self) -> None:
        super().__init__(
            type="research_status_not_found",
            message="Research status was not found",
            status_code=404,
        )


class PersistenceApiError(ApiError):
    def __init__(self, message: str = "Persistence operation failed") -> None:
        super().__init__(type="persistence_error", message=message, status_code=503)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return api_error_response(exc)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return api_error_response(ApiError(type="not_found", message="Resource was not found", status_code=404))
        if exc.status_code == 405:
            return api_error_response(
                ApiError(type="method_not_allowed", message="HTTP method is not allowed", status_code=405)
            )
        return api_error_response(
            ApiError(
                type="http_error",
                message="HTTP request failed",
                status_code=exc.status_code,
            )
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return api_error_response(
            ApiError(
                type="validation_error",
                message="Request validation failed",
                status_code=422,
            )
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return api_error_response(
            ApiError(
                type="internal_error",
                message="Internal server error",
                status_code=500,
            )
        )


def api_error_response(error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"type": error.type, "message": error.message}},
    )
