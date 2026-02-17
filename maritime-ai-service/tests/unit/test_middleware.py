"""Tests for app.core.middleware — Request-ID middleware."""

import pytest
import httpx
from fastapi import FastAPI

from app.core.middleware import RequestIDMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


def _make_client(app: FastAPI) -> httpx.AsyncClient:
    """Create async httpx client compatible with httpx 0.28+."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


class TestRequestIDMiddleware:
    """Verify X-Request-ID is generated/propagated."""

    @pytest.mark.asyncio
    async def test_generates_request_id_when_missing(self):
        async with _make_client(_make_app()) as client:
            resp = await client.get("/ping")
            assert resp.status_code == 200
            request_id = resp.headers.get("X-Request-ID")
            assert request_id is not None
            assert len(request_id) == 32  # uuid4 hex

    @pytest.mark.asyncio
    async def test_propagates_caller_request_id(self):
        async with _make_client(_make_app()) as client:
            resp = await client.get("/ping", headers={"X-Request-ID": "my-trace-123"})
            assert resp.headers["X-Request-ID"] == "my-trace-123"

    @pytest.mark.asyncio
    async def test_each_request_gets_unique_id(self):
        async with _make_client(_make_app()) as client:
            ids = set()
            for _ in range(5):
                resp = await client.get("/ping")
                ids.add(resp.headers["X-Request-ID"])
            assert len(ids) == 5

    @pytest.mark.asyncio
    async def test_request_id_in_response_with_handled_error(self):
        from fastapi.responses import JSONResponse

        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.exception_handler(ValueError)
        async def value_error_handler(request, exc):
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
            )

        @app.get("/fail")
        async def fail():
            raise ValueError("boom")

        async with _make_client(app) as client:
            resp = await client.get("/fail")
            assert resp.status_code == 400
            assert "X-Request-ID" in resp.headers
