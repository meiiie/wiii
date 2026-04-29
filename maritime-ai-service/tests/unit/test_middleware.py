"""Tests for app.core.middleware — Request-ID middleware."""

import pytest
import httpx
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.core.middleware import (
    EmbedCSPMiddleware,
    RequestIDMiddleware,
    _find_embed_asset_replacement,
)


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


def _make_embed_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(EmbedCSPMiddleware)

    @app.get("/embed/assets/embed.js")
    async def embed_asset():
        return PlainTextResponse("ok")

    @app.get("/ping")
    async def ping():
        return PlainTextResponse("ok")

    return app


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


class TestEmbedCSPMiddleware:
    """Verify iframe policy and local cache safety for embed assets."""

    def test_finds_single_current_embed_asset_for_stale_hash(self, tmp_path):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        current_asset = assets_dir / "MarkdownLiteSegment-current.js"
        current_asset.write_text("export default null;", encoding="utf-8")

        assert (
            _find_embed_asset_replacement(
                "/embed/assets/MarkdownLiteSegment-stale.js",
                roots=[tmp_path],
            )
            == current_asset
        )

    def test_refuses_ambiguous_embed_asset_replacement(self, tmp_path):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "dist-js-one.js").write_text("one", encoding="utf-8")
        (assets_dir / "dist-js-two.js").write_text("two", encoding="utf-8")

        assert (
            _find_embed_asset_replacement("/embed/assets/dist-js-stale.js", roots=[tmp_path])
            is None
        )

    @pytest.mark.asyncio
    async def test_sets_no_store_for_embed_assets_in_development(self, monkeypatch):
        monkeypatch.setattr(settings, "environment", "development")
        monkeypatch.setattr(settings, "embed_allowed_origins", "http://localhost:4200")

        async with _make_client(_make_embed_app()) as client:
            resp = await client.get("/embed/assets/embed.js")

        assert resp.status_code == 200
        assert resp.headers["Content-Security-Policy"] == (
            "frame-ancestors 'self' http://localhost:4200"
        )
        assert resp.headers["Cache-Control"] == "no-store"
        assert resp.headers["Pragma"] == "no-cache"
        assert resp.headers["Expires"] == "0"

    @pytest.mark.asyncio
    async def test_serves_stale_embed_chunk_replacement_in_development(
        self, monkeypatch, tmp_path
    ):
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        (assets_dir / "MarkdownLiteSegment-current.js").write_text("ok", encoding="utf-8")
        monkeypatch.setattr(settings, "environment", "development")
        monkeypatch.setattr(settings, "embed_allowed_origins", "")
        monkeypatch.setattr("app.core.middleware._embed_asset_roots", lambda: [tmp_path])

        async with _make_client(_make_embed_app()) as client:
            resp = await client.get("/embed/assets/MarkdownLiteSegment-stale.js")

        assert resp.status_code == 200
        assert resp.text == "ok"
        assert resp.headers["Content-Security-Policy"] == "frame-ancestors 'self'"
        assert resp.headers["Cache-Control"] == "no-store"

    @pytest.mark.asyncio
    async def test_keeps_non_embed_routes_cache_neutral(self, monkeypatch):
        monkeypatch.setattr(settings, "environment", "development")

        async with _make_client(_make_embed_app()) as client:
            resp = await client.get("/ping")

        assert resp.status_code == 200
        assert "Content-Security-Policy" not in resp.headers
        assert "Cache-Control" not in resp.headers
