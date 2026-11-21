"""Registry validation results, error codes, and text reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .constants import (
    REGISTRY_NAME,
    REGISTRY_OUTPUT_PATH_DIRECTORY_ERROR,
    REGISTRY_OUTPUT_PATH_PARENT_SYMLINK_ERROR,
    REGISTRY_OUTPUT_PATH_SYMLINK_ERROR,
)


@dataclass(frozen=True)
class RegistryResult:
    validation_schema_version: str
    registry: str
    registry_version: int | None
    registry_path: str
    registry_fingerprint_sha256: str
    requirement_count: int
    passed_checks: int
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ok"] = self.ok
        data["error_codes"] = _error_codes(self.errors)
        data["error_code_counts"] = _error_code_counts(self.errors)
        return data


def _error_codes(errors: list[str]) -> list[str]:
    return sorted({_error_code(error) for error in errors})


def _error_code_counts(errors: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for error in errors:
        code = _error_code(error)
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def _error_code(error: str) -> str:
    return normalize_registry_error_code(error)


def normalize_registry_error_code(error: str) -> str:
    if error == "registry validation output path must not overwrite registry":
        return "registry_output_path_overwrites_registry"
    if error == REGISTRY_OUTPUT_PATH_SYMLINK_ERROR:
        return "registry_output_path_symlink"
    if error == REGISTRY_OUTPUT_PATH_PARENT_SYMLINK_ERROR:
        return "registry_output_path_parent_symlink"
    if error == REGISTRY_OUTPUT_PATH_DIRECTORY_ERROR:
        return "registry_output_path_directory"
    if (
        "No such file or directory" in error
        or "cannot find the file" in error.casefold()
        or "non-finite JSON number is not allowed" in error
        or "duplicate JSON object key(s)" in error
    ):
        return "registry_load_failed"
    if error == "registry root must be a JSON object":
        return "registry_root_not_object"
    if error.startswith("registry: `registry` must be "):
        return "registry_identity_mismatch"
    if error == "registry: `version` must be an integer >= 1":
        return "registry_version_invalid"
    if error == "registry: `requirements` must be a non-empty list":
        return "registry_requirements_empty"
    if error.startswith("registry: unknown field(s):"):
        return "registry_unknown_field"
    if error.endswith(": requirement must be an object"):
        return "registry_requirement_not_object"
    if ".freshness: unknown field(s):" in error:
        return "registry_freshness_unknown_field"
    if ".payload_checks[" in error and ": unknown field(s):" in error:
        return "registry_payload_check_unknown_field"
    if ".freshness:" in error and "dot-path syntax" in error:
        return "registry_freshness_path_invalid"
    if ".freshness: max_age_hours must be a positive integer" in error:
        return "registry_freshness_max_age_invalid"
    if ".payload_checks[" in error and "dot-path syntax" in error:
        return "registry_payload_check_path_invalid"
    if (
        ".payload_checks[" in error
        and ".when:" in error
        and "must be a non-null JSON scalar" in error
    ):
        return "registry_payload_check_when_value_invalid"
    if ".payload_checks[" in error and (
        "min must be a JSON number" in error
        or "sorted_equals must be a list" in error
        or "must be a non-null JSON scalar" in error
    ):
        return "registry_payload_check_value_invalid"
    if ".payload_checks[" in error and ".when:" in error and "equals or not_equals" in error:
        return "registry_payload_check_when_operation_invalid"
    if ": unknown field(s):" in error and "requirements[" in error:
        return "registry_requirement_unknown_field"
    if error.endswith(": `id` must be lowercase kebab-case"):
        return "registry_requirement_id_invalid"
    if error.endswith(": duplicate requirement id"):
        return "registry_requirement_id_duplicate"
    if ": unsupported layer " in error:
        return "registry_layer_unsupported"
    if ": `artifact` must be a file name, not a path" in error:
        return "registry_artifact_path_invalid"
    if ": `artifact` must be a JSON file" in error:
        return "registry_artifact_not_json"
    if "safe lowercase kebab-case JSON file name" in error:
        return "registry_artifact_name_invalid"
    if ": duplicate artifact name " in error:
        return "registry_artifact_name_duplicate"
    if ": invalid schema_version " in error:
        return "registry_schema_version_invalid"
    if ": unsupported payload_schema_field " in error:
        return "registry_payload_schema_field_unsupported"
    if ": path must be a non-empty string" in error:
        return "repo_path_missing"
    if ": path must be repo-relative:" in error:
        return "repo_path_not_relative"
    if ": path escapes repo root:" in error:
        return "repo_path_escapes_root"
    if ": file does not exist:" in error:
        return "repo_file_missing"
    if ": path must be a file:" in error:
        return "repo_path_not_file"
    if ": path must not contain symlinks:" in error:
        return "repo_path_symlink"
    if ": file is not UTF-8:" in error:
        return "repo_file_not_utf8"
    if ": missing token " in error:
        return "source_token_missing"
    if ".workflow: workflow must be a YAML file" in error:
        return "workflow_file_not_yaml"
    if ".workflow: workflow must live directly under .github/workflows/" in error:
        return "workflow_file_location_invalid"
    if "pull_request_target is not allowed" in error:
        return "workflow_pull_request_target_forbidden"
    if "duplicate top-level" in error:
        return "workflow_top_level_duplicate"
    if "duplicate workflow event name(s)" in error:
        return "workflow_event_duplicate"
    if "duplicate workflow job id(s)" in error:
        return "workflow_job_name_duplicate"
    if "duplicate job-level field(s)" in error:
        return "workflow_job_control_duplicate"
    if "validate_runtime_evidence_artifact.py" in error:
        return "workflow_validation_binding_invalid"
    if "unregistered upload-artifact step" in error:
        return "workflow_unregistered_upload_step"
    if "upload-artifact" in error or "if-no-files-found: error" in error or "retention-days" in error:
        return "workflow_upload_binding_invalid"
    if "actions/checkout" in error or "persist-credentials false" in error or "checkout before" in error:
        return "workflow_checkout_invalid"
    if "timeout-minutes" in error:
        return "workflow_timeout_invalid"
    if "continue-on-error" in error:
        return "workflow_continue_on_error_forbidden"
    if "shell xtrace" in error:
        return "workflow_shell_xtrace_forbidden"
    if "permissions" in error:
        return "workflow_permissions_invalid"
    if "concurrency" in error or "cancel-in-progress" in error:
        return "workflow_concurrency_invalid"
    if "live evidence job must declare `environment:" in error:
        return "workflow_environment_invalid"
    if "secret references" in error or "secret-bearing evidence job" in error:
        return "workflow_secret_scope_invalid"
    if "allow_production" in error or "ALLOW_PRODUCTION_INPUT" in error or "--allow-production" in error:
        return "workflow_production_override_invalid"
    if "dispatch_or_schedule_gate_tokens contains unsupported gate token" in error:
        return "registry_gate_token_unsupported"
    if "dispatch_or_schedule_gate_tokens must include exactly one" in error:
        return "registry_gate_token_pair_invalid"
    if "duplicate workflow_dispatch input" in error:
        return "workflow_dispatch_input_duplicate"
    if (
        "live_guard_tokens entries" in error
        or "must be an argparse store_true CLI flag" in error
        or "fail-closed process.argv.includes" in error
        or "MJS probe fail() must call process.exit" in error
    ):
        return "registry_live_guard_token_invalid"
    if (
        "workflow_dispatch input" in error
        or "workflow_dispatch runs must be guarded" in error
        or "scheduled runs must be guarded" in error
        or "guard token" in error
        or " live evidence job must be guarded " in error
    ):
        return "workflow_gate_binding_invalid"
    if "live_env_flags entries" in error:
        return "registry_live_env_flag_invalid"
    if "workflow env maps must not duplicate" in error:
        return "workflow_env_flag_duplicate"
    if ": artifact token must include requirement id " in error:
        return "registry_artifact_token_identity_invalid"
    if ": duplicate artifact token " in error:
        return "registry_artifact_token_duplicate"
    if (
        "registered probe invocation" in error
        or "registered Python probe invocation" in error
        or "workflow must set `" in error
        or "missing workflow step invoking" in error
    ):
        return "workflow_probe_binding_invalid"
    if "must import emit_json_payload from runtime_evidence_output" in error:
        return "registry_probe_output_helper_invalid"
    if "must call emit_json_payload with an output path argument" in error:
        return "registry_probe_output_helper_invalid"
    if "must define `--out` as an argparse CLI flag" in error:
        return "registry_probe_output_argument_invalid"
    if "registered MJS probe must parse `--out` from process.argv" in error:
        return "registry_probe_output_argument_invalid"
    if "must forward parsed `--out` path to WIII_RUNTIME_FLOW_BROWSER_REPLAY_SUMMARY_JSON" in error:
        return "registry_probe_output_argument_invalid"
    if "must not write evidence files outside runtime_evidence_output" in error:
        return "registry_probe_raw_file_write_forbidden"
    if "must not write evidence files outside runtime-evidence-output.mjs" in error:
        return "registry_probe_raw_file_write_forbidden"
    if "runtime evidence output helper" in error and "atomic temp-file writes" in error:
        return "registry_output_helper_atomic_invalid"
    if "runtime evidence output helper test" in error:
        return "workflow_output_helper_contract_invalid"
    if ".probe: probe must be a script file" in error:
        return "registry_probe_suffix_invalid"
    if ": contract_tests entries must be Python " in error:
        return "registry_contract_test_path_invalid"
    if "contract test" in error or "registered contract test" in error or "`needs: contract`" in error:
        return "workflow_contract_test_invalid"
    if "unsupported workflow uses action" in error:
        return "workflow_action_not_allowed"
    if "40-character commit SHA" in error:
        return "workflow_action_ref_unpinned"
    if "missing paths filter" in error:
        return "workflow_path_filter_missing"
    if "duplicate event filter field(s)" in error:
        return "workflow_path_filter_duplicate"
    if "unsupported event filter field(s)" in error:
        return "workflow_path_filter_invalid"
    if "branches filter must include 'main'" in error:
        return "workflow_path_filter_invalid"
    if "`payload_checks` must be a non-empty list" in error:
        return "registry_payload_checks_missing"
    if "duplicate payload check" in error:
        return "registry_payload_check_duplicate"
    if "must not contain duplicate values" in error:
        return "registry_string_list_duplicate"
    if "`contract_tests` must not contain duplicate normalized paths" in error:
        return "registry_contract_test_duplicate"
    if "case-insensitive duplicate values" in error:
        return "registry_forbidden_payload_token_duplicate"
    if "forbidden_payload_regexes pattern must compile" in error:
        return "registry_forbidden_payload_regex_invalid"
    if "duplicate forbidden_payload_regexes pattern" in error:
        return "registry_forbidden_payload_regex_duplicate"
    if "payload_checks" in error and ("raw_content_included == false" in error or "identifier_strategy" in error):
        return "registry_payload_privacy_check_missing"
    if ".payload_checks[" in error:
        return "registry_payload_check_invalid"
    if "`freshness` must be an object" in error:
        return "registry_freshness_missing"
    if ".freshness:" in error:
        return "registry_freshness_invalid"
    return "validation_error"


def format_summary(result: RegistryResult) -> str:
    status = "PASS" if result.ok else "FAIL"
    lines = [
        f"{REGISTRY_NAME}: {status}",
        f"validation_schema: {result.validation_schema_version}",
        f"registry: {result.registry_path}",
        f"registry_version: {result.registry_version if result.registry_version is not None else '-'}",
        f"registry_fingerprint_sha256: {result.registry_fingerprint_sha256}",
        f"requirements: {result.requirement_count}",
        f"checks passed: {result.passed_checks}",
    ]
    if result.errors:
        lines.append("")
        lines.append(f"Error codes: {', '.join(_error_codes(result.errors)) or '-'}")
        lines.append(
            f"Error code counts: {_format_error_code_counts(_error_code_counts(result.errors))}"
        )
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in result.errors)
    return "\n".join(lines)


def _format_error_code_counts(error_code_counts: dict[str, int]) -> str:
    if not error_code_counts:
        return "-"
    return ", ".join(
        f"{error_code}={count}" for error_code, count in error_code_counts.items()
    )
