"""Validate evidence obligations without executing live probes.

Validation is intentionally text-based and standard-library-only so it can
run in the lightweight Self-Harness workflow.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from strict_json import load_strict_json_file

from .checks import _is_positive_int
from .constants import (
    ALLOWED_DIAGNOSTIC_UPLOAD_KEYS,
    ALLOWED_FRESHNESS_KEYS,
    ALLOWED_IDENTIFIER_STRATEGIES,
    ALLOWED_PAYLOAD_CHECK_KEYS,
    ALLOWED_PAYLOAD_CHECK_WHEN_KEYS,
    ALLOWED_PROBE_SUFFIXES,
    ALLOWED_REGISTRY_KEYS,
    ALLOWED_REQUIREMENT_KEYS,
    ALLOWED_TYPESCRIPT_TEST_SUFFIXES,
    ARTIFACT_NAME_RE,
    ARTIFACT_TOKEN_RE,
    BASELINE_FORBIDDEN_PAYLOAD_TOKENS,
    DEFAULT_REGISTRY,
    DISPATCH_GATE_TOKEN_RE,
    ID_RE,
    LIVE_ENV_FLAG_RE,
    LIVE_GUARD_TOKEN_RE,
    REGISTRY_NAME,
    REGISTRY_VALIDATION_SCHEMA_VERSION,
    REPO_ROOT,
    SCHEDULE_GATE_TOKEN_RE,
    SCHEMA_RE,
    UNSUPPORTED_GATE_TOKEN_SUMMARY,
    VALID_LAYERS,
)
from .probe_checks import ProbeChecks
from .report import RegistryResult
from .workflow_artifacts import DiagnosticUploadSpec
from .workflow_checks import WorkflowChecks


class RegistryValidator(WorkflowChecks, ProbeChecks):
    def validate(self, data: dict[str, Any]) -> RegistryResult:
        self.reject_unknown_keys(
            data,
            allowed_keys=ALLOWED_REGISTRY_KEYS,
            context="registry",
        )
        if data.get("registry") != REGISTRY_NAME:
            self.error(f"registry: `registry` must be {REGISTRY_NAME!r}")
        else:
            self.pass_check()

        version = data.get("version")
        if not _is_positive_int(version):
            self.error("registry: `version` must be an integer >= 1")
        else:
            self.pass_check()

        self.require_string(data.get("description"), "description", context="registry")
        requirements = data.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            self.error("registry: `requirements` must be a non-empty list")
            requirements = []
        else:
            self.pass_check()

        seen_ids: set[str] = set()
        seen_artifacts: set[str] = set()
        seen_artifact_tokens: set[str] = set()
        for index, item in enumerate(requirements):
            self.validate_requirement(
                item,
                index=index,
                seen_ids=seen_ids,
                seen_artifacts=seen_artifacts,
                seen_artifact_tokens=seen_artifact_tokens,
            )
        self.require_registered_workflow_upload_steps(requirements)
        self.require_registered_workflow_secret_scope(requirements)
        self.require_registered_workflow_production_override_guard(requirements)

        return RegistryResult(
            validation_schema_version=REGISTRY_VALIDATION_SCHEMA_VERSION,
            registry=REGISTRY_NAME,
            registry_version=version if _is_positive_int(version) else None,
            registry_path=str(self.registry_path),
            registry_fingerprint_sha256=_registry_fingerprint(data),
            requirement_count=len(requirements),
            passed_checks=self.passed_checks,
            errors=self.errors,
        )

    def validate_requirement(
        self,
        item: Any,
        *,
        index: int,
        seen_ids: set[str],
        seen_artifacts: set[str],
        seen_artifact_tokens: set[str],
    ) -> None:
        context = f"requirements[{index}]"
        if not isinstance(item, dict):
            self.error(f"{context}: requirement must be an object")
            return
        self.reject_unknown_keys(
            item,
            allowed_keys=ALLOWED_REQUIREMENT_KEYS,
            context=context,
        )

        requirement_id = self.require_string(item.get("id"), "id", context=context)
        if requirement_id:
            context = f"requirements[{requirement_id}]"
            if not ID_RE.match(requirement_id):
                self.error(f"{context}: `id` must be lowercase kebab-case")
            elif requirement_id in seen_ids:
                self.error(f"{context}: duplicate requirement id")
            else:
                seen_ids.add(requirement_id)
                self.pass_check()

        self.require_string(item.get("title"), "title", context=context)
        layer = self.require_string(item.get("layer"), "layer", context=context)
        if layer and layer not in VALID_LAYERS:
            self.error(f"{context}: unsupported layer {layer!r}")
        elif layer:
            self.pass_check()

        artifact = self.require_string(item.get("artifact"), "artifact", context=context)
        if artifact:
            if "/" in artifact or "\\" in artifact:
                self.error(f"{context}: `artifact` must be a file name, not a path")
            elif not artifact.endswith(".json"):
                self.error(f"{context}: `artifact` must be a JSON file")
            elif not ARTIFACT_NAME_RE.match(artifact):
                self.error(
                    f"{context}: `artifact` must be a safe lowercase kebab-case JSON file name"
                )
            elif artifact in seen_artifacts:
                self.error(f"{context}: duplicate artifact name {artifact!r}")
            else:
                seen_artifacts.add(artifact)
                self.pass_check()
        schema = self.require_string(item.get("schema_version"), "schema_version", context=context)
        if schema and not SCHEMA_RE.match(schema):
            self.error(f"{context}: invalid schema_version {schema!r}")
        elif schema:
            self.pass_check()

        self.validate_freshness(item.get("freshness"), context=context)

        payload_schema_field = self.require_string(
            item.get("payload_schema_field"),
            "payload_schema_field",
            context=context,
        )
        if payload_schema_field and payload_schema_field not in {"schema", "schema_version"}:
            self.error(f"{context}: unsupported payload_schema_field {payload_schema_field!r}")
        elif payload_schema_field:
            self.pass_check()

        forbidden_payload_tokens = self.require_string_list(
            item.get("forbidden_payload_tokens"),
            "forbidden_payload_tokens",
            context=context,
        )
        self.require_baseline_forbidden_payload_tokens(
            forbidden_payload_tokens,
            context=context,
        )
        self.require_casefold_unique_forbidden_payload_tokens(
            forbidden_payload_tokens,
            context=context,
        )
        forbidden_payload_regexes = self.require_string_list_allow_empty(
            item.get("forbidden_payload_regexes"),
            "forbidden_payload_regexes",
            context=context,
        )
        self.validate_forbidden_payload_regexes(
            forbidden_payload_regexes,
            context=context,
        )
        self.validate_payload_checks(item.get("payload_checks"), context=context)
        self.require_privacy_payload_checks(item.get("payload_checks"), context=context)

        live_flags = self.require_string_list(item.get("live_env_flags"), "live_env_flags", context=context)
        self.validate_live_env_flags(live_flags, context=context)
        guard_tokens = self.require_string_list(item.get("live_guard_tokens"), "live_guard_tokens", context=context)
        self.validate_live_guard_tokens(guard_tokens, context=context)
        gate_tokens = self.require_string_list(
            item.get("dispatch_or_schedule_gate_tokens"),
            "dispatch_or_schedule_gate_tokens",
            context=context,
        )
        self.validate_dispatch_or_schedule_gate_tokens(
            gate_tokens,
            context=context,
        )
        artifact_tokens = self.require_string_list(item.get("artifact_tokens"), "artifact_tokens", context=context)
        self.validate_artifact_tokens(
            artifact_tokens,
            context=context,
            seen_artifact_tokens=seen_artifact_tokens,
            requirement_id=requirement_id,
            artifact=artifact,
        )
        diagnostic_uploads = self.validate_diagnostic_uploads(
            item.get("diagnostic_uploads"),
            context=context,
            requirement_id=requirement_id,
            seen_artifacts=seen_artifacts,
            seen_artifact_tokens=seen_artifact_tokens,
        )

        workflow_path, workflow_text = self.require_file_text(item.get("workflow"), context=f"{context}.workflow")
        probe_path, probe_text = self.require_file_text(item.get("probe"), context=f"{context}.probe")
        self.validate_probe_script_path(probe_path, context=f"{context}.probe")
        test_paths = self.require_string_list(item.get("contract_tests"), "contract_tests", context=context)
        self.require_unique_repo_path_values(
            test_paths,
            field="contract_tests",
            context=context,
        )
        for test_index, test_path in enumerate(test_paths):
            contract_test_path, _ = self.require_file_text(
                test_path,
                context=f"{context}.contract_tests[{test_index}]",
            )
            self.validate_contract_test_path(
                contract_test_path,
                context=f"{context}.contract_tests[{test_index}]",
            )

        if workflow_path and workflow_path.suffix not in {".yml", ".yaml"}:
            self.error(f"{context}.workflow: workflow must be a YAML file")
        elif workflow_path:
            self.pass_check()
        self.validate_workflow_path_location(workflow_path, context=f"{context}.workflow")

        if "pull_request_target:" in workflow_text:
            self.error(f"{context}.workflow: pull_request_target is not allowed for evidence workflows")
        elif workflow_text:
            self.pass_check()

        workflow_required = [
            "permissions:",
            "contents: read",
            "pull_request:",
            "workflow_dispatch:",
            "schedule:",
            "actions/upload-artifact@",
            "validate_runtime_evidence_artifact.py",
            str(item.get("id") or ""),
            artifact,
            *live_flags,
            *guard_tokens,
            *gate_tokens,
            *artifact_tokens,
            *[
                token
                for diagnostic_upload in diagnostic_uploads
                for token in diagnostic_upload.artifact_tokens
            ],
            *[diagnostic_upload.path for diagnostic_upload in diagnostic_uploads],
        ]
        self.require_tokens(workflow_text, workflow_required, context=f"{context}.workflow")
        self.require_workflow_top_level_key_uniqueness(
            workflow_text,
            keys=["on", "permissions", "concurrency", "jobs"],
            context=f"{context}.workflow.top_level",
        )
        self.require_workflow_event_name_uniqueness(
            workflow_text,
            context=f"{context}.workflow.events",
        )
        self.require_workflow_job_name_uniqueness(
            workflow_text,
            context=f"{context}.workflow.job_names",
        )
        self.require_tokens(
            workflow_text,
            test_paths,
            context=f"{context}.workflow.contract_tests",
        )
        self.require_workflow_contract_test_execution(
            workflow_text,
            test_paths=test_paths,
            context=f"{context}.workflow.contract_tests",
        )
        self.require_workflow_validation_binding(
            workflow_text,
            artifact=artifact,
            requirement_id=requirement_id,
            context=f"{context}.workflow.validation",
        )
        self.require_workflow_upload_binding(
            workflow_text,
            artifact=artifact,
            artifact_tokens=artifact_tokens,
            context=f"{context}.workflow.upload",
        )
        self.require_workflow_diagnostic_upload_bindings(
            workflow_text,
            specs=diagnostic_uploads,
            context=f"{context}.workflow.diagnostic_uploads",
        )
        self.require_workflow_checkout_hardening(
            workflow_text,
            context=f"{context}.workflow.checkout",
        )
        self.require_workflow_job_timeouts(
            workflow_text,
            context=f"{context}.workflow.jobs",
        )
        self.require_workflow_job_control_key_uniqueness(
            workflow_text,
            context=f"{context}.workflow.job_controls",
        )
        self.require_workflow_fail_closed_execution(
            workflow_text,
            context=f"{context}.workflow.fail_closed",
        )
        self.require_workflow_no_shell_xtrace(
            workflow_text,
            context=f"{context}.workflow.shell",
        )
        self.require_workflow_permissions_hardening(
            workflow_text,
            context=f"{context}.workflow.permissions",
        )
        self.require_workflow_concurrency_guard(
            workflow_text,
            context=f"{context}.workflow.concurrency",
        )
        self.require_workflow_gate_bindings(
            workflow_text,
            gate_tokens=gate_tokens,
            context=f"{context}.workflow.gates",
        )
        self.require_workflow_live_probe_binding(
            workflow_text,
            probe_path=str(item.get("probe") or ""),
            artifact=artifact,
            live_flags=live_flags,
            guard_tokens=guard_tokens,
            context=f"{context}.workflow.live_probe",
        )
        self.require_workflow_requirement_job_binding(
            workflow_text,
            artifact=artifact,
            artifact_tokens=artifact_tokens,
            requirement_id=requirement_id,
            probe_path=str(item.get("probe") or ""),
            live_flags=live_flags,
            guard_tokens=guard_tokens,
            context=f"{context}.workflow.requirement_job",
        )
        self.require_workflow_live_job_contract_dependency(
            workflow_text,
            artifact=artifact,
            artifact_tokens=artifact_tokens,
            requirement_id=requirement_id,
            probe_path=str(item.get("probe") or ""),
            live_flags=live_flags,
            guard_tokens=guard_tokens,
            test_paths=test_paths,
            context=f"{context}.workflow.live_contract",
        )
        self.require_workflow_live_job_gate_binding(
            workflow_text,
            artifact=artifact,
            artifact_tokens=artifact_tokens,
            requirement_id=requirement_id,
            probe_path=str(item.get("probe") or ""),
            live_flags=live_flags,
            guard_tokens=guard_tokens,
            gate_tokens=gate_tokens,
            context=f"{context}.workflow.live_gates",
        )
        self.require_workflow_live_job_environment(
            workflow_text,
            artifact=artifact,
            artifact_tokens=artifact_tokens,
            requirement_id=requirement_id,
            probe_path=str(item.get("probe") or ""),
            live_flags=live_flags,
            guard_tokens=guard_tokens,
            gate_tokens=gate_tokens,
            context=f"{context}.workflow.environment",
        )
        self.require_workflow_action_pinning(
            workflow_text,
            context=f"{context}.workflow.actions",
        )
        self.require_workflow_path_filters(
            workflow_text,
            workflow_path=str(item.get("workflow") or ""),
            probe_path=str(item.get("probe") or ""),
            test_paths=test_paths,
            context=f"{context}.workflow.paths",
        )
        self.require_workflow_runtime_evidence_output_helper_contract(
            workflow_text,
            probe_path=probe_path,
            context=f"{context}.workflow.output_helper_contract",
        )

        probe_required = [schema, *live_flags, *guard_tokens]
        self.require_tokens(probe_text, probe_required, context=f"{context}.probe")
        if probe_path and probe_path.suffix == ".py":
            self.require_python_probe_cli_guard_tokens(
                probe_text,
                guard_tokens=guard_tokens,
                context=f"{context}.probe",
            )
            self.require_python_probe_output_argument(
                probe_text,
                context=f"{context}.probe",
            )
            self.require_python_probe_output_helper_import(
                probe_text,
                context=f"{context}.probe",
            )
            self.require_python_probe_output_helper_call(
                probe_text,
                context=f"{context}.probe",
            )
            self.require_python_probe_no_raw_file_writes(
                probe_text,
                context=f"{context}.probe",
            )
            self.require_python_runtime_evidence_output_helper(
                probe_path,
                context=f"{context}.probe.output_helper",
            )
            self.require_tokens(
                workflow_text,
                ["--out"],
                context=f"{context}.workflow",
            )
        if probe_path and probe_path.suffix == ".mjs":
            self.require_mjs_probe_cli_guard_tokens(
                probe_text,
                guard_tokens=guard_tokens,
                context=f"{context}.probe",
            )
            self.require_mjs_probe_output_argument(
                probe_text,
                context=f"{context}.probe",
            )
            self.require_mjs_probe_no_raw_file_writes(
                probe_text,
                context=f"{context}.probe",
            )
            self.require_mjs_runtime_evidence_output_helper(
                probe_path,
                context=f"{context}.probe.output_helper",
            )

    def validate_diagnostic_uploads(
        self,
        value: Any,
        *,
        context: str,
        requirement_id: str,
        seen_artifacts: set[str],
        seen_artifact_tokens: set[str],
    ) -> list[DiagnosticUploadSpec]:
        if value is None:
            return []
        if not isinstance(value, list) or not value:
            self.error(f"{context}: `diagnostic_uploads` must be a non-empty list")
            return []
        self.pass_check()

        specs: list[DiagnosticUploadSpec] = []
        for index, item in enumerate(value):
            upload_context = f"{context}.diagnostic_uploads[{index}]"
            if not isinstance(item, dict):
                self.error(f"{upload_context}: diagnostic upload must be an object")
                continue
            self.reject_unknown_keys(
                item,
                allowed_keys=ALLOWED_DIAGNOSTIC_UPLOAD_KEYS,
                context=upload_context,
            )

            artifact = self.require_string(item.get("artifact"), "artifact", context=upload_context)
            artifact_valid = False
            if artifact:
                if "/" in artifact or "\\" in artifact:
                    self.error(f"{upload_context}: `artifact` must be a file name, not a path")
                elif not artifact.endswith(".json"):
                    self.error(f"{upload_context}: `artifact` must be a JSON file")
                elif not ARTIFACT_NAME_RE.match(artifact):
                    self.error(
                        f"{upload_context}: `artifact` must be a safe lowercase kebab-case JSON file name"
                    )
                elif artifact in seen_artifacts:
                    self.error(f"{upload_context}: duplicate artifact name {artifact!r}")
                else:
                    seen_artifacts.add(artifact)
                    self.pass_check()
                    artifact_valid = True

            upload_path = self.require_string(item.get("path"), "path", context=upload_context)
            normalized_path = upload_path.replace("\\", "/").strip() if upload_path else ""
            path_valid = False
            if normalized_path:
                posix_path = PurePosixPath(normalized_path)
                parts = posix_path.parts
                if (
                    Path(normalized_path).is_absolute()
                    or posix_path.is_absolute()
                    or ".." in parts
                    or not parts
                    or (parts and ":" in parts[0])
                    or any(token in normalized_path for token in ("*", "?", "[", "]", "{", "}", "$", "%"))
                ):
                    self.error(f"{upload_context}: `path` must be an explicit repo-relative JSON path")
                elif posix_path.name != artifact:
                    self.error(
                        f"{upload_context}: `path` file name must match artifact {artifact!r}"
                    )
                elif posix_path.suffix != ".json":
                    self.error(f"{upload_context}: `path` must point to a JSON file")
                else:
                    self.pass_check()
                    path_valid = True

            artifact_tokens = self.require_string_list(
                item.get("artifact_tokens"),
                "artifact_tokens",
                context=upload_context,
            )
            self.validate_artifact_tokens(
                artifact_tokens,
                context=upload_context,
                seen_artifact_tokens=seen_artifact_tokens,
                requirement_id=requirement_id,
                artifact=artifact,
            )

            if_no_files_found = self.require_string(
                item.get("if_no_files_found"),
                "if_no_files_found",
                context=upload_context,
            )
            if if_no_files_found and if_no_files_found != "warn":
                self.error(
                    f"{upload_context}: `if_no_files_found` must be 'warn' for diagnostic uploads"
                )
            elif if_no_files_found:
                self.pass_check()

            retention_days = item.get("retention_days")
            if not _is_positive_int(retention_days):
                self.error(f"{upload_context}: `retention_days` must be an integer >= 1")
            elif retention_days > 30:
                self.error(f"{upload_context}: `retention_days` must be <= 30")
            else:
                self.pass_check()

            if (
                artifact_valid
                and path_valid
                and artifact_tokens
                and if_no_files_found == "warn"
                and _is_positive_int(retention_days)
                and retention_days <= 30
            ):
                specs.append(
                    DiagnosticUploadSpec(
                        requirement_id=requirement_id,
                        artifact=artifact,
                        path=normalized_path,
                        artifact_tokens=tuple(artifact_tokens),
                        if_no_files_found=if_no_files_found,
                        retention_days=retention_days,
                    )
                )
        return specs

    def validate_artifact_tokens(
        self,
        artifact_tokens: list[str],
        *,
        context: str,
        seen_artifact_tokens: set[str],
        requirement_id: str,
        artifact: str,
    ) -> None:
        artifact_stem = artifact.removesuffix(".json")
        for token in artifact_tokens:
            if not ARTIFACT_TOKEN_RE.match(token):
                self.error(
                    f"{context}: artifact token must be lowercase kebab-case "
                    "ending with `${{ github.run_id }}`: "
                    f"{token!r}"
                )
                continue
            if token in seen_artifact_tokens:
                self.error(f"{context}: duplicate artifact token {token!r}")
                continue
            token_stem = token.removesuffix("-${{ github.run_id }}")
            if requirement_id not in token_stem and artifact_stem not in token_stem:
                self.error(
                    f"{context}: artifact token must include requirement id "
                    f"{requirement_id!r} or artifact stem {artifact_stem!r}: {token!r}"
                )
                continue
            seen_artifact_tokens.add(token)
            self.pass_check()

    def validate_workflow_path_location(self, workflow_path: Path | None, *, context: str) -> None:
        if workflow_path is None:
            return
        expected_parent = (self.repo_root / ".github" / "workflows").resolve()
        if workflow_path.parent != expected_parent:
            self.error(f"{context}: workflow must live directly under .github/workflows/")
            return
        self.pass_check()

    def validate_probe_script_path(self, probe_path: Path | None, *, context: str) -> None:
        if probe_path is None:
            return
        if probe_path.suffix not in ALLOWED_PROBE_SUFFIXES:
            suffixes = ", ".join(sorted(ALLOWED_PROBE_SUFFIXES))
            self.error(f"{context}: probe must be a script file ending in {suffixes}")
            return
        self.pass_check()

    def validate_contract_test_path(
        self,
        contract_test_path: Path | None,
        *,
        context: str,
    ) -> None:
        if contract_test_path is None:
            return
        name = contract_test_path.name
        if contract_test_path.suffix == ".py" and name.startswith("test_"):
            self.pass_check()
            return
        if name.endswith(ALLOWED_TYPESCRIPT_TEST_SUFFIXES):
            self.pass_check()
            return
        self.error(
            f"{context}: contract_tests entries must be Python `test_*.py` "
            "or TypeScript `*.test.ts`/`*.spec.ts` files"
        )

    def validate_live_env_flags(self, live_flags: list[str], *, context: str) -> None:
        for flag in live_flags:
            if not LIVE_ENV_FLAG_RE.match(flag):
                self.error(
                    f"{context}: live_env_flags entries must be uppercase "
                    f"`WIII_*` environment variables: {flag!r}"
                )
                continue
            if flag.endswith("_EVIDENCE_ENABLED"):
                self.error(
                    f"{context}: live_env_flags entries must not reuse scheduled "
                    f"evidence gate tokens: {flag!r}"
                )
                continue
            self.pass_check()

    def validate_live_guard_tokens(self, guard_tokens: list[str], *, context: str) -> None:
        for token in guard_tokens:
            if not LIVE_GUARD_TOKEN_RE.match(token):
                self.error(
                    f"{context}: live_guard_tokens entries must be explicit "
                    f"`--allow-*` lowercase kebab-case CLI flags: {token!r}"
                )
                continue
            self.pass_check()

    def validate_dispatch_or_schedule_gate_tokens(
        self,
        gate_tokens: list[str],
        *,
        context: str,
    ) -> None:
        dispatch_tokens = [
            token for token in gate_tokens if DISPATCH_GATE_TOKEN_RE.match(token)
        ]
        schedule_tokens = [
            token for token in gate_tokens if SCHEDULE_GATE_TOKEN_RE.match(token)
        ]
        recognized_tokens = set(dispatch_tokens) | set(schedule_tokens)
        unsupported_tokens = [
            token for token in gate_tokens if token not in recognized_tokens
        ]
        if unsupported_tokens:
            self.error(
                f"{context}: dispatch_or_schedule_gate_tokens contains "
                f"{UNSUPPORTED_GATE_TOKEN_SUMMARY}: {', '.join(unsupported_tokens)}"
            )
        else:
            self.pass_check()

        if len(dispatch_tokens) != 1:
            self.error(
                f"{context}: dispatch_or_schedule_gate_tokens must include exactly "
                "one workflow_dispatch input gate token starting with `allow_` or `run_`"
            )
        else:
            self.pass_check()

        if len(schedule_tokens) != 1:
            self.error(
                f"{context}: dispatch_or_schedule_gate_tokens must include exactly "
                "one scheduled vars gate token matching `WIII_*_EVIDENCE_ENABLED`"
            )
        else:
            self.pass_check()

    def require_baseline_forbidden_payload_tokens(
        self,
        forbidden_payload_tokens: list[str],
        *,
        context: str,
    ) -> None:
        missing = sorted(BASELINE_FORBIDDEN_PAYLOAD_TOKENS - set(forbidden_payload_tokens))
        if missing:
            self.error(
                f"{context}: forbidden_payload_tokens must include baseline "
                f"secret token(s): {', '.join(missing)}"
            )
        else:
            self.pass_check()

    def require_casefold_unique_forbidden_payload_tokens(
        self,
        forbidden_payload_tokens: list[str],
        *,
        context: str,
    ) -> None:
        first_seen_by_casefold: dict[str, str] = {}
        for token in forbidden_payload_tokens:
            normalized = token.casefold()
            previous = first_seen_by_casefold.get(normalized)
            if previous is not None and previous != token:
                self.error(
                    f"{context}: forbidden_payload_tokens must not contain "
                    f"case-insensitive duplicate values: {previous!r}, {token!r}"
                )
                return
            first_seen_by_casefold[normalized] = token
        self.pass_check()

    def validate_forbidden_payload_regexes(
        self,
        forbidden_payload_regexes: list[str],
        *,
        context: str,
    ) -> None:
        seen_patterns: set[str] = set()
        for pattern in forbidden_payload_regexes:
            if pattern in seen_patterns:
                self.error(f"{context}: duplicate forbidden_payload_regexes pattern {pattern!r}")
                continue
            seen_patterns.add(pattern)
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                self.error(
                    f"{context}: forbidden_payload_regexes pattern must compile: "
                    f"{pattern!r} ({exc})"
                )
                continue
            self.pass_check()

    def validate_payload_checks(self, checks: Any, *, context: str) -> None:
        if not isinstance(checks, list) or not checks:
            self.error(f"{context}: `payload_checks` must be a non-empty list")
            return
        self.pass_check()
        seen_check_keys: set[tuple[str, str, str]] = set()
        for index, check in enumerate(checks):
            check_context = f"{context}.payload_checks[{index}]"
            if not isinstance(check, dict):
                self.error(f"{check_context}: check must be an object")
                continue
            self.reject_unknown_keys(
                check,
                allowed_keys=ALLOWED_PAYLOAD_CHECK_KEYS,
                context=check_context,
            )
            path = self.require_string(check.get("path"), "path", context=check_context)
            if path:
                self.require_dot_path(
                    path,
                    "path",
                    context=check_context,
                    allow_wildcard="length_equals_path" not in check,
                )
            operation_count = sum(
                key in check for key in ("equals", "min", "sorted_equals", "length_equals_path")
            )
            if operation_count != 1:
                self.error(
                    f"{check_context}: exactly one of equals, min, sorted_equals, "
                    "or length_equals_path is required"
                )
            else:
                self.pass_check()
            if "equals" in check:
                self.require_json_scalar(
                    check.get("equals"),
                    "equals",
                    context=check_context,
                )
            if "min" in check:
                min_value = check.get("min")
                if isinstance(min_value, bool) or not isinstance(min_value, (int, float)):
                    self.error(f"{check_context}: min must be a JSON number")
                else:
                    self.pass_check()
            if "sorted_equals" in check:
                sorted_equals = check.get("sorted_equals")
                if not isinstance(sorted_equals, list):
                    self.error(f"{check_context}: sorted_equals must be a list")
                else:
                    self.pass_check()
                    for item_index, item in enumerate(sorted_equals):
                        self.require_json_scalar(
                            item,
                            f"sorted_equals[{item_index}]",
                            context=check_context,
                        )
            if "length_equals_path" in check:
                length_equals_path = self.require_string(
                    check.get("length_equals_path"),
                    "length_equals_path",
                    context=check_context,
                )
                if length_equals_path:
                    self.require_dot_path(
                        length_equals_path,
                        "length_equals_path",
                        context=check_context,
                    )
            when = check.get("when")
            operation = next(
                (
                    key
                    for key in ("equals", "min", "sorted_equals", "length_equals_path")
                    if key in check
                ),
                "",
            )
            if path and operation:
                when_key = _payload_check_when_key(when)
                check_key = (path, operation, when_key)
                if check_key in seen_check_keys:
                    self.error(
                        f"{check_context}: duplicate payload check for "
                        f"{path!r} with operation {operation!r}"
                    )
                else:
                    seen_check_keys.add(check_key)
                    self.pass_check()
            if when is None:
                continue
            if not isinstance(when, dict):
                self.error(f"{check_context}: `when` must be an object when present")
                continue
            self.reject_unknown_keys(
                when,
                allowed_keys=ALLOWED_PAYLOAD_CHECK_WHEN_KEYS,
                context=f"{check_context}.when",
            )
            when_path = self.require_string(
                when.get("path"),
                "path",
                context=f"{check_context}.when",
            )
            if when_path:
                self.require_dot_path(
                    when_path,
                    "path",
                    context=f"{check_context}.when",
                )
            when_operation_count = sum(key in when for key in ("equals", "not_equals"))
            if when_operation_count != 1:
                self.error(
                    f"{check_context}.when: exactly one of equals or not_equals is required"
                )
            else:
                self.pass_check()
                when_operation = "equals" if "equals" in when else "not_equals"
                self.require_json_scalar(
                    when.get(when_operation),
                    when_operation,
                    context=f"{check_context}.when",
                )

    def require_privacy_payload_checks(self, checks: Any, *, context: str) -> None:
        if not isinstance(checks, list):
            return
        raw_content_check_present = False
        identifier_strategy_check_present = False
        for check in checks:
            if not isinstance(check, dict):
                continue
            path = check.get("path")
            if not isinstance(path, str):
                continue
            if "raw_content_included" in path and check.get("equals") is False:
                raw_content_check_present = True
            if (
                "identifier_strategy" in path
                and check.get("equals") in ALLOWED_IDENTIFIER_STRATEGIES
            ):
                identifier_strategy_check_present = True

        if raw_content_check_present:
            self.pass_check()
        else:
            self.error(
                f"{context}: payload_checks must prove raw content absence with "
                "`raw_content_included == false`"
            )
        if identifier_strategy_check_present:
            self.pass_check()
        else:
            self.error(
                f"{context}: payload_checks must prove an allowed "
                "identifier_strategy"
            )

    def validate_freshness(self, value: Any, *, context: str) -> None:
        if not isinstance(value, dict):
            self.error(f"{context}: `freshness` must be an object")
            return
        self.pass_check()
        self.reject_unknown_keys(
            value,
            allowed_keys=ALLOWED_FRESHNESS_KEYS,
            context=f"{context}.freshness",
        )
        timestamp_path = self.require_string(
            value.get("timestamp_path"),
            "timestamp_path",
            context=f"{context}.freshness",
        )
        if timestamp_path:
            self.require_dot_path(
                timestamp_path,
                "timestamp_path",
                context=f"{context}.freshness",
            )
        max_age_hours = value.get("max_age_hours")
        if not _is_positive_int(max_age_hours):
            self.error(f"{context}.freshness: max_age_hours must be a positive integer")
        else:
            self.pass_check()


def _payload_check_when_key(when: Any) -> str:
    if not isinstance(when, dict):
        return ""
    operation = next((key for key in ("equals", "not_equals") if key in when), "")
    value = when.get(operation) if operation else None
    return json.dumps(
        {
            "path": when.get("path"),
            "operation": operation,
            "value": value,
        },
        sort_keys=True,
        ensure_ascii=True,
    )


def load_registry(path: Path) -> dict[str, Any]:
    data = load_strict_json_file(path)
    if not isinstance(data, dict):
        raise ValueError("registry root must be a JSON object")
    return data


def _registry_fingerprint(registry: dict[str, Any]) -> str:
    contract = {
        "registry": registry.get("registry"),
        "version": registry.get("version"),
        "requirements": registry.get("requirements"),
    }
    encoded = json.dumps(
        contract,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_registry(
    data: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
) -> RegistryResult:
    validator = RegistryValidator(repo_root=repo_root, registry_path=registry_path)
    return validator.validate(data)
