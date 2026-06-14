from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError, install_error_handlers
from backend.models.review import ReviewCreateRequest


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


def test_unexpected_error_handler_logs_exception_server_side(monkeypatch) -> None:
    app = FastAPI()
    install_error_handlers(app)
    logged: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def capture_exception(
        message: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        logged.append((message, args, kwargs))

    monkeypatch.setattr("backend.api.errors.logger.exception", capture_exception)

    @app.post("/unexpected")
    def unexpected_error() -> None:
        raise RuntimeError("sensitive internal detail")

    response = TestClient(app, raise_server_exceptions=False).post("/unexpected")

    assert response.status_code == 500
    assert "sensitive internal detail" not in response.text
    assert len(logged) == 1
    message, args, kwargs = logged[0]
    assert message % args == "Unexpected error while handling POST /unexpected"
    exc_info = kwargs["exc_info"]
    assert isinstance(exc_info, tuple)
    assert exc_info[2] is not None


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


def test_local_smoke_repo_url_requires_explicit_internal_flag(monkeypatch) -> None:
    url = "http://github.com@127.0.0.1:8123/sample.git"

    monkeypatch.delenv("CODEPILOT_ALLOW_LOCAL_SMOKE_REPO", raising=False)
    assert _request_is_valid(url) is False

    monkeypatch.setenv("CODEPILOT_ALLOW_LOCAL_SMOKE_REPO", "true")
    assert ReviewCreateRequest(repo_url=url).repo_url is not None


def _request_is_valid(url: str) -> bool:
    try:
        ReviewCreateRequest(repo_url=url)
    except ValueError:
        return False
    return True
