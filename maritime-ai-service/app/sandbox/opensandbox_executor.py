"""OpenSandbox control-plane adapter for Wiii's privileged execution layer."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import re
import shlex
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.core.generated_files import build_generated_file_url, is_allowed_generated_file, persist_generated_file
from app.core.config import Settings
from app.sandbox.base import SandboxExecutor
from app.sandbox.models import (
    SandboxArtifact,
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxNetworkMode,
    SandboxProvider,
    SandboxWorkloadKind,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenSandboxExecutionPlan:
    """Resolved Wiii-side execution plan before provider API mapping."""

    image: str
    network_mode: SandboxNetworkMode
    timeout_seconds: int
    labels: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OpenSandboxSdk:
    """Optional OpenSandbox SDK surface loaded lazily at runtime."""

    code_interpreter: Any
    connection_config: Any
    network_policy: Any
    run_command_opts: Any
    sandbox: Any
    supported_language: Any
    write_entry: Any
    search_entry: Any = None


_ARTIFACT_GLOB_PATTERNS = (
    "*.html",
    "*.htm",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.webp",
    "*.svg",
    "*.csv",
    "*.json",
    "*.xlsx",
    "*.docx",
    "*.pdf",
    "*.md",
    "*.txt",
)
_TEXT_INLINE_LIMIT = 160_000
_IMAGE_INLINE_LIMIT = 2_500_000
_MAX_HARVESTED_ARTIFACTS = 12


def _load_opensandbox_sdk() -> OpenSandboxSdk:
    """Import the optional OpenSandbox SDK only when execution is requested."""
    from code_interpreter import CodeInterpreter, SupportedLanguage
    from opensandbox.adapters.converter.sandbox_model_converter import SandboxModelConverter
    from opensandbox import Sandbox
    from opensandbox.config import ConnectionConfig
    from opensandbox.models.execd import RunCommandOpts

    try:
        from opensandbox.models.filesystem import SearchEntry, WriteEntry
    except Exception:  # pragma: no cover - fallback for older SDK exports
        from opensandbox.models import SearchEntry, WriteEntry

    try:
        from opensandbox.models.sandboxes import NetworkPolicy
    except Exception:  # pragma: no cover - fallback for older SDK exports
        from opensandbox.models import NetworkPolicy

    if not getattr(SandboxModelConverter, "_wiii_endpoint_patch", False):
        original_to_sandbox_endpoint = SandboxModelConverter.to_sandbox_endpoint

        def _patched_to_sandbox_endpoint(api_endpoint: Any) -> Any:
            endpoint = original_to_sandbox_endpoint(api_endpoint)
            endpoint_value = getattr(endpoint, "endpoint", "")
            parsed = urlparse(
                endpoint_value if "://" in endpoint_value else f"http://{endpoint_value}"
            )
            if re.fullmatch(r"/proxy/\d+", parsed.path or "") and parsed.port:
                normalized = f"host.docker.internal:{parsed.port}"
                logger.warning(
                    "Normalizing OpenSandbox direct endpoint from '%s' to '%s'",
                    endpoint_value,
                    normalized,
                )
                endpoint.endpoint = normalized
            return endpoint

        SandboxModelConverter.to_sandbox_endpoint = staticmethod(_patched_to_sandbox_endpoint)
        SandboxModelConverter._wiii_endpoint_patch = True

    return OpenSandboxSdk(
        code_interpreter=CodeInterpreter,
        connection_config=ConnectionConfig,
        network_policy=NetworkPolicy,
        run_command_opts=RunCommandOpts,
        sandbox=Sandbox,
        supported_language=SupportedLanguage,
        write_entry=WriteEntry,
        search_entry=SearchEntry,
    )


class OpenSandboxExecutor(SandboxExecutor):
    """Adapter for an external OpenSandbox deployment."""

    def __init__(
        self,
        *,
        base_url: Optional[str],
        api_key: Optional[str],
        timeout_seconds: int,
        healthcheck_path: str,
        code_template: str,
        browser_template: str,
        network_mode: SandboxNetworkMode,
        keepalive_seconds: int,
        allow_browser_workloads: bool,
    ):
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._healthcheck_path = healthcheck_path or "/health"
        self._code_template = code_template
        self._browser_template = browser_template
        self._network_mode = network_mode
        self._keepalive_seconds = keepalive_seconds
        self._allow_browser_workloads = allow_browser_workloads

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenSandboxExecutor":
        return cls(
            base_url=settings.opensandbox_base_url,
            api_key=settings.opensandbox_api_key,
            timeout_seconds=settings.sandbox_default_timeout_seconds,
            healthcheck_path=settings.opensandbox_healthcheck_path,
            code_template=settings.opensandbox_code_template,
            browser_template=settings.opensandbox_browser_template,
            network_mode=SandboxNetworkMode(settings.opensandbox_network_mode),
            keepalive_seconds=settings.opensandbox_keepalive_seconds,
            allow_browser_workloads=settings.sandbox_allow_browser_workloads,
        )

    @property
    def provider(self) -> SandboxProvider:
        return SandboxProvider.OPENSANDBOX

    def is_configured(self) -> bool:
        return bool(self._base_url)

    def select_image(self, request: SandboxExecutionRequest) -> str:
        """Select the OpenSandbox runtime image for this workload."""
        if request.runtime_template:
            return request.runtime_template
        if request.workload_kind == SandboxWorkloadKind.BROWSER:
            return self._browser_template
        return self._code_template

    def select_template(self, request: SandboxExecutionRequest) -> str:
        """Backward-compatible alias for older callers/tests."""
        return self.select_image(request)

    def build_labels(self, request: SandboxExecutionRequest) -> dict[str, str]:
        """Build stable labels for provider-side tracing and cleanup."""
        labels = {"wiii.provider": self.provider.value}
        if request.organization_id:
            labels["wiii.org"] = request.organization_id
        if request.user_id:
            labels["wiii.user"] = request.user_id
        if request.session_id:
            labels["wiii.session"] = request.session_id
        if request.request_id:
            labels["wiii.request"] = request.request_id
        labels["wiii.workload"] = request.workload_kind.value
        return labels

    def plan(self, request: SandboxExecutionRequest) -> OpenSandboxExecutionPlan:
        """Resolve Wiii policy into an OpenSandbox-facing execution plan."""
        timeout_seconds = request.timeout_seconds or self._timeout_seconds
        network_mode = request.network_mode or self._network_mode
        metadata = {
            "keepalive_seconds": self._keepalive_seconds,
            **request.metadata,
        }
        return OpenSandboxExecutionPlan(
            image=self.select_image(request),
            network_mode=network_mode,
            timeout_seconds=timeout_seconds,
            labels=self.build_labels(request),
            metadata=metadata,
        )

    def build_network_policy(
        self,
        network_mode: SandboxNetworkMode,
        network_policy_cls: Any,
    ) -> Any:
        """Translate Wiii's coarse network policy into an OpenSandbox policy."""
        if network_mode == SandboxNetworkMode.DISABLED:
            return network_policy_cls(defaultAction="deny", egress=[])
        return None

    def build_connection_config(self, timeout_seconds: int, sdk: OpenSandboxSdk) -> Any:
        """Create an SDK connection config from the configured base URL."""
        parsed = urlparse(self._base_url)
        protocol = parsed.scheme or "http"
        request_timeout = timedelta(seconds=max(timeout_seconds + 10, 30))
        return sdk.connection_config(
            api_key=self._api_key,
            domain=self._base_url,
            protocol=protocol,
            request_timeout=request_timeout,
            use_server_proxy=False,
        )

    def build_provider_metadata(
        self,
        plan: OpenSandboxExecutionPlan,
        request: SandboxExecutionRequest,
    ) -> dict[str, Any]:
        """Expose provider plan details alongside execution results."""
        metadata = dict(request.metadata or {})
        metadata.update({
            "provider": self.provider.value,
            "planned_image": plan.image,
            "planned_template": plan.image,
            "planned_network_mode": plan.network_mode.value,
            "planned_timeout_seconds": plan.timeout_seconds,
            "planned_workload_kind": request.workload_kind.value,
            "labels": plan.labels,
        })
        if request.organization_id:
            metadata.setdefault("organization_id", request.organization_id)
        if request.user_id:
            metadata.setdefault("user_id", request.user_id)
        if request.session_id:
            metadata.setdefault("session_id", request.session_id)
        if request.request_id:
            metadata.setdefault("request_id", request.request_id)
        return metadata

    def build_sandbox_metadata(
        self,
        plan: OpenSandboxExecutionPlan,
    ) -> dict[str, str]:
        """Serialize labels and metadata for sandbox-side tracing."""
        metadata = {
            key: self.to_label_safe_value(value)
            for key, value in {
                **plan.labels,
                "wiii.image": plan.image,
                "wiii.template": plan.image,
                "wiii.network_mode": plan.network_mode.value,
            }.items()
        }
        for key, value in plan.metadata.items():
            if value is None:
                continue
            metadata[f"wiii.meta.{key}"] = self.to_label_safe_value(value)
        return metadata

    def stringify_metadata_value(self, value: Any) -> str:
        """Normalize metadata values into provider-safe strings."""
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(value, ensure_ascii=True, sort_keys=True)

    def to_label_safe_value(self, value: Any) -> str:
        """Normalize metadata into a safe token for OpenSandbox server labels."""
        text = self.stringify_metadata_value(value).strip()
        if not text:
            return "empty"

        normalized = text.lower()
        normalized = re.sub(r"[^a-z0-9._-]+", "-", normalized)
        normalized = re.sub(r"-{2,}", "-", normalized).strip("-.")

        if normalized and len(normalized) <= 63:
            return normalized

        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
        prefix = normalized[:48].rstrip("-.") if normalized else "meta"
        prefix = prefix or "meta"
        return f"{prefix}-{digest}"[:63].rstrip("-.")

    def prepare_code(self, request: SandboxExecutionRequest) -> str:
        """Inject provider-managed setup before user code when needed."""
        code = request.code or ""
        if not request.working_directory:
            return code
        working_directory = json.dumps(request.working_directory, ensure_ascii=True)
        return (
            "import os as __wiii_os\n"
            f"__wiii_os.chdir({working_directory})\n"
            "del __wiii_os\n\n"
            f"{code}"
        )

    def build_command_text(self, request: SandboxExecutionRequest) -> str:
        """Serialize a command workload into the shell string expected by SDK."""
        if not request.command:
            raise ValueError("OpenSandbox command/browser workloads require a command.")
        return shlex.join(str(part) for part in request.command)

    async def healthcheck(self) -> bool:
        """Probe the OpenSandbox control plane with a simple HTTP GET."""
        if not self.is_configured():
            return False

        path = self._healthcheck_path
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{self._base_url}{path}"
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=headers)
            return 200 <= response.status_code < 300
        except Exception as exc:
            logger.debug("[OPENSANDBOX] healthcheck failed: %s", exc)
            return False

    async def execute(
        self,
        request: SandboxExecutionRequest,
    ) -> SandboxExecutionResult:
        """Run a workload inside OpenSandbox."""
        plan = self.plan(request)
        provider_metadata = self.build_provider_metadata(plan, request)

        if not self.is_configured():
            return SandboxExecutionResult(
                success=False,
                error="OpenSandbox executor is not configured.",
                metadata=provider_metadata,
            )

        if request.workload_kind == SandboxWorkloadKind.BROWSER and not self._allow_browser_workloads:
            return SandboxExecutionResult(
                success=False,
                error="Browser workloads are not enabled for OpenSandbox in this deployment.",
                metadata=provider_metadata,
            )

        try:
            sdk = _load_opensandbox_sdk()
        except ImportError as exc:
            return SandboxExecutionResult(
                success=False,
                error=(
                    "OpenSandbox SDK is not installed. Install 'opensandbox' and "
                    "'opensandbox-code-interpreter' to enable remote execution."
                ),
                metadata={
                    **provider_metadata,
                    "dependency_error": str(exc),
                },
            )

        validation_error = self.validate_request(request)
        if validation_error:
            return SandboxExecutionResult(
                success=False,
                error=validation_error,
                metadata=provider_metadata,
            )

        sandbox = None
        try:
            sandbox = await self.create_sandbox(
                plan=plan,
                request=request,
                sdk=sdk,
            )
            await self.stage_files(
                sandbox=sandbox,
                request=request,
                sdk=sdk,
            )

            if request.workload_kind == SandboxWorkloadKind.PYTHON:
                execution = await self.execute_python_workload(
                    sandbox=sandbox,
                    request=request,
                    plan=plan,
                    sdk=sdk,
                )
            elif request.workload_kind in (
                SandboxWorkloadKind.COMMAND,
                SandboxWorkloadKind.BROWSER,
            ):
                execution = await self.execute_command_workload(
                    sandbox=sandbox,
                    request=request,
                    plan=plan,
                    sdk=sdk,
                )
            else:
                return SandboxExecutionResult(
                    success=False,
                    error=(
                        f"OpenSandbox does not support workload kind "
                        f"'{request.workload_kind.value}'."
                    ),
                    metadata=provider_metadata,
                )

            return await self.build_execution_result(
                execution=execution,
                sandbox=sandbox,
                request=request,
                sdk=sdk,
                sandbox_id=sandbox.id,
                provider_metadata=provider_metadata,
            )
        except asyncio.TimeoutError:
            return SandboxExecutionResult(
                success=False,
                error=f"OpenSandbox execution timed out after {plan.timeout_seconds}s.",
                exit_code=124,
                sandbox_id=getattr(sandbox, "id", None),
                metadata=provider_metadata,
            )
        except Exception as exc:
            logger.error("[OPENSANDBOX] execution failed: %s", exc, exc_info=True)
            return SandboxExecutionResult(
                success=False,
                error=f"OpenSandbox execution failed: {exc}",
                sandbox_id=getattr(sandbox, "id", None),
                metadata=provider_metadata,
            )
        finally:
            await self.cleanup_sandbox(sandbox)

    def validate_request(self, request: SandboxExecutionRequest) -> Optional[str]:
        """Fail early on unsupported or incomplete workload requests."""
        if request.workload_kind == SandboxWorkloadKind.PYTHON:
            if not (request.code or "").strip():
                return "OpenSandbox python execution requires non-empty code."
            return None

        if request.workload_kind in (
            SandboxWorkloadKind.COMMAND,
            SandboxWorkloadKind.BROWSER,
        ):
            if not request.command:
                return "OpenSandbox command/browser workloads require a command."
            return None

        return None

    async def create_sandbox(
        self,
        *,
        plan: OpenSandboxExecutionPlan,
        request: SandboxExecutionRequest,
        sdk: OpenSandboxSdk,
    ) -> Any:
        """Provision the remote sandbox instance for the workload."""
        return await sdk.sandbox.create(
            plan.image,
            timeout=timedelta(seconds=max(plan.timeout_seconds + 60, 120)),
            ready_timeout=timedelta(seconds=max(min(plan.timeout_seconds, 300), 90)),
            env=request.env or None,
            metadata=self.build_sandbox_metadata(plan),
            network_policy=self.build_network_policy(
                plan.network_mode,
                sdk.network_policy,
            ),
            connection_config=self.build_connection_config(
                plan.timeout_seconds,
                sdk,
            ),
        )

    async def stage_files(
        self,
        *,
        sandbox: Any,
        request: SandboxExecutionRequest,
        sdk: OpenSandboxSdk,
    ) -> None:
        """Write requested files into the sandbox before execution."""
        if not request.files:
            return
        await sandbox.files.write_files(
            [
                sdk.write_entry(path=path, data=content, mode=644)
                for path, content in request.files.items()
            ]
        )

    async def execute_python_workload(
        self,
        *,
        sandbox: Any,
        request: SandboxExecutionRequest,
        plan: OpenSandboxExecutionPlan,
        sdk: OpenSandboxSdk,
    ) -> Any:
        """Run Python as a sandboxed script for broad image compatibility."""
        script_path = "/tmp/wiii_exec.py"
        await sandbox.files.write_files(
            [
                sdk.write_entry(
                    path=script_path,
                    data=self.prepare_code(request),
                    mode=0o644,
                )
            ]
        )
        working_directory = request.working_directory or "/workspace"
        command = (
            f"mkdir -p {shlex.quote(working_directory)} && "
            f"cd {shlex.quote(working_directory)} && "
            f"python {shlex.quote(script_path)}"
        )
        opts = sdk.run_command_opts(
            timeout=timedelta(seconds=plan.timeout_seconds),
        )
        return await sandbox.commands.run(command, opts=opts)

    async def execute_command_workload(
        self,
        *,
        sandbox: Any,
        request: SandboxExecutionRequest,
        plan: OpenSandboxExecutionPlan,
        sdk: OpenSandboxSdk,
    ) -> Any:
        """Run a shell command workload through the lower-level command surface."""
        opts = sdk.run_command_opts(
            timeout=timedelta(seconds=plan.timeout_seconds),
            working_directory=request.working_directory,
        )
        return await sandbox.commands.run(
            self.build_command_text(request),
            opts=opts,
        )

    async def build_execution_result(
        self,
        *,
        execution: Any,
        sandbox: Any,
        request: SandboxExecutionRequest,
        sdk: OpenSandboxSdk,
        sandbox_id: Optional[str],
        provider_metadata: dict[str, Any],
    ) -> SandboxExecutionResult:
        """Normalize the SDK execution model into Wiii's provider-neutral result."""
        stdout = "".join(
            message.text
            for message in getattr(execution.logs, "stdout", [])
            if message.text
        ).strip()
        stderr = "".join(
            message.text
            for message in getattr(execution.logs, "stderr", [])
            if message.text
        ).strip()
        result_text = "\n".join(
            item.text
            for item in getattr(execution, "result", [])
            if getattr(item, "text", None)
        ).strip()

        error = getattr(execution, "error", None)
        success = error is None
        exit_code = 0 if success else 1
        artifacts = await self.collect_artifacts(
            execution=execution,
            sandbox=sandbox,
            request=request,
            sdk=sdk,
        )

        if result_text:
            stdout = "\n".join(
                part for part in [stdout, result_text] if part
            ).strip()

        if error is not None:
            error_lines = [f"{error.name}: {error.value}"]
            traceback_lines = [
                line for line in getattr(error, "traceback", []) if line
            ]
            if traceback_lines:
                error_lines.extend(traceback_lines)
            stderr = "\n".join(
                part for part in [stderr, "\n".join(error_lines)] if part
            ).strip()

        return SandboxExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            error=None if success else f"{error.name}: {error.value}",
            sandbox_id=sandbox_id,
            artifacts=artifacts,
            metadata={
                **provider_metadata,
                "sandbox_id": sandbox_id,
                "execution_id": getattr(execution, "id", None),
                "artifact_count": len(artifacts),
            },
        )

    async def collect_artifacts(
        self,
        *,
        execution: Any,
        sandbox: Any,
        request: SandboxExecutionRequest,
        sdk: OpenSandboxSdk,
    ) -> list[SandboxArtifact]:
        """Harvest explicit execution artifacts plus generated sandbox files."""
        artifacts: list[SandboxArtifact] = []
        seen_keys: set[tuple[str, str]] = set()

        def _add_artifact(item: Optional[SandboxArtifact]) -> None:
            if item is None:
                return
            key = (
                (item.path or item.url or item.name).lower(),
                (item.content_type or "").lower(),
            )
            if key in seen_keys:
                return
            seen_keys.add(key)
            artifacts.append(item)

        for candidate in self._extract_execution_artifacts(execution):
            _add_artifact(candidate)
            if len(artifacts) >= _MAX_HARVESTED_ARTIFACTS:
                return artifacts

        for candidate in await self._harvest_sandbox_files(
            sandbox=sandbox,
            request=request,
            sdk=sdk,
        ):
            _add_artifact(candidate)
            if len(artifacts) >= _MAX_HARVESTED_ARTIFACTS:
                break

        return artifacts

    def _extract_execution_artifacts(
        self,
        execution: Any,
    ) -> list[SandboxArtifact]:
        """Best-effort extraction from provider execution payloads."""
        artifacts: list[SandboxArtifact] = []
        for attr_name in ("artifacts", "files", "outputs", "result"):
            value = getattr(execution, attr_name, None)
            if not value or not isinstance(value, list):
                continue
            for item in value:
                artifact = self._coerce_execution_artifact(item)
                if artifact is not None:
                    artifacts.append(artifact)
        return artifacts

    def _coerce_execution_artifact(self, item: Any) -> Optional[SandboxArtifact]:
        """Normalize loose SDK artifact objects into Wiii sandbox artifacts."""
        path = self._read_field(item, "path", "file_path")
        name = self._read_field(item, "name", "filename")
        url = self._read_field(item, "url", "download_url")
        content_type = (
            self._read_field(item, "content_type", "mime_type")
            or self._guess_content_type(path or name or url)
        )
        inline_content = self._read_field(item, "content", "data", "body", "bytes")

        if not any([path, name, url, inline_content]):
            return None
        if inline_content is None and not any([path, name, url]):
            return None

        normalized_name = name or self._filename_from_ref(path or url) or "artifact"
        artifact = SandboxArtifact(
            name=normalized_name,
            content_type=content_type or "application/octet-stream",
            url=str(url) if url else None,
            path=str(path) if path else None,
            metadata={
                "harvest_source": "execution_payload",
            },
        )

        self._attach_inline_content(artifact, inline_content, normalized_name)
        size_bytes = self._read_field(item, "size", "size_bytes")
        if size_bytes is not None:
            artifact.metadata["size_bytes"] = size_bytes
        return artifact

    async def _harvest_sandbox_files(
        self,
        *,
        sandbox: Any,
        request: SandboxExecutionRequest,
        sdk: OpenSandboxSdk,
    ) -> list[SandboxArtifact]:
        """Search common execution directories for user-visible generated files."""
        files_api = getattr(sandbox, "files", None)
        if files_api is None or not hasattr(files_api, "search"):
            return []

        staged_paths = {self._normalize_path(path) for path in request.files}
        roots = self._build_search_roots(request.working_directory)
        discovered: list[SandboxArtifact] = []
        seen_paths: set[str] = set()

        for root in roots:
            for pattern in _ARTIFACT_GLOB_PATTERNS:
                if len(discovered) >= _MAX_HARVESTED_ARTIFACTS:
                    return discovered
                try:
                    results = await files_api.search(
                        self._build_search_entry(root, pattern, sdk)
                    )
                except Exception as exc:
                    logger.debug(
                        "[OPENSANDBOX] artifact search failed for %s %s: %s",
                        root,
                        pattern,
                        exc,
                    )
                    continue

                for entry in results or []:
                    path = self._normalize_path(
                        self._read_field(entry, "path", "file_path")
                    )
                    if not path or path in staged_paths or path in seen_paths:
                        continue
                    seen_paths.add(path)
                    artifact = await self._build_sandbox_file_artifact(
                        files_api=files_api,
                        path=path,
                    )
                    if artifact is not None:
                        discovered.append(artifact)
                        if len(discovered) >= _MAX_HARVESTED_ARTIFACTS:
                            return discovered

        return discovered

    async def _build_sandbox_file_artifact(
        self,
        *,
        files_api: Any,
        path: str,
    ) -> Optional[SandboxArtifact]:
        """Create an artifact record from a sandbox-side file path."""
        content_type = self._guess_content_type(path)
        artifact = SandboxArtifact(
            name=self._filename_from_ref(path) or "artifact",
            content_type=content_type,
            path=path,
            metadata={
                "harvest_source": "sandbox_filesystem",
                "sandbox_path": path,
            },
        )

        raw_content = await self._read_sandbox_file_content(
            files_api=files_api,
            path=path,
        )

        published = self._publish_harvested_file(
            artifact.name,
            raw_content,
        )
        if published is not None:
            artifact.path = str(published)
            artifact.url = build_generated_file_url(published.name)
            artifact.metadata["published_from_sandbox"] = True

        if self._should_inline_file(content_type, path):
            self._attach_inline_content(artifact, raw_content, artifact.name)

        return artifact

    async def _read_sandbox_file_content(
        self,
        *,
        files_api: Any,
        path: str,
    ) -> Any:
        """Read a sandbox file using the most binary-safe API available."""
        if hasattr(files_api, "read_bytes"):
            try:
                return await files_api.read_bytes(path)
            except Exception as exc:
                logger.debug(
                    "[OPENSANDBOX] artifact read_bytes failed for %s: %s",
                    path,
                    exc,
                )

        if hasattr(files_api, "read_file"):
            try:
                return await files_api.read_file(path)
            except Exception as exc:
                logger.debug(
                    "[OPENSANDBOX] artifact read_file failed for %s: %s",
                    path,
                    exc,
                )

        return None

    def _publish_harvested_file(
        self,
        filename: str,
        raw_content: Any,
    ) -> Optional[Path]:
        """Persist a harvested sandbox file into Wiii's generated workspace."""
        if raw_content is None or not is_allowed_generated_file(filename):
            return None
        if isinstance(raw_content, str):
            return persist_generated_file(filename, raw_content, prefix="sandbox")
        if isinstance(raw_content, (bytes, bytearray)):
            return persist_generated_file(filename, bytes(raw_content), prefix="sandbox")
        return None

    def _build_search_roots(self, working_directory: Optional[str]) -> list[str]:
        roots: list[str] = []
        for candidate in (working_directory, "/workspace", "/tmp"):
            normalized = self._normalize_path(candidate)
            if normalized and normalized not in roots:
                roots.append(normalized)
        return roots

    def _build_search_entry(
        self,
        path: str,
        pattern: str,
        sdk: OpenSandboxSdk,
    ) -> Any:
        search_entry_cls = getattr(sdk, "search_entry", None)
        if search_entry_cls is None:
            return {"path": path, "pattern": pattern}
        for kwargs in (
            {"path": path, "pattern": pattern, "recursive": True},
            {"path": path, "pattern": pattern},
        ):
            try:
                return search_entry_cls(**kwargs)
            except TypeError:
                continue
        return search_entry_cls(path=path, pattern=pattern)

    def _attach_inline_content(
        self,
        artifact: SandboxArtifact,
        raw_content: Any,
        fallback_name: str,
    ) -> None:
        """Attach inline text/base64 content when it is useful and safe."""
        if raw_content is None:
            return

        content_type = artifact.content_type or self._guess_content_type(fallback_name)
        if self._is_image_content(content_type):
            encoded = self._encode_inline_image(raw_content)
            if encoded:
                artifact.metadata["inline_content"] = encoded
                artifact.metadata["inline_encoding"] = "base64"
            return

        text = self._coerce_text_content(raw_content)
        if text is None:
            return

        if len(text) > _TEXT_INLINE_LIMIT:
            artifact.metadata["inline_content"] = text[:_TEXT_INLINE_LIMIT]
            artifact.metadata["content_truncated"] = True
        else:
            artifact.metadata["inline_content"] = text
        artifact.metadata["inline_encoding"] = "text"

    def _coerce_text_content(self, raw_content: Any) -> Optional[str]:
        if raw_content is None:
            return None
        if isinstance(raw_content, str):
            return raw_content
        if isinstance(raw_content, (bytes, bytearray)):
            try:
                return bytes(raw_content).decode("utf-8")
            except UnicodeDecodeError:
                return None
        return None

    def _encode_inline_image(self, raw_content: Any) -> Optional[str]:
        if raw_content is None:
            return None
        if isinstance(raw_content, str):
            return raw_content if len(raw_content) <= _IMAGE_INLINE_LIMIT else None
        if isinstance(raw_content, (bytes, bytearray)):
            if len(raw_content) > _IMAGE_INLINE_LIMIT:
                return None
            return base64.b64encode(bytes(raw_content)).decode("ascii")
        return None

    def _guess_content_type(self, ref: Optional[str]) -> str:
        guessed, _ = mimetypes.guess_type(ref or "")
        return guessed or "application/octet-stream"

    def _filename_from_ref(self, ref: Optional[str]) -> Optional[str]:
        if not ref:
            return None
        try:
            return PurePosixPath(str(ref)).name or None
        except Exception:
            return str(ref).rsplit("/", 1)[-1] or None

    def _normalize_path(self, value: Optional[str]) -> str:
        if not value:
            return ""
        return str(PurePosixPath(str(value)))

    def _read_field(self, item: Any, *names: str) -> Any:
        if isinstance(item, dict):
            for name in names:
                if name in item:
                    return item[name]
            return None

        for name in names:
            if hasattr(item, name):
                return getattr(item, name)
        return None

    def _should_inline_file(self, content_type: str, path: str) -> bool:
        if self._is_image_content(content_type):
            return True
        return (
            content_type.startswith("text/")
            or content_type in {
                "application/json",
                "text/csv",
                "application/csv",
                "image/svg+xml",
            }
            or PurePosixPath(path).suffix.lower() in {
                ".html",
                ".htm",
                ".md",
                ".txt",
                ".json",
                ".csv",
                ".svg",
            }
        )

    def _is_image_content(self, content_type: str) -> bool:
        return content_type.startswith("image/") and content_type != "image/svg+xml"

    async def cleanup_sandbox(self, sandbox: Any) -> None:
        """Terminate remote sandbox resources and close local SDK transports."""
        if sandbox is None:
            return

        try:
            await sandbox.kill()
        except Exception as exc:
            logger.warning(
                "[OPENSANDBOX] failed to terminate sandbox %s: %s",
                getattr(sandbox, "id", None),
                exc,
            )

        try:
            await sandbox.close()
        except Exception as exc:
            logger.warning(
                "[OPENSANDBOX] failed to close sandbox %s: %s",
                getattr(sandbox, "id", None),
                exc,
            )
