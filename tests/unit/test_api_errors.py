from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError, install_error_handlers


def test_api_error_handler_preserves_structured_fields() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/known")
    def known_error() -> None:
        raise APIError(409, "Known failure", "known_failure", "A precise explanation.")

    response = TestClient(app).get("/known")

    assert response.status_code == 409
    assert response.json() == {
        "error": "Known failure",
        "code": "known_failure",
        "detail": "A precise explanation.",
    }


def test_unexpected_error_handler_does_not_expose_internal_details() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/unexpected")
    def unexpected_error() -> None:
        raise RuntimeError("database password or internal stack detail")

    response = TestClient(app, raise_server_exceptions=False).get("/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "error": "Internal server error",
        "code": "internal_error",
        "detail": "The request could not be completed.",
    }


def test_framework_http_errors_use_structured_envelope() -> None:
    app = FastAPI()
    install_error_handlers(app)

    response = TestClient(app).get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": "Not Found",
        "code": "http_404",
        "detail": "Not Found",
    }
