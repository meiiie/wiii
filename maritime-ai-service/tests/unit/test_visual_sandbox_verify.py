"""Tests for sandbox-based visual rendering verification (Phase 3)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.engine.tools.visual_sandbox_verify import (
    VisualSandboxVerifyRequest,
    VisualSandboxVerifyResult,
    VisualSandboxVerifier,
)
from app.sandbox.models import SandboxArtifact, SandboxExecutionResult


class TestVisualSandboxVerifyRequest:
    def test_request_defaults(self):
        req = VisualSandboxVerifyRequest(html="<p>Hello</p>")
        assert req.html == "<p>Hello</p>"
        assert req.visual_type == ""
        assert req.viewport_width == 1024
        assert req.viewport_height == 768
        assert req.timeout_seconds is None

    def test_request_custom(self):
        req = VisualSandboxVerifyRequest(
            html="<div/>",
            visual_type="simulation",
            viewport_width=800,
            viewport_height=600,
            timeout_seconds=30,
        )
        assert req.visual_type == "simulation"
        assert req.viewport_width == 800
        assert req.timeout_seconds == 30


class TestVisualSandboxVerifyResult:
    def test_result_success(self):
        result = VisualSandboxVerifyResult(
            success=True,
            screenshot_url="https://example.com/screenshot.png",
        )
        assert result.success is True
        assert result.screenshot_url is not None

    def test_result_failure(self):
        result = VisualSandboxVerifyResult(
            success=False,
            error="Sandbox unavailable",
        )
        assert result.success is False
        assert result.error == "Sandbox unavailable"


class TestVisualSandboxVerifier:
    def _make_mock_service(self, *, success: bool, screenshot_url: str | None = None):
        service = MagicMock()

        async def mock_execute(*args, **kwargs):
            if success:
                artifacts = []
                if screenshot_url:
                    artifacts.append(SandboxArtifact(
                        name="screenshot.png",
                        content_type="image/png",
                        url=screenshot_url,
                    ))
                return SandboxExecutionResult(
                    success=True,
                    artifacts=artifacts,
                )
            return SandboxExecutionResult(
                success=False,
                error="Sandbox error",
            )

        service.execute_profile = mock_execute
        return service

    @pytest.mark.asyncio
    async def test_verify_with_mock_sandbox(self):
        service = self._make_mock_service(
            success=True,
            screenshot_url="https://sandbox.test/screenshot.png",
        )
        verifier = VisualSandboxVerifier(service=service)
        request = VisualSandboxVerifyRequest(html="<p>Test</p>")
        result = await verifier.verify(request)
        assert result.success is True
        assert result.screenshot_url == "https://sandbox.test/screenshot.png"

    @pytest.mark.asyncio
    async def test_verify_sandbox_failure_graceful(self):
        service = self._make_mock_service(success=False)
        verifier = VisualSandboxVerifier(service=service)
        request = VisualSandboxVerifyRequest(html="<p>Test</p>")
        result = await verifier.verify(request)
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_stages_html_as_file(self):
        service = self._make_mock_service(success=True)
        # Track what files are passed
        captured_kwargs = {}

        async def capture_execute(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return SandboxExecutionResult(success=True, artifacts=[])

        service.execute_profile = capture_execute

        verifier = VisualSandboxVerifier(service=service)
        request = VisualSandboxVerifyRequest(html="<html><body>Hello</body></html>")
        await verifier.verify(request)

        files = captured_kwargs.get("files", {})
        assert "index.html" in files
        assert "Hello" in files["index.html"]

    @pytest.mark.asyncio
    async def test_verify_no_service_graceful(self):
        verifier = VisualSandboxVerifier(service=None)
        # Mock _get_service to raise
        verifier._get_service = MagicMock(side_effect=RuntimeError("No sandbox"))
        request = VisualSandboxVerifyRequest(html="<p>Test</p>")
        result = await verifier.verify(request)
        assert result.success is False
        assert "unavailable" in result.error.lower()
