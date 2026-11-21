"""Registry schema and repository evidence policy constants."""

from __future__ import annotations

import re
from pathlib import Path

REGISTRY_NAME = "Wiii Runtime Evidence Registry"
REGISTRY_VALIDATION_SCHEMA_VERSION = "wiii.runtime_evidence_registry_validation.v1"
REGISTRY_OUTPUT_PATH_DIRECTORY_ERROR = (
    "registry validation output path must not be a directory"
)
REGISTRY_OUTPUT_PATH_SYMLINK_ERROR = (
    "registry validation output path must not be a symlink"
)
REGISTRY_OUTPUT_PATH_PARENT_SYMLINK_ERROR = (
    "registry validation output path parent must not be a symlink"
)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = Path(__file__).parent.parent / "runtime_evidence_registry.json"
CANONICAL_ARTIFACT_VALIDATOR_PATHS = {
    "tools/wiii_self_harness/validate_runtime_evidence_artifact.py",
    "../tools/wiii_self_harness/validate_runtime_evidence_artifact.py",
}
VALID_LAYERS = {"Wiii Core", "Wiii Living", "Wiii Host", "Wiii Org", "Wiii Data"}
ALLOWED_REGISTRY_KEYS = {"registry", "version", "description", "requirements"}
ALLOWED_REQUIREMENT_KEYS = {
    "id",
    "title",
    "layer",
    "workflow",
    "artifact",
    "schema_version",
    "freshness",
    "payload_schema_field",
    "forbidden_payload_tokens",
    "forbidden_payload_regexes",
    "payload_checks",
    "probe",
    "contract_tests",
    "live_env_flags",
    "live_guard_tokens",
    "dispatch_or_schedule_gate_tokens",
    "artifact_tokens",
    "diagnostic_uploads",
}
ALLOWED_DIAGNOSTIC_UPLOAD_KEYS = {
    "artifact",
    "path",
    "artifact_tokens",
    "if_no_files_found",
    "retention_days",
}
ALLOWED_FRESHNESS_KEYS = {"timestamp_path", "max_age_hours"}
ALLOWED_PAYLOAD_CHECK_KEYS = {
    "path",
    "equals",
    "min",
    "sorted_equals",
    "length_equals_path",
    "when",
}
ALLOWED_PAYLOAD_CHECK_WHEN_KEYS = {"path", "equals", "not_equals"}
DOT_PATH_RE = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$")
WILDCARD_DOT_PATH_RE = re.compile(r"^(?:[A-Za-z0-9_]+|\*)(?:\.(?:[A-Za-z0-9_]+|\*))*$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
ARTIFACT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\.json$")
ARTIFACT_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*-\$\{\{ github\.run_id \}\}$")
LIVE_ENV_FLAG_RE = re.compile(r"^WIII_[A-Z0-9_]+$")
LIVE_GUARD_TOKEN_RE = re.compile(r"^--allow-[a-z0-9][a-z0-9-]*$")
DISPATCH_GATE_TOKEN_RE = re.compile(r"^(?:allow|run)_[a-z0-9]+(?:_[a-z0-9]+)*$")
SCHEDULE_GATE_TOKEN_RE = re.compile(
    r"^WIII_[A-Z0-9]+(?:_[A-Z0-9]+)*_EVIDENCE_ENABLED$"
)
SECRET_REFERENCE_RE = re.compile(r"\bsecrets\s*(?:\.|\[)")
SCHEMA_RE = re.compile(r"^wiii\.[a-z0-9_]+\.v[0-9]+$")
PINNED_ACTION_REF_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_ACTION_NAMES = {
    "actions/checkout",
    "actions/setup-node",
    "actions/setup-python",
    "actions/upload-artifact",
}
ALLOWED_PROBE_SUFFIXES = {".py", ".mjs"}
ALLOWED_TYPESCRIPT_TEST_SUFFIXES = (".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx")
ALLOWED_IDENTIFIER_STRATEGIES = {
    "aggregate_counts_only",
    "hash_only",
    "hash_or_count_only",
    "hashes_and_counts",
    "presence_hash_or_count_only",
    "status_only",
}
BASELINE_FORBIDDEN_PAYLOAD_TOKENS = {"api_key", "access_token", "authorization"}
EXPECTED_CONCURRENCY_GROUP = (
    "${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}"
)
EXPECTED_CONCURRENCY_CANCEL = "${{ github.event_name == 'pull_request' }}"
EXPECTED_LIVE_EVIDENCE_ENVIRONMENT = "wiii-runtime-evidence"
PRODUCTION_OVERRIDE_INPUT = "allow_production"
PRODUCTION_OVERRIDE_ENV = "ALLOW_PRODUCTION_INPUT"
PRODUCTION_OVERRIDE_FLAG = "--allow-production"
PRODUCTION_OVERRIDE_ENV_VALUE = (
    "${{ github.event_name == 'workflow_dispatch' && inputs.allow_production || false }}"
)
PRODUCTION_OVERRIDE_ENV_BINDING = (
    f"ALLOW_PRODUCTION_INPUT: {PRODUCTION_OVERRIDE_ENV_VALUE}"
)
PRODUCTION_OVERRIDE_GUARD_LINE = 'if [[ "${ALLOW_PRODUCTION_INPUT}" == "true" ]]; then'
PRODUCTION_OVERRIDE_APPEND_LINE = "args+=(--allow-production)"
PRODUCTION_OVERRIDE_ARGS_EXPANSION = "${args[@]}"
PRODUCTION_OVERRIDE_REQUIRED = "production_override_required"
PRODUCTION_OVERRIDE_DUPLICATE_INPUT_FIELD_MESSAGE = (
    "allow_production input must not duplicate workflow_dispatch input field(s)"
)
UNSUPPORTED_GATE_TOKEN_SUMMARY = "unsupported gate token(s)"
PYTHON_RUNTIME_EVIDENCE_HELPER_ATOMIC_TOKENS = [
    "emit_json_payload",
    "validate_output_path",
    "tempfile.NamedTemporaryFile",
    "delete=False",
    "dir=out_path.parent",
    "os.fsync",
    "os.replace",
    "suffix=\".tmp\"",
]
MJS_RUNTIME_EVIDENCE_HELPER_ATOMIC_TOKENS = [
    "writeJsonFile",
    "validateOutputPath",
    "openSync(tempPath, \"wx\", 0o600)",
    "writeFileSync(fd,",
    "fsyncSync(fd)",
    "renameSync(tempPath, resolved)",
    "rmSync",
    "randomUUID",
    ".tmp",
]
PYTHON_RUNTIME_EVIDENCE_HELPER_TEST_NAME = "test_runtime_evidence_output.py"
MJS_RUNTIME_EVIDENCE_HELPER_TEST_NAME = "test-runtime-evidence-output.mjs"
MJS_RAW_FILE_WRITE_FUNCTIONS = {
    "appendFile",
    "appendFileSync",
    "createWriteStream",
    "writeFile",
    "writeFileSync",
}
MJS_RAW_PROMISE_FILE_WRITE_FUNCTIONS = {"appendFile", "writeFile"}
MJS_RAW_FS_MODULES = {"fs", "node:fs"}
MJS_RAW_FS_PROMISE_MODULES = {"fs/promises", "node:fs/promises"}
