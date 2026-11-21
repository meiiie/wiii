"""Validate registered workflows against evidence policy."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from .checks import (
    ValidationChecks,
    _is_positive_int,
)
from .constants import (
    ALLOWED_ACTION_NAMES,
    EXPECTED_CONCURRENCY_CANCEL,
    EXPECTED_CONCURRENCY_GROUP,
    EXPECTED_LIVE_EVIDENCE_ENVIRONMENT,
    PINNED_ACTION_REF_RE,
    PRODUCTION_OVERRIDE_DUPLICATE_INPUT_FIELD_MESSAGE,
    PRODUCTION_OVERRIDE_ENV,
    PRODUCTION_OVERRIDE_FLAG,
    PRODUCTION_OVERRIDE_INPUT,
    PRODUCTION_OVERRIDE_REQUIRED,
)
from .python_probe import _probe_supports_production_override
from .workflow_artifacts import (
    DiagnosticUploadSpec,
    _workflow_job_has_bound_validation_upload,
    _workflow_job_has_diagnostic_validation_upload_order,
    _workflow_job_has_expected_uploads,
    _workflow_job_has_probe_validation_upload_order,
    _workflow_job_validation_expected_upload_paths,
    _workflow_secret_job_matches_registered_requirement,
    _workflow_upload_artifact_blocks,
    _workflow_upload_artifact_paths,
    _workflow_upload_artifact_retention_days,
    _workflow_upload_block_binds_artifact_path,
    _workflow_upload_block_has_artifact_token,
    _workflow_upload_paths_are_narrow_json,
    _workflow_upload_paths_match_expected,
    _workflow_upload_with_block,
    _workflow_upload_with_scalar_field_equals,
    _workflow_validation_command_matches,
    _workflow_validator_commands,
)
from .workflow_commands import (
    _workflow_command_enables_shell_xtrace,
    _workflow_contract_job_checks_out_before_test,
    _workflow_contract_job_runs_test,
    _workflow_job_checks_out_before_probe,
    _workflow_probe_block_has_guard,
    _workflow_probe_block_writes_artifact,
    _workflow_probe_blocks_have_guards,
    _workflow_probe_invocation_blocks,
    _workflow_run_block_starts_with_strict_shell,
    _workflow_run_command_lines,
    _workflow_runs_contract_test,
)
from .workflow_gates import (
    _workflow_has_job_if_gate,
    _workflow_job_if_matches_any_dispatch_or_schedule_gate_pair,
    _workflow_job_if_matches_dispatch_or_schedule_gates,
    _workflow_production_override_env_is_manual_only,
    _workflow_production_override_flag_steps_bind_env,
    _workflow_production_override_flag_steps_invoke_registered_probe,
    _workflow_production_override_flag_steps_pass_args_to_probe,
    _workflow_production_override_flags_are_guarded,
    _workflow_production_override_registered_probe_steps_pass_args,
    _workflow_text_references_secrets,
)
from .workflow_structure import (
    _workflow_block_duplicate_direct_fields,
    _workflow_block_has_duplicate_env_flag,
    _workflow_block_sets_env_flag,
    _workflow_block_sets_unique_env_flag,
    _workflow_checkout_block_disables_persisted_credentials,
    _workflow_checkout_blocks,
    _workflow_contract_job_is_unconditional,
    _workflow_dispatch_duplicate_input_names,
    _workflow_dispatch_input_block,
    _workflow_dispatch_input_duplicate_fields,
    _workflow_dispatch_input_is_boolean_default_false,
    _workflow_duplicate_event_names,
    _workflow_duplicate_job_names,
    _workflow_event_duplicate_direct_fields,
    _workflow_event_filter_values,
    _workflow_event_has_direct_field,
    _workflow_event_paths,
    _workflow_job_blocks,
    _workflow_job_direct_scalar_values,
    _workflow_job_duplicate_direct_fields,
    _workflow_job_needs_contract,
    _workflow_mapping_duplicate_direct_fields,
    _workflow_step_blocks,
    _workflow_step_scalar_field_equals,
    _workflow_text_before_jobs,
    _workflow_top_level_block,
    _workflow_top_level_key_count,
    _workflow_uses_refs,
)


class WorkflowChecks(ValidationChecks):
    def require_workflow_validation_binding(
        self,
        workflow_text: str,
        *,
        artifact: str,
        requirement_id: str,
        context: str,
    ) -> None:
        commands = _workflow_validator_commands(workflow_text)
        if not commands:
            self.error(f"{context}: missing validate_runtime_evidence_artifact.py command")
            return
        for command in commands:
            if _workflow_validation_command_matches(
                command,
                artifact=artifact,
                requirement_id=requirement_id,
            ):
                self.pass_check()
                return
        self.error(
            f"{context}: validate_runtime_evidence_artifact.py must validate "
            f"{artifact!r} with --requirement-id {requirement_id!r}"
        )

    def require_workflow_top_level_key_uniqueness(
        self,
        workflow_text: str,
        *,
        keys: list[str],
        context: str,
    ) -> None:
        for key in keys:
            count = _workflow_top_level_key_count(workflow_text, key)
            if count > 1:
                self.error(f"{context}: duplicate top-level `{key}` key")
            else:
                self.pass_check()

    def require_workflow_job_name_uniqueness(
        self,
        workflow_text: str,
        *,
        context: str,
    ) -> None:
        duplicate_names = _workflow_duplicate_job_names(workflow_text)
        if duplicate_names:
            rendered = ", ".join(duplicate_names)
            self.error(f"{context}: duplicate workflow job id(s): {rendered}")
        else:
            self.pass_check()

    def require_workflow_event_name_uniqueness(
        self,
        workflow_text: str,
        *,
        context: str,
    ) -> None:
        duplicate_names = _workflow_duplicate_event_names(workflow_text)
        if duplicate_names:
            rendered = ", ".join(duplicate_names)
            self.error(f"{context}: duplicate workflow event name(s): {rendered}")
        else:
            self.pass_check()

    def require_workflow_upload_binding(
        self,
        workflow_text: str,
        *,
        artifact: str,
        artifact_tokens: list[str],
        context: str,
    ) -> None:
        upload_blocks = _workflow_upload_artifact_blocks(workflow_text)
        if not upload_blocks:
            self.error(f"{context}: missing actions/upload-artifact step")
            return
        for token in artifact_tokens:
            matching_blocks = [
                block
                for block in upload_blocks
                if _workflow_upload_block_has_artifact_token(block, token)
            ]
            if not matching_blocks:
                self.error(
                    f"{context}: upload-artifact step must bind artifact token "
                    f"{token!r} to uploaded path {artifact!r}"
                )
                continue
            self.pass_check()
            for block in matching_blocks:
                duplicate_step_fields = _workflow_block_duplicate_direct_fields(
                    block,
                    ["uses", "if", "with"],
                )
                if duplicate_step_fields:
                    rendered = ", ".join(duplicate_step_fields)
                    self.error(
                        f"{context}: upload-artifact step for {token!r} must not "
                        f"duplicate step field(s): {rendered}"
                    )
                duplicate_with_fields = _workflow_mapping_duplicate_direct_fields(
                    _workflow_upload_with_block(block),
                    ["name", "path", "if-no-files-found", "retention-days"],
                )
                if duplicate_with_fields:
                    rendered = ", ".join(duplicate_with_fields)
                    self.error(
                        f"{context}: upload-artifact step for {token!r} must not "
                        f"duplicate with field(s): {rendered}"
                    )
                if _workflow_step_scalar_field_equals(block, "if", "always()"):
                    self.pass_check()
                else:
                    self.error(
                        f"{context}: upload-artifact step for {token!r} must use "
                        "if: always()"
                    )
                if _workflow_upload_with_scalar_field_equals(
                    block,
                    "if-no-files-found",
                    "error",
                ):
                    self.pass_check()
                else:
                    self.error(
                        f"{context}: upload-artifact step for {token!r} must use "
                        "if-no-files-found: error"
                    )
                retention_days = _workflow_upload_artifact_retention_days(block)
                if retention_days is None:
                    self.error(
                        f"{context}: upload-artifact step for {token!r} must set "
                        "retention-days"
                    )
                    continue
                if retention_days <= 0 or retention_days > 90:
                    self.error(
                        f"{context}: upload-artifact retention-days for {token!r} "
                        "must be between 1 and 90"
                    )
                else:
                    self.pass_check()
                upload_paths = _workflow_upload_artifact_paths(block)
                if not upload_paths:
                    self.error(
                        f"{context}: upload-artifact step for {token!r} must set "
                        "explicit JSON path(s)"
                    )
                elif _workflow_upload_paths_are_narrow_json(upload_paths, artifact):
                    self.pass_check()
                else:
                    self.error(
                        f"{context}: upload-artifact step for {token!r} must "
                        "upload exactly one explicit JSON evidence file named "
                        f"{artifact!r}"
                    )

    def require_workflow_diagnostic_upload_bindings(
        self,
        workflow_text: str,
        *,
        specs: list[DiagnosticUploadSpec],
        context: str,
    ) -> None:
        if not specs:
            return
        upload_blocks = _workflow_upload_artifact_blocks(workflow_text)
        for spec in specs:
            spec_context = f"{context}[{spec.artifact}]"
            if any(
                _workflow_job_has_diagnostic_validation_upload_order(
                    job_block,
                    spec=spec,
                )
                for _job_name, job_block in _workflow_job_blocks(workflow_text)
            ):
                self.pass_check()
            else:
                self.error(
                    f"{spec_context}: diagnostic upload workflow must validate "
                    "and clean up preflight JSON before upload in the same job"
                )
            for token in spec.artifact_tokens:
                matching_blocks = [
                    block
                    for block in upload_blocks
                    if _workflow_upload_block_has_artifact_token(block, token)
                ]
                if not matching_blocks:
                    self.error(
                        f"{spec_context}: upload-artifact step must bind diagnostic "
                        f"artifact token {token!r} to uploaded path {spec.path!r}"
                    )
                    continue
                self.pass_check()
                for block in matching_blocks:
                    duplicate_step_fields = _workflow_block_duplicate_direct_fields(
                        block,
                        ["uses", "if", "with"],
                    )
                    if duplicate_step_fields:
                        rendered = ", ".join(duplicate_step_fields)
                        self.error(
                            f"{spec_context}: upload-artifact step for {token!r} "
                            f"must not duplicate step field(s): {rendered}"
                        )
                    duplicate_with_fields = _workflow_mapping_duplicate_direct_fields(
                        _workflow_upload_with_block(block),
                        ["name", "path", "if-no-files-found", "retention-days"],
                    )
                    if duplicate_with_fields:
                        rendered = ", ".join(duplicate_with_fields)
                        self.error(
                            f"{spec_context}: upload-artifact step for {token!r} "
                            f"must not duplicate with field(s): {rendered}"
                        )
                    if _workflow_step_scalar_field_equals(block, "if", "always()"):
                        self.pass_check()
                    else:
                        self.error(
                            f"{spec_context}: upload-artifact step for {token!r} "
                            "must use if: always()"
                        )
                    if _workflow_upload_with_scalar_field_equals(
                        block,
                        "if-no-files-found",
                        spec.if_no_files_found,
                    ):
                        self.pass_check()
                    else:
                        self.error(
                            f"{spec_context}: upload-artifact step for {token!r} "
                            f"must use if-no-files-found: {spec.if_no_files_found}"
                        )
                    retention_days = _workflow_upload_artifact_retention_days(block)
                    if retention_days == spec.retention_days:
                        self.pass_check()
                    else:
                        self.error(
                            f"{spec_context}: upload-artifact retention-days for "
                            f"{token!r} must be {spec.retention_days}"
                        )
                    upload_paths = _workflow_upload_artifact_paths(block)
                    if not upload_paths:
                        self.error(
                            f"{spec_context}: upload-artifact step for {token!r} "
                            "must set explicit JSON path(s)"
                        )
                    elif _workflow_upload_paths_match_expected(
                        upload_paths,
                        artifact=spec.artifact,
                        expected_path=spec.path,
                    ):
                        self.pass_check()
                    else:
                        self.error(
                            f"{spec_context}: upload-artifact step for {token!r} "
                            f"must upload exactly {spec.path!r}"
                        )

    def require_workflow_checkout_hardening(self, workflow_text: str, *, context: str) -> None:
        checkout_blocks = _workflow_checkout_blocks(workflow_text)
        if not checkout_blocks:
            self.error(f"{context}: missing actions/checkout step")
            return
        for block in checkout_blocks:
            if _workflow_checkout_block_disables_persisted_credentials(block):
                self.pass_check()
            else:
                self.error(
                    f"{context}: actions/checkout steps must set "
                    "persist-credentials: false"
                )

    def require_workflow_job_timeouts(self, workflow_text: str, *, context: str) -> None:
        job_blocks = _workflow_job_blocks(workflow_text)
        if not job_blocks:
            self.error(f"{context}: missing workflow jobs")
            return
        for job_name, block in job_blocks:
            match = re.search(r"(?m)^\s{4}timeout-minutes:\s*([0-9]+)\s*$", block)
            if not match:
                self.error(f"{context}.{job_name}: missing timeout-minutes")
                continue
            timeout_minutes = int(match.group(1))
            if timeout_minutes <= 0 or timeout_minutes > 120:
                self.error(
                    f"{context}.{job_name}: timeout-minutes must be between 1 and 120"
                )
            else:
                self.pass_check()

    def require_workflow_job_control_key_uniqueness(
        self,
        workflow_text: str,
        *,
        context: str,
    ) -> None:
        job_blocks = _workflow_job_blocks(workflow_text)
        if not job_blocks:
            self.error(f"{context}: missing workflow jobs")
            return

        control_fields = [
            "runs-on",
            "environment",
            "timeout-minutes",
            "needs",
            "if",
            "env",
            "steps",
        ]
        for job_name, block in job_blocks:
            duplicates = _workflow_job_duplicate_direct_fields(block, control_fields)
            if duplicates:
                rendered = ", ".join(duplicates)
                self.error(
                    f"{context}.{job_name}: duplicate job-level field(s): {rendered}"
                )
            else:
                self.pass_check()

    def require_workflow_fail_closed_execution(self, workflow_text: str, *, context: str) -> None:
        errors = 0
        for line_number, line in enumerate(workflow_text.splitlines(), start=1):
            match = re.match(r"^\s+continue-on-error:\s*(.+?)\s*$", line)
            if not match:
                continue
            value = match.group(1).split("#", 1)[0].strip().strip("\"'")
            if value.casefold() == "false":
                continue
            errors += 1
            self.error(
                f"{context}: continue-on-error must not be enabled "
                f"(line {line_number})"
            )
        if errors == 0:
            self.pass_check()

    def require_workflow_no_shell_xtrace(self, workflow_text: str, *, context: str) -> None:
        errors = 0
        for block in _workflow_step_blocks(workflow_text):
            for line in _workflow_run_command_lines(block):
                if _workflow_command_enables_shell_xtrace(line):
                    errors += 1
                    self.error(
                        f"{context}: shell xtrace must not be enabled in "
                        f"registered evidence workflows: {line!r}"
                    )
        if errors == 0:
            self.pass_check()

    def require_workflow_permissions_hardening(self, workflow_text: str, *, context: str) -> None:
        if re.search(r"(?m)^[ \t]+permissions:", workflow_text):
            self.error(f"{context}: job-level permissions overrides are not allowed")
            return
        permissions_block = _workflow_top_level_block(workflow_text, "permissions")
        if not permissions_block:
            self.error(f"{context}: missing top-level permissions block")
            return
        if permissions_block[0] != "permissions:":
            self.error(f"{context}: top-level permissions must be a mapping")
            return
        permissions: dict[str, str] = {}
        for line in permissions_block[1:]:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.match(r"^  ([A-Za-z-]+):\s*(read|write|none)\s*$", line)
            if not match:
                self.error(f"{context}: unsupported permissions entry {line.strip()!r}")
                continue
            permissions[match.group(1)] = match.group(2)
        if permissions != {"contents": "read"}:
            self.error(f"{context}: permissions must be exactly `contents: read`")
        else:
            self.pass_check()

    def require_workflow_concurrency_guard(self, workflow_text: str, *, context: str) -> None:
        concurrency_block = _workflow_top_level_block(workflow_text, "concurrency")
        if not concurrency_block:
            self.error(f"{context}: missing top-level concurrency block")
            return
        if concurrency_block[0] != "concurrency:":
            self.error(f"{context}: top-level concurrency must be a mapping")
            return

        entries: dict[str, str] = {}
        for line in concurrency_block[1:]:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.match(r"^  (group|cancel-in-progress):\s*(.+?)\s*$", line)
            if not match:
                self.error(f"{context}: unsupported concurrency entry {line.strip()!r}")
                continue
            entries[match.group(1)] = match.group(2)

        group = entries.get("group")
        if group != EXPECTED_CONCURRENCY_GROUP:
            self.error(
                f"{context}: group must be "
                f"`group: {EXPECTED_CONCURRENCY_GROUP}`"
            )
        else:
            self.pass_check()

        cancel_in_progress = entries.get("cancel-in-progress")
        if cancel_in_progress != EXPECTED_CONCURRENCY_CANCEL:
            self.error(
                f"{context}: cancel-in-progress must be "
                f"`cancel-in-progress: {EXPECTED_CONCURRENCY_CANCEL}`"
            )
        else:
            self.pass_check()

    def require_registered_workflow_secret_scope(self, requirements: list[Any]) -> None:
        specs_by_workflow: dict[str, list[tuple[str, str, list[str], str, list[str], list[str], list[str]]]] = {}
        for item in requirements:
            if not isinstance(item, dict):
                continue
            workflow = item.get("workflow")
            requirement_id = item.get("id")
            artifact = item.get("artifact")
            artifact_tokens = item.get("artifact_tokens")
            probe = item.get("probe")
            live_flags = item.get("live_env_flags")
            guard_tokens = item.get("live_guard_tokens")
            gate_tokens = item.get("dispatch_or_schedule_gate_tokens")
            if (
                not isinstance(workflow, str)
                or not workflow.strip()
                or not isinstance(requirement_id, str)
                or not requirement_id.strip()
                or not isinstance(artifact, str)
                or not artifact.strip()
                or not isinstance(artifact_tokens, list)
                or not isinstance(probe, str)
                or not probe.strip()
                or not isinstance(live_flags, list)
                or not isinstance(guard_tokens, list)
                or not isinstance(gate_tokens, list)
            ):
                continue
            clean_artifact_tokens = [
                token.strip()
                for token in artifact_tokens
                if isinstance(token, str) and token.strip()
            ]
            clean_live_flags = [
                token.strip()
                for token in live_flags
                if isinstance(token, str) and token.strip()
            ]
            clean_guard_tokens = [
                token.strip()
                for token in guard_tokens
                if isinstance(token, str) and token.strip()
            ]
            clean_gate_tokens = [
                token.strip()
                for token in gate_tokens
                if isinstance(token, str) and token.strip()
            ]
            if clean_artifact_tokens and clean_live_flags and clean_guard_tokens and clean_gate_tokens:
                specs_by_workflow.setdefault(workflow.strip(), []).append(
                    (
                        requirement_id.strip(),
                        artifact.strip(),
                        clean_artifact_tokens,
                        probe.strip(),
                        clean_live_flags,
                        clean_guard_tokens,
                        clean_gate_tokens,
                    )
                )

        for workflow, requirement_specs in specs_by_workflow.items():
            _, workflow_text = self.require_file_text(
                workflow,
                context=f"workflow_secrets[{workflow}]",
            )
            if not workflow_text:
                continue
            self.require_workflow_secret_scope_hardening(
                workflow_text,
                requirement_specs=requirement_specs,
                context=f"workflow_secrets[{workflow}]",
            )

    def require_workflow_secret_scope_hardening(
        self,
        workflow_text: str,
        *,
        requirement_specs: list[tuple[str, str, list[str], str, list[str], list[str], list[str]]],
        context: str,
    ) -> None:
        violation_count = 0
        gate_tokens = sorted(
            {
                token
                for *_, spec_gate_tokens in requirement_specs
                for token in spec_gate_tokens
            }
        )
        pre_jobs_text = _workflow_text_before_jobs(workflow_text)
        if _workflow_text_references_secrets(pre_jobs_text):
            violation_count += 1
            self.error(f"{context}: top-level secret references are not allowed")

        for job_name, block in _workflow_job_blocks(workflow_text):
            if not _workflow_text_references_secrets(block):
                continue
            if not _workflow_job_if_matches_any_dispatch_or_schedule_gate_pair(
                block,
                gate_tokens,
            ):
                violation_count += 1
                self.error(
                    f"{context}.{job_name}: secret references must stay behind "
                    "a registered workflow_dispatch or schedule evidence gate"
                )
            if not _workflow_job_needs_contract(block):
                violation_count += 1
                self.error(
                    f"{context}.{job_name}: secret-bearing evidence job must "
                    "declare `needs: contract`"
                )
            if not any(
                _workflow_secret_job_matches_registered_requirement(
                    block,
                    requirement_id=requirement_id,
                    artifact=artifact,
                    artifact_tokens=artifact_tokens,
                    probe_path=probe_path,
                    live_flags=live_flags,
                    guard_tokens=guard_tokens,
                    gate_tokens=requirement_gate_tokens,
                )
                for (
                    requirement_id,
                    artifact,
                    artifact_tokens,
                    probe_path,
                    live_flags,
                    guard_tokens,
                    requirement_gate_tokens,
                ) in requirement_specs
            ):
                violation_count += 1
                self.error(
                    f"{context}.{job_name}: secret references must stay inside "
                    "a registered live evidence job"
                )

        if violation_count == 0:
            self.pass_check()

    def require_registered_workflow_production_override_guard(
        self,
        requirements: list[Any],
    ) -> None:
        workflows: dict[str, set[str]] = {}
        production_override_workflows: dict[str, set[str]] = {}
        for item in requirements:
            if not isinstance(item, dict):
                continue
            workflow = item.get("workflow")
            if isinstance(workflow, str) and workflow.strip():
                workflow_key = workflow.strip()
                workflows.setdefault(workflow_key, set())
                probe = item.get("probe")
                if isinstance(probe, str) and probe.strip():
                    probe_path = probe.strip()
                    workflows[workflow_key].add(probe_path)
                    _, probe_text = self.require_file_text(
                        probe_path,
                        context=(
                            "workflow_production_override"
                            f"[{workflow_key}].probe[{probe_path}]"
                        ),
                    )
                    if _probe_supports_production_override(probe_text):
                        production_override_workflows.setdefault(
                            workflow_key,
                            set(),
                        ).add(probe_path)

        for workflow, probe_paths in sorted(workflows.items()):
            _, workflow_text = self.require_file_text(
                workflow,
                context=f"workflow_production_override[{workflow}]",
            )
            if not workflow_text:
                continue
            self.require_workflow_production_override_guard(
                workflow_text,
                context=f"workflow_production_override[{workflow}]",
                registered_probe_paths=sorted(probe_paths),
                production_override_probe_paths=sorted(
                    production_override_workflows.get(workflow, set())
                ),
            )

    def require_workflow_production_override_guard(
        self,
        workflow_text: str,
        *,
        context: str,
        registered_probe_paths: list[str],
        production_override_probe_paths: list[str],
    ) -> None:
        if (
            PRODUCTION_OVERRIDE_INPUT not in workflow_text
            and PRODUCTION_OVERRIDE_ENV not in workflow_text
            and PRODUCTION_OVERRIDE_FLAG not in workflow_text
        ):
            if production_override_probe_paths:
                self.error(
                    f"{context}: {PRODUCTION_OVERRIDE_REQUIRED}: "
                    "registered probe supports --allow-production; "
                    "workflow must expose manual allow_production input and pass "
                    "guarded args to the live probe command"
                )
            else:
                self.pass_check()
            return

        input_block = _workflow_dispatch_input_block(
            workflow_text,
            PRODUCTION_OVERRIDE_INPUT,
        )
        duplicate_input_names = _workflow_dispatch_duplicate_input_names(workflow_text)
        if PRODUCTION_OVERRIDE_INPUT in duplicate_input_names:
            self.error(
                f"{context}: allow_production input must not duplicate "
                f"workflow_dispatch input name {PRODUCTION_OVERRIDE_INPUT!r}"
            )
        elif not input_block:
            self.error(f"{context}: missing workflow_dispatch allow_production input")
        else:
            duplicate_input_fields = _workflow_dispatch_input_duplicate_fields(
                input_block,
                ["description", "required", "type", "default"],
            )
            if duplicate_input_fields:
                rendered = ", ".join(duplicate_input_fields)
                self.error(
                    f"{context}: {PRODUCTION_OVERRIDE_DUPLICATE_INPUT_FIELD_MESSAGE}: {rendered}"
                )
            elif _workflow_dispatch_input_is_boolean_default_false(input_block):
                self.pass_check()
            else:
                self.error(
                    f"{context}: allow_production input must be boolean with default false"
                )

        if _workflow_block_has_duplicate_env_flag(workflow_text, PRODUCTION_OVERRIDE_ENV):
            self.error(
                f"{context}: ALLOW_PRODUCTION_INPUT must not duplicate workflow env binding"
            )
        elif _workflow_production_override_env_is_manual_only(workflow_text):
            if not _workflow_production_override_flag_steps_bind_env(workflow_text):
                self.error(
                    f"{context}: ALLOW_PRODUCTION_INPUT must be bound on each "
                    "--allow-production guard step"
                )
            elif not _workflow_production_override_flag_steps_invoke_registered_probe(
                workflow_text,
                registered_probe_paths,
            ):
                self.error(
                    f"{context}: --allow-production must be appended in a "
                    "registered live probe step"
                )
            elif not _workflow_production_override_flag_steps_pass_args_to_probe(
                workflow_text,
                registered_probe_paths,
            ):
                self.error(
                    f"{context}: --allow-production args must be passed to the "
                    "registered live probe command"
                )
            elif not _workflow_production_override_registered_probe_steps_pass_args(
                workflow_text,
                production_override_probe_paths,
            ):
                self.error(
                    f"{context}: each registered probe that supports "
                    "--allow-production must receive guarded production override args"
                )
            else:
                self.pass_check()
        else:
            self.error(
                f"{context}: ALLOW_PRODUCTION_INPUT must be bound only from "
                "workflow_dispatch inputs.allow_production with fallback false"
            )

        if _workflow_production_override_flags_are_guarded(workflow_text):
            self.pass_check()
        else:
            self.error(
                f"{context}: --allow-production must be appended only inside "
                'the ALLOW_PRODUCTION_INPUT == "true" guard'
            )

    def require_workflow_live_job_environment(
        self,
        workflow_text: str,
        *,
        requirement_id: str,
        artifact: str,
        artifact_tokens: list[str],
        probe_path: str,
        live_flags: list[str],
        guard_tokens: list[str],
        gate_tokens: list[str],
        context: str,
    ) -> None:
        for job_name, block in _workflow_job_blocks(workflow_text):
            if not _workflow_secret_job_matches_registered_requirement(
                block,
                requirement_id=requirement_id,
                artifact=artifact,
                artifact_tokens=artifact_tokens,
                probe_path=probe_path,
                live_flags=live_flags,
                guard_tokens=guard_tokens,
                gate_tokens=gate_tokens,
            ):
                continue
            environments = _workflow_job_direct_scalar_values(block, "environment")
            if environments == [EXPECTED_LIVE_EVIDENCE_ENVIRONMENT]:
                self.pass_check()
            else:
                self.error(
                    f"{context}.{job_name}: live evidence job must declare "
                    f"`environment: {EXPECTED_LIVE_EVIDENCE_ENVIRONMENT}`"
                )
            return

    def require_workflow_gate_bindings(
        self,
        workflow_text: str,
        *,
        gate_tokens: list[str],
        context: str,
    ) -> None:
        duplicate_input_names = _workflow_dispatch_duplicate_input_names(workflow_text)
        for token in gate_tokens:
            if token.startswith(("allow_", "run_")):
                if token in duplicate_input_names:
                    self.error(
                        f"{context}.{token}: duplicate workflow_dispatch input "
                        f"name {token!r}"
                    )
                input_block = _workflow_dispatch_input_block(workflow_text, token)
                if not input_block:
                    self.error(f"{context}.{token}: missing workflow_dispatch input")
                else:
                    duplicate_input_fields = _workflow_dispatch_input_duplicate_fields(
                        input_block,
                        ["description", "required", "type", "default"],
                    )
                    if duplicate_input_fields:
                        rendered = ", ".join(duplicate_input_fields)
                        self.error(
                            f"{context}.{token}: duplicate workflow_dispatch "
                            f"input field(s): {rendered}"
                        )
                    if _workflow_dispatch_input_is_boolean_default_false(input_block):
                        self.pass_check()
                    else:
                        self.error(
                            f"{context}.{token}: workflow_dispatch input must be "
                            "boolean with default false"
                        )
                if _workflow_has_job_if_gate(workflow_text, token):
                    self.pass_check()
                else:
                    self.error(
                        f"{context}.{token}: workflow_dispatch runs must be guarded "
                        f"by `inputs.{token} == true`"
                    )
            if token.startswith("WIII_") and token.endswith("_EVIDENCE_ENABLED"):
                if _workflow_has_job_if_gate(workflow_text, token):
                    self.pass_check()
                else:
                    self.error(
                        f"{context}.{token}: scheduled runs must be guarded by "
                        f"`vars.{token} == '1'`"
                    )

    def require_workflow_live_probe_binding(
        self,
        workflow_text: str,
        *,
        probe_path: str,
        artifact: str,
        live_flags: list[str],
        guard_tokens: list[str],
        context: str,
    ) -> None:
        for flag in live_flags:
            if _workflow_block_has_duplicate_env_flag(workflow_text, flag):
                self.error(
                    f"{context}.{flag}: workflow env maps must not duplicate "
                    f"`{flag}`"
                )
            elif _workflow_block_sets_env_flag(workflow_text, flag):
                self.pass_check()
            else:
                self.error(f"{context}.{flag}: workflow must set `{flag}: \"1\"`")

        probe_blocks = _workflow_probe_invocation_blocks(workflow_text, probe_path)
        if not probe_blocks:
            self.error(f"{context}: missing workflow step invoking {probe_path!r}")
            return
        self.pass_check()
        for guard_token in guard_tokens:
            if any(
                _workflow_probe_block_has_guard(block, probe_path, guard_token)
                for block in probe_blocks
            ):
                self.pass_check()
            else:
                self.error(
                    f"{context}.{guard_token}: guard token must appear in the "
                    "workflow command line that invokes the registered probe"
                )
        guarded_probe_blocks = [
            block
            for block in probe_blocks
            if any(
                _workflow_probe_block_has_guard(block, probe_path, guard_token)
                for guard_token in guard_tokens
            )
        ]
        strict_shell_missing = [
            block
            for block in guarded_probe_blocks
            if not _workflow_run_block_starts_with_strict_shell(block)
        ]
        if strict_shell_missing:
            self.error(
                f"{context}: registered live probe multiline run steps must "
                "start with `set -euo pipefail`"
            )
        elif guarded_probe_blocks:
            self.pass_check()
        probe_suffix = PurePosixPath(probe_path.replace("\\", "/")).suffix
        if probe_suffix in {".py", ".mjs"}:
            if any(
                _workflow_probe_block_writes_artifact(
                    block,
                    probe_path=probe_path,
                    artifact=artifact,
                )
                for block in probe_blocks
            ):
                self.pass_check()
            else:
                self.error(
                    f"{context}.--out: registered probe invocation must "
                    f"write `--out {artifact}`"
                )

    def require_workflow_requirement_job_binding(
        self,
        workflow_text: str,
        *,
        artifact: str,
        artifact_tokens: list[str],
        requirement_id: str,
        probe_path: str,
        live_flags: list[str],
        guard_tokens: list[str],
        context: str,
    ) -> None:
        job_blocks = _workflow_job_blocks(workflow_text)
        if not job_blocks:
            self.error(f"{context}: missing workflow jobs")
            return
        candidate_notes: list[str] = []
        for job_name, block in job_blocks:
            missing: list[str] = []
            live_flags_ok = all(
                _workflow_block_sets_unique_env_flag(block, flag)
                for flag in live_flags
            )
            if not live_flags_ok:
                missing.append("live env")

            probe_blocks = _workflow_probe_invocation_blocks(block, probe_path)
            probe_ok = bool(probe_blocks) and _workflow_probe_blocks_have_guards(
                probe_blocks,
                probe_path=probe_path,
                guard_tokens=guard_tokens,
            )
            if not probe_ok:
                missing.append("probe guard")
            if not _workflow_job_checks_out_before_probe(block, probe_path):
                missing.append("checkout before probe")

            expected_upload_paths = _workflow_job_validation_expected_upload_paths(
                block,
                artifact=artifact,
                requirement_id=requirement_id,
            )
            validation_ok = bool(expected_upload_paths)
            if not validation_ok:
                missing.append("artifact validation")

            upload_ok = any(
                _workflow_job_has_expected_uploads(
                    block,
                    artifact=artifact,
                    artifact_tokens=artifact_tokens,
                    expected_path=expected_path,
                )
                for expected_path in expected_upload_paths
            )
            if not upload_ok:
                missing.append("artifact upload")

            if (
                probe_ok
                and validation_ok
                and upload_ok
                and not _workflow_job_has_probe_validation_upload_order(
                    block,
                    probe_path=probe_path,
                    artifact=artifact,
                    artifact_tokens=artifact_tokens,
                    requirement_id=requirement_id,
                    guard_tokens=guard_tokens,
                )
            ):
                missing.append("probe-validation-upload order")

            if not missing:
                self.pass_check()
                return
            if artifact in block or probe_blocks or any(token in block for token in artifact_tokens):
                candidate_notes.append(f"{job_name} missing {', '.join(missing)}")

        details = "; ".join(candidate_notes[:3]) if candidate_notes else "no candidate jobs"
        self.error(
            f"{context}: no single workflow job binds live env, probe guard, "
            "artifact validation, upload, and probe-validation-upload order "
            f"for {artifact!r} ({details})"
        )

    def require_workflow_live_job_contract_dependency(
        self,
        workflow_text: str,
        *,
        artifact: str,
        artifact_tokens: list[str],
        requirement_id: str,
        probe_path: str,
        live_flags: list[str],
        guard_tokens: list[str],
        test_paths: list[str],
        context: str,
    ) -> None:
        for job_name, block in _workflow_job_blocks(workflow_text):
            if not all(_workflow_block_sets_env_flag(block, flag) for flag in live_flags):
                continue
            probe_blocks = _workflow_probe_invocation_blocks(block, probe_path)
            if not probe_blocks:
                continue
            if not _workflow_probe_blocks_have_guards(
                probe_blocks,
                probe_path=probe_path,
                guard_tokens=guard_tokens,
            ):
                continue
            validation_ok = _workflow_job_has_bound_validation_upload(
                block,
                artifact=artifact,
                artifact_tokens=artifact_tokens,
                requirement_id=requirement_id,
            )
            if not validation_ok:
                continue

            if all(_workflow_runs_contract_test(block, test_path) for test_path in test_paths):
                self.pass_check()
                return
            if _workflow_job_needs_contract(block):
                if not _workflow_contract_job_is_unconditional(workflow_text):
                    self.error(
                        f"{context}.{job_name}: `needs: contract` job must not "
                        "have a job-level if condition"
                    )
                    return
                missing_tests = [
                    test_path
                    for test_path in test_paths
                    if not _workflow_contract_job_runs_test(workflow_text, test_path)
                ]
                if missing_tests:
                    self.error(
                        f"{context}.{job_name}: `needs: contract` job must execute "
                        f"registered contract test(s): {', '.join(missing_tests)}"
                    )
                    return
                missing_checkout_tests = [
                    test_path
                    for test_path in test_paths
                    if not _workflow_contract_job_checks_out_before_test(
                        workflow_text,
                        test_path,
                    )
                ]
                if missing_checkout_tests:
                    self.error(
                        f"{context}.{job_name}: `needs: contract` job must checkout "
                        "with persist-credentials false before registered contract "
                        f"test(s): {', '.join(missing_checkout_tests)}"
                    )
                else:
                    self.pass_check()
                return
            self.error(
                f"{context}.{job_name}: live evidence job must either execute all "
                "registered contract tests or declare `needs: contract`"
            )
            return

    def require_workflow_live_job_gate_binding(
        self,
        workflow_text: str,
        *,
        artifact: str,
        artifact_tokens: list[str],
        requirement_id: str,
        probe_path: str,
        live_flags: list[str],
        guard_tokens: list[str],
        gate_tokens: list[str],
        context: str,
    ) -> None:
        for job_name, block in _workflow_job_blocks(workflow_text):
            if not all(_workflow_block_sets_env_flag(block, flag) for flag in live_flags):
                continue
            probe_blocks = _workflow_probe_invocation_blocks(block, probe_path)
            if not probe_blocks:
                continue
            if not _workflow_probe_blocks_have_guards(
                probe_blocks,
                probe_path=probe_path,
                guard_tokens=guard_tokens,
            ):
                continue
            validation_ok = _workflow_job_has_bound_validation_upload(
                block,
                artifact=artifact,
                artifact_tokens=artifact_tokens,
                requirement_id=requirement_id,
            )
            if not validation_ok:
                continue

            if not _workflow_job_if_matches_dispatch_or_schedule_gates(block, gate_tokens):
                self.error(
                    f"{context}.{job_name}: live evidence job-level if must be "
                    "guarded by exactly the registered workflow_dispatch input "
                    "or scheduled vars gate"
                )
            else:
                self.pass_check()
            return

    def require_workflow_action_pinning(self, workflow_text: str, *, context: str) -> None:
        action_refs = _workflow_uses_refs(workflow_text)
        if not action_refs:
            self.error(f"{context}: missing workflow uses steps")
            return
        for action, ref in action_refs:
            if action not in ALLOWED_ACTION_NAMES:
                self.error(f"{context}: unsupported workflow uses action {action!r}")
                continue
            if PINNED_ACTION_REF_RE.match(ref):
                self.pass_check()
            else:
                self.error(
                    f"{context}: {action} must be pinned to a 40-character commit SHA"
                )

    def require_workflow_path_filters(
        self,
        workflow_text: str,
        *,
        workflow_path: str,
        probe_path: str,
        test_paths: list[str],
        context: str,
    ) -> None:
        required_paths = [
            workflow_path.replace("\\", "/"),
            "tools/wiii_self_harness/**",
            probe_path.replace("\\", "/"),
            *[test_path.replace("\\", "/") for test_path in test_paths],
        ]
        for event_name in ("pull_request", "push"):
            duplicate_filter_fields = _workflow_event_duplicate_direct_fields(
                workflow_text,
                event_name,
                ["paths", "paths-ignore", "branches", "branches-ignore"],
            )
            if duplicate_filter_fields:
                rendered = ", ".join(duplicate_filter_fields)
                self.error(
                    f"{context}.{event_name}: duplicate event filter field(s): "
                    f"{rendered}"
                )
            unsupported_filter_fields = [
                field
                for field in ("paths-ignore", "branches-ignore")
                if _workflow_event_has_direct_field(workflow_text, event_name, field)
            ]
            if unsupported_filter_fields:
                rendered = ", ".join(unsupported_filter_fields)
                self.error(
                    f"{context}.{event_name}: unsupported event filter field(s): "
                    f"{rendered}"
                )
            else:
                self.pass_check()
            branches = _workflow_event_filter_values(workflow_text, event_name, "branches")
            if branches and "main" not in branches:
                self.error(
                    f"{context}.{event_name}: branches filter must include 'main'"
                )
            else:
                self.pass_check()
            paths = _workflow_event_paths(workflow_text, event_name)
            if not paths:
                self.error(f"{context}.{event_name}: missing paths filter")
                continue
            for required_path in required_paths:
                if required_path in paths:
                    self.pass_check()
                else:
                    self.error(
                        f"{context}.{event_name}: missing paths filter {required_path!r}"
                    )

    def require_workflow_contract_test_execution(
        self,
        workflow_text: str,
        *,
        test_paths: list[str],
        context: str,
    ) -> None:
        for test_path in test_paths:
            if _workflow_runs_contract_test(workflow_text, test_path):
                self.pass_check()
            else:
                self.error(
                    f"{context}: registered contract test {test_path!r} "
                    "must be executed by pytest or vitest in a run step"
                )

    def require_registered_workflow_upload_steps(self, requirements: list[Any]) -> None:
        specs_by_workflow: dict[str, list[tuple[str, str, list[str]]]] = {}
        diagnostic_specs_by_workflow: dict[str, list[DiagnosticUploadSpec]] = {}
        for item in requirements:
            if not isinstance(item, dict):
                continue
            workflow = item.get("workflow")
            artifact = item.get("artifact")
            requirement_id = item.get("id")
            artifact_tokens = item.get("artifact_tokens")
            if (
                not isinstance(workflow, str)
                or not workflow.strip()
                or not isinstance(requirement_id, str)
                or not requirement_id.strip()
                or not isinstance(artifact, str)
                or not artifact.strip()
                or not isinstance(artifact_tokens, list)
            ):
                continue
            tokens = [
                token.strip()
                for token in artifact_tokens
                if isinstance(token, str) and token.strip()
            ]
            if tokens:
                specs_by_workflow.setdefault(workflow.strip(), []).append(
                    (requirement_id.strip(), artifact.strip(), tokens)
                )
            diagnostic_uploads = item.get("diagnostic_uploads")
            if isinstance(diagnostic_uploads, list):
                for diagnostic_upload in diagnostic_uploads:
                    if not isinstance(diagnostic_upload, dict):
                        continue
                    diagnostic_artifact = diagnostic_upload.get("artifact")
                    diagnostic_path = diagnostic_upload.get("path")
                    diagnostic_tokens = diagnostic_upload.get("artifact_tokens")
                    diagnostic_if_no_files_found = diagnostic_upload.get("if_no_files_found")
                    diagnostic_retention_days = diagnostic_upload.get("retention_days")
                    if (
                        isinstance(diagnostic_artifact, str)
                        and diagnostic_artifact.strip()
                        and isinstance(diagnostic_path, str)
                        and diagnostic_path.strip()
                        and isinstance(diagnostic_tokens, list)
                        and diagnostic_tokens
                        and all(isinstance(token, str) and token.strip() for token in diagnostic_tokens)
                        and isinstance(diagnostic_if_no_files_found, str)
                        and diagnostic_if_no_files_found.strip()
                        and _is_positive_int(diagnostic_retention_days)
                    ):
                        diagnostic_specs_by_workflow.setdefault(workflow.strip(), []).append(
                            DiagnosticUploadSpec(
                                requirement_id=requirement_id.strip(),
                                artifact=diagnostic_artifact.strip(),
                                path=diagnostic_path.replace("\\", "/").strip(),
                                artifact_tokens=tuple(token.strip() for token in diagnostic_tokens),
                                if_no_files_found=diagnostic_if_no_files_found.strip(),
                                retention_days=diagnostic_retention_days,
                            )
                        )

        for workflow in sorted(set(specs_by_workflow) | set(diagnostic_specs_by_workflow)):
            specs = specs_by_workflow.get(workflow, [])
            diagnostic_specs = diagnostic_specs_by_workflow.get(workflow, [])
            _, workflow_text = self.require_file_text(
                workflow,
                context=f"workflow_uploads[{workflow}]",
            )
            if not workflow_text:
                continue
            upload_index = 0
            for _, job_block in _workflow_job_blocks(workflow_text):
                expected_paths_by_artifact: dict[tuple[str, str], list[str]] = {}
                for requirement_id, artifact, _tokens in specs:
                    expected_paths_by_artifact[(requirement_id, artifact)] = (
                        _workflow_job_validation_expected_upload_paths(
                            job_block,
                            artifact=artifact,
                            requirement_id=requirement_id,
                        )
                    )
                for block in _workflow_upload_artifact_blocks(job_block):
                    if any(
                        any(
                            _workflow_upload_block_binds_artifact_path(
                                block,
                                artifact=artifact,
                                artifact_token=token,
                                expected_path=expected_path,
                            )
                            for token in tokens
                            for expected_path in expected_paths_by_artifact[
                                (requirement_id, artifact)
                            ]
                        )
                        for requirement_id, artifact, tokens in specs
                    ):
                        self.pass_check()
                    elif any(
                        any(
                            _workflow_upload_block_binds_artifact_path(
                                block,
                                artifact=diagnostic_spec.artifact,
                                artifact_token=token,
                                expected_path=diagnostic_spec.path,
                            )
                            for token in diagnostic_spec.artifact_tokens
                        )
                        for diagnostic_spec in diagnostic_specs
                    ):
                        self.pass_check()
                    else:
                        self.error(
                            f"workflow_uploads[{workflow}].upload[{upload_index}]: "
                            "unregistered upload-artifact step"
                        )
                    upload_index += 1
