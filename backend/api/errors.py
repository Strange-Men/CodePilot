from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    def __init__(self, status_code: int, error: str, code: str, detail: str) -> None:
        super().__init__(error)
        self.status_code = status_code
        self.error = error
        self.code = code
        self.detail = detail


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(_request: Request, exc: APIError) -> JSONResponse:
        return _error_response(exc.status_code, exc.error, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        detail = _validation_detail(errors[0]) if errors else "The request payload is invalid."
        return _error_response(422, "Invalid request", "validation_error", detail)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = str(exc.detail)
        return _error_response(
            exc.status_code,
            detail,
            f"http_{exc.status_code}",
            detail,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
        return _error_response(
            500,
            "Internal server error",
            "internal_error",
            "The request could not be completed.",
        )


def _error_response(status_code: int, error: str, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "code": code, "detail": detail},
    )


def _validation_detail(error: dict[str, Any]) -> str:
    location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
    message = str(error.get("msg", "Invalid value"))
    return f"{location}: {message}" if location else message
