"""Sandbox-based visual rendering verification.

Stages visual HTML in a sandboxed browser (Playwright) and captures a screenshot
for real rendering validation. Used by VisualVerifier when verify_in_sandbox=True.

Architecture:
- Uses SandboxExecutionService to execute the 'visual_render' workload profile
- Stages HTML as index.html in /opt/wiii-visual/
- Playwright opens file:///opt/wiii-visual/index.html and captures screenshot
- Returns screenshot URL/base64 for verification

Network mode: disabled — self-contained HTML needs no network access.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VisualSandboxVerifyRequest:
    """Request for sandbox-based visual rendering verification."""

    html: str
    visual_type: str = ""
    viewport_width: int = 1024
    viewport_height: int = 768
    timeout_seconds: Optional[int] = None


@dataclass(slots=True)
class VisualSandboxVerifyResult:
    """Result from sandbox-based visual rendering verification."""

    success: bool
    screenshot_url: Optional[str] = None
    screenshot_base64: str = ""
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class VisualSandboxVerifier:
    """Verify visual output by rendering in a sandboxed browser.

    Uses the existing SandboxExecutionService with the 'visual_render' workload
    profile to stage HTML and capture a screenshot via Playwright.

    The sandbox is optional — if unavailable, verification gracefully returns
    a failure result without crashing the pipeline.
    """

    def __init__(
        self,
        service: Any = None,
    ):
        self._service = service

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        from app.sandbox.service import get_sandbox_execution_service
        self._service = get_sandbox_execution_service()
        return self._service

    async def verify(self, request: VisualSandboxVerifyRequest) -> VisualSandboxVerifyResult:
        """Render HTML in sandbox and capture screenshot.

        Returns VisualSandboxVerifyResult with screenshot URL on success,
        or error details on failure. Never raises — failures are graceful.
        """
        try:
            service = self._get_service()
        except Exception as exc:
            logger.debug("[SANDBOX-VERIFY] Service unavailable: %s", exc)
            return VisualSandboxVerifyResult(
                success=False,
                error=f"Sandbox service unavailable: {exc}",
            )

        # Stage HTML as index.html + a Playwright runner script
        runner_js = self._build_runner_script(request)
        try:
            result = await service.execute_profile(
                "visual_render",
                code=runner_js,
                files={
                    "index.html": request.html,
                    "verify_runner.mjs": runner_js,
                },
                metadata={
                    "visual_type": request.visual_type,
                    "viewport_width": request.viewport_width,
                    "viewport_height": request.viewport_height,
                },
            )
        except Exception as exc:
            logger.debug("[SANDBOX-VERIFY] Execution failed: %s", exc)
            return VisualSandboxVerifyResult(
                success=False,
                error=f"Sandbox execution failed: {exc}",
            )

        if not result.success:
            return VisualSandboxVerifyResult(
                success=False,
                error=result.error or result.stderr or "Unknown sandbox error",
                metadata=dict(result.metadata),
            )

        # Extract screenshot artifact
        screenshot_url = None
        screenshot_base64 = ""
        for artifact in result.artifacts:
            if artifact.content_type.startswith("image/"):
                screenshot_url = artifact.url
                break
            if artifact.name.endswith((".png", ".jpg", ".jpeg")):
                screenshot_url = artifact.url
                break

        return VisualSandboxVerifyResult(
            success=True,
            screenshot_url=screenshot_url,
            screenshot_base64=screenshot_base64,
            metadata=dict(result.metadata),
        )

    def _build_runner_script(self, request: VisualSandboxVerifyRequest) -> str:
        """Build Playwright runner script for screenshot capture."""
        return (
            "const { chromium } = require('playwright');\n"
            "(async () => {\n"
            "  const browser = await chromium.launch();\n"
            "  const page = await browser.newPage({\n"
            f"    viewport: {{ width: {request.viewport_width}, height: {request.viewport_height} }},\n"
            "  });\n"
            "  await page.goto('file:///opt/wiii-visual/index.html', { waitUntil: 'networkidle' });\n"
            "  await page.waitForTimeout(500);\n"
            "  await page.screenshot({ path: '/opt/wiii-visual/screenshot.png', fullPage: true });\n"
            "  await browser.close();\n"
            "})();\n"
        )
