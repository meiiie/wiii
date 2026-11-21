"""Validate evidence probes and their shared output helpers."""

from __future__ import annotations

from pathlib import Path

from .checks import ValidationChecks
from .constants import (
    MJS_RUNTIME_EVIDENCE_HELPER_ATOMIC_TOKENS,
    MJS_RUNTIME_EVIDENCE_HELPER_TEST_NAME,
    PYTHON_RUNTIME_EVIDENCE_HELPER_ATOMIC_TOKENS,
    PYTHON_RUNTIME_EVIDENCE_HELPER_TEST_NAME,
)
from .javascript_probe import (
    _mjs_probe_fail_closed_guard_tokens,
    _mjs_probe_fail_function_exits_nonzero,
    _mjs_probe_forwards_output_to_summary_env,
    _mjs_probe_handles_output_argument,
    _mjs_probe_raw_file_write_calls,
)
from .python_probe import (
    _python_probe_argparse_flags,
    _python_probe_argparse_store_true_flags,
    _python_probe_calls_output_helper_with_output_path,
    _python_probe_imports_runtime_evidence_output_helper,
    _python_probe_raw_file_write_calls,
)
from .workflow_commands import (
    _workflow_contract_job_runs_node_script,
    _workflow_contract_job_runs_test,
)
from .workflow_structure import _workflow_event_paths


class ProbeChecks(ValidationChecks):
    def require_python_probe_cli_guard_tokens(
        self,
        probe_text: str,
        *,
        guard_tokens: list[str],
        context: str,
    ) -> None:
        parser_flags = _python_probe_argparse_store_true_flags(probe_text)
        for token in guard_tokens:
            if token in parser_flags:
                self.pass_check()
            else:
                self.error(
                    f"{context}: live guard token {token!r} must be an argparse "
                    "store_true CLI flag in the registered Python probe"
                )

    def require_python_probe_output_argument(
        self,
        probe_text: str,
        *,
        context: str,
    ) -> None:
        parser_flags = _python_probe_argparse_flags(probe_text)
        if "--out" in parser_flags:
            self.pass_check()
            return
        self.error(
            f"{context}: registered Python probe must define `--out` as an "
            "argparse CLI flag"
        )

    def require_python_probe_output_helper_import(
        self,
        probe_text: str,
        *,
        context: str,
    ) -> None:
        if _python_probe_imports_runtime_evidence_output_helper(probe_text):
            self.pass_check()
            return
        self.error(
            f"{context}: registered Python probe must import emit_json_payload "
            "from runtime_evidence_output"
        )

    def require_python_probe_output_helper_call(
        self,
        probe_text: str,
        *,
        context: str,
    ) -> None:
        if _python_probe_calls_output_helper_with_output_path(probe_text):
            self.pass_check()
            return
        self.error(
            f"{context}: registered Python probe must call emit_json_payload "
            "with an output path argument"
        )

    def require_python_probe_no_raw_file_writes(
        self,
        probe_text: str,
        *,
        context: str,
    ) -> None:
        raw_write_calls = _python_probe_raw_file_write_calls(probe_text)
        if not raw_write_calls:
            self.pass_check()
            return
        rendered = ", ".join(raw_write_calls)
        self.error(
            f"{context}: registered Python probe must not write evidence files "
            f"outside runtime_evidence_output: {rendered}"
        )

    def require_python_runtime_evidence_output_helper(
        self,
        probe_path: Path,
        *,
        context: str,
    ) -> None:
        helper_path = probe_path.with_name("runtime_evidence_output.py")
        self.require_runtime_evidence_output_helper_atomic_tokens(
            helper_path,
            tokens=PYTHON_RUNTIME_EVIDENCE_HELPER_ATOMIC_TOKENS,
            context=context,
        )

    def require_mjs_probe_cli_guard_tokens(
        self,
        probe_text: str,
        *,
        guard_tokens: list[str],
        context: str,
    ) -> None:
        if _mjs_probe_fail_function_exits_nonzero(probe_text):
            self.pass_check()
        else:
            self.error(
                f"{context}: registered MJS probe fail() must call "
                "process.exit with a non-zero literal status"
            )
        guarded_flags = _mjs_probe_fail_closed_guard_tokens(probe_text)
        for token in guard_tokens:
            if token in guarded_flags:
                self.pass_check()
            else:
                self.error(
                    f"{context}: live guard token {token!r} must be checked by "
                    "a fail-closed process.argv.includes(...) guard in the "
                    "registered MJS probe"
                )

    def require_mjs_probe_output_argument(
        self,
        probe_text: str,
        *,
        context: str,
    ) -> None:
        if _mjs_probe_handles_output_argument(probe_text):
            self.pass_check()
        else:
            self.error(
                f"{context}: registered MJS probe must parse `--out` from "
                "process.argv"
            )
        if _mjs_probe_forwards_output_to_summary_env(probe_text):
            self.pass_check()
        else:
            self.error(
                f"{context}: registered MJS probe must forward parsed `--out` "
                "path to WIII_RUNTIME_FLOW_BROWSER_REPLAY_SUMMARY_JSON"
            )

    def require_mjs_probe_no_raw_file_writes(
        self,
        probe_text: str,
        *,
        context: str,
    ) -> None:
        raw_write_calls = _mjs_probe_raw_file_write_calls(probe_text)
        if not raw_write_calls:
            self.pass_check()
            return
        rendered = ", ".join(raw_write_calls)
        self.error(
            f"{context}: registered MJS probe must not write evidence files "
            f"outside runtime-evidence-output.mjs: {rendered}"
        )

    def require_mjs_runtime_evidence_output_helper(
        self,
        probe_path: Path,
        *,
        context: str,
    ) -> None:
        helper_path = probe_path.with_name("runtime-evidence-output.mjs")
        self.require_runtime_evidence_output_helper_atomic_tokens(
            helper_path,
            tokens=MJS_RUNTIME_EVIDENCE_HELPER_ATOMIC_TOKENS,
            context=context,
        )

    def require_runtime_evidence_output_helper_atomic_tokens(
        self,
        helper_path: Path,
        *,
        tokens: list[str],
        context: str,
    ) -> None:
        relative_path = helper_path.relative_to(self.repo_root).as_posix()
        _, helper_text = self.require_file_text(relative_path, context=context)
        if not helper_text:
            return
        missing = [token for token in tokens if token not in helper_text]
        if not missing:
            self.passed_checks += len(tokens)
            return
        rendered = ", ".join(repr(token) for token in missing)
        self.error(
            f"{context}: runtime evidence output helper {relative_path!r} must "
            f"use atomic temp-file writes; missing token(s): {rendered}"
        )

    def require_workflow_runtime_evidence_output_helper_contract(
        self,
        workflow_text: str,
        *,
        probe_path: Path | None,
        context: str,
    ) -> None:
        helper_paths = _runtime_evidence_output_helper_paths_for_probe(
            probe_path,
            repo_root=self.repo_root,
        )
        if helper_paths is None:
            return
        helper_path, helper_test_path = helper_paths
        for event_name in ("pull_request", "push"):
            paths = _workflow_event_paths(workflow_text, event_name)
            for required_path in (helper_path, helper_test_path):
                if required_path in paths:
                    self.pass_check()
                else:
                    self.error(
                        f"{context}.{event_name}: missing paths filter "
                        f"{required_path!r}"
                    )
        if helper_test_path.endswith(".py"):
            helper_test_runs = _workflow_contract_job_runs_test(
                workflow_text,
                helper_test_path,
            )
        else:
            helper_test_runs = _workflow_contract_job_runs_node_script(
                workflow_text,
                helper_test_path,
            )
        if helper_test_runs:
            self.pass_check()
            return
        self.error(
            f"{context}: contract job must execute runtime evidence output "
            f"helper test {helper_test_path!r}"
        )


def _runtime_evidence_output_helper_paths_for_probe(
    probe_path: Path | None,
    *,
    repo_root: Path,
) -> tuple[str, str] | None:
    if probe_path is None:
        return None
    try:
        relative_probe = probe_path.relative_to(repo_root)
    except ValueError:
        return None
    if probe_path.suffix == ".py":
        helper_path = relative_probe.with_name("runtime_evidence_output.py")
        if relative_probe.parts and relative_probe.parts[0] == "maritime-ai-service":
            helper_test_path = Path(
                "maritime-ai-service",
                "tests",
                "unit",
                PYTHON_RUNTIME_EVIDENCE_HELPER_TEST_NAME,
            )
        else:
            helper_test_path = Path("tests", PYTHON_RUNTIME_EVIDENCE_HELPER_TEST_NAME)
        return helper_path.as_posix(), helper_test_path.as_posix()
    if probe_path.suffix == ".mjs":
        return (
            relative_probe.with_name("runtime-evidence-output.mjs").as_posix(),
            relative_probe.with_name(MJS_RUNTIME_EVIDENCE_HELPER_TEST_NAME).as_posix(),
        )
    return None
