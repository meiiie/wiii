"""Inspect live-job gates and production override bindings."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from .constants import (
    PRODUCTION_OVERRIDE_APPEND_LINE,
    PRODUCTION_OVERRIDE_ARGS_EXPANSION,
    PRODUCTION_OVERRIDE_ENV,
    PRODUCTION_OVERRIDE_ENV_VALUE,
    PRODUCTION_OVERRIDE_FLAG,
    PRODUCTION_OVERRIDE_GUARD_LINE,
    SECRET_REFERENCE_RE,
)
from .workflow_commands import (
    _workflow_command_arguments,
    _workflow_command_arguments_invoke_probe,
    _workflow_probe_path_tokens,
    _workflow_run_block_invokes_probe,
    _workflow_run_command_text,
)
from .workflow_structure import (
    _workflow_env_blocks,
    _workflow_job_blocks,
    _workflow_job_if_text,
    _workflow_mapping_block,
    _workflow_mapping_direct_scalar_values,
    _workflow_step_blocks,
)


def _workflow_text_references_secrets(text: str) -> bool:
    return bool(SECRET_REFERENCE_RE.search(text))


def _workflow_job_block_has_gate(job_block: str, token: str) -> bool:
    if_text = _workflow_job_if_text(job_block)
    if token.startswith(("allow_", "run_")):
        return (
            "github.event_name == 'workflow_dispatch'" in if_text
            and f"inputs.{token} == true" in if_text
        )
    if token.startswith("WIII_") and token.endswith("_EVIDENCE_ENABLED"):
        return (
            "github.event_name == 'schedule'" in if_text
            and f"vars.{token} == '1'" in if_text
        )
    return token in if_text


def _workflow_job_if_matches_dispatch_or_schedule_gates(
    job_block: str,
    gate_tokens: list[str],
) -> bool:
    dispatch_tokens = [
        token
        for token in gate_tokens
        if token.startswith(("allow_", "run_"))
    ]
    schedule_tokens = [
        token
        for token in gate_tokens
        if token.startswith("WIII_") and token.endswith("_EVIDENCE_ENABLED")
    ]
    if len(dispatch_tokens) != 1 or len(schedule_tokens) != 1:
        return False

    dispatch_token = dispatch_tokens[0]
    schedule_token = schedule_tokens[0]
    normalized_if = _normalize_workflow_if_expression(_workflow_job_if_text(job_block))
    dispatch_gate = (
        "(github.event_name=='workflow_dispatch'"
        f"&&inputs.{dispatch_token}==true)"
    )
    schedule_gate = (
        "(github.event_name=='schedule'"
        f"&&vars.{schedule_token}=='1')"
    )
    expected_orders = {
        dispatch_gate + "||" + schedule_gate,
        schedule_gate + "||" + dispatch_gate,
    }
    return normalized_if in expected_orders | {
        f"({expected})" for expected in expected_orders
    }


def _workflow_job_if_matches_any_dispatch_or_schedule_gate_pair(
    job_block: str,
    gate_tokens: list[str],
) -> bool:
    dispatch_tokens = sorted(
        {
            token
            for token in gate_tokens
            if token.startswith(("allow_", "run_"))
        }
    )
    schedule_tokens = sorted(
        {
            token
            for token in gate_tokens
            if token.startswith("WIII_") and token.endswith("_EVIDENCE_ENABLED")
        }
    )
    return any(
        _workflow_job_if_matches_dispatch_or_schedule_gates(
            job_block,
            [dispatch_token, schedule_token],
        )
        for dispatch_token in dispatch_tokens
        for schedule_token in schedule_tokens
    )


def _workflow_production_override_flags_are_guarded(workflow_text: str) -> bool:
    found_flag = False
    for block in _workflow_step_blocks(workflow_text):
        in_production_guard = False
        heredoc_delimiter: str | None = None
        for raw_line in _workflow_run_command_text(block).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if heredoc_delimiter is not None:
                if line == heredoc_delimiter:
                    heredoc_delimiter = None
                continue
            heredoc_delimiter = _workflow_shell_heredoc_delimiter(line)
            if line == PRODUCTION_OVERRIDE_GUARD_LINE:
                in_production_guard = True
                continue
            if line == "fi" and in_production_guard:
                in_production_guard = False
                continue
            if PRODUCTION_OVERRIDE_FLAG not in line:
                continue
            found_flag = True
            if not in_production_guard or line != PRODUCTION_OVERRIDE_APPEND_LINE:
                return False
    return found_flag


def _workflow_production_override_env_is_manual_only(workflow_text: str) -> bool:
    values = [
        value
        for block in _workflow_env_blocks(workflow_text)
        for value in _workflow_mapping_direct_scalar_values(
            block,
            PRODUCTION_OVERRIDE_ENV,
        )
    ]
    return bool(values) and all(value == PRODUCTION_OVERRIDE_ENV_VALUE for value in values)


def _workflow_production_override_flag_steps_bind_env(workflow_text: str) -> bool:
    flag_blocks = [
        block
        for block in _workflow_step_blocks(workflow_text)
        if _workflow_step_has_executed_production_override_flag(block)
    ]
    return bool(flag_blocks) and all(
        _workflow_step_binds_production_override_env(block) for block in flag_blocks
    )


def _workflow_production_override_flag_steps_invoke_registered_probe(
    workflow_text: str,
    probe_paths: list[str],
) -> bool:
    flag_blocks = [
        block
        for block in _workflow_step_blocks(workflow_text)
        if _workflow_step_has_executed_production_override_flag(block)
    ]
    return bool(probe_paths) and bool(flag_blocks) and all(
        any(_workflow_run_block_invokes_probe(block, probe_path) for probe_path in probe_paths)
        for block in flag_blocks
    )


def _workflow_production_override_flag_steps_pass_args_to_probe(
    workflow_text: str,
    probe_paths: list[str],
) -> bool:
    flag_blocks = [
        block
        for block in _workflow_step_blocks(workflow_text)
        if _workflow_step_has_executed_production_override_flag(block)
    ]
    return bool(probe_paths) and bool(flag_blocks) and all(
        any(
            _workflow_probe_command_passes_production_override_args(block, probe_path)
            for probe_path in probe_paths
        )
        for block in flag_blocks
    )


def _workflow_production_override_registered_probe_steps_pass_args(
    workflow_text: str,
    probe_paths: list[str],
) -> bool:
    step_blocks = _workflow_step_blocks(workflow_text)
    return all(
        any(
            _workflow_probe_command_passes_production_override_args(block, probe_path)
            for block in step_blocks
        )
        for probe_path in probe_paths
    )


def _workflow_probe_command_passes_production_override_args(
    block: str,
    probe_path: str,
) -> bool:
    production_append_seen = False
    heredoc_delimiter: str | None = None
    normalized_probe_path = probe_path.replace("\\", "/")
    suffix = PurePosixPath(normalized_probe_path).suffix
    path_tokens = _workflow_probe_path_tokens(normalized_probe_path)
    for raw_line in _workflow_run_command_text(block).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if heredoc_delimiter is not None:
            if line == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        heredoc_delimiter = _workflow_shell_heredoc_delimiter(line)
        if line == PRODUCTION_OVERRIDE_APPEND_LINE:
            production_append_seen = True
            continue
        if production_append_seen and _workflow_shell_resets_args_array(line):
            return False
        arguments = _workflow_command_arguments(line)
        if not _workflow_command_arguments_invoke_probe(
            arguments,
            suffix=suffix,
            path_tokens=path_tokens,
        ):
            continue
        return production_append_seen and PRODUCTION_OVERRIDE_ARGS_EXPANSION in arguments[2:]
    return False


def _workflow_shell_resets_args_array(line: str) -> bool:
    if re.match(r"^args(?:=|\[)", line):
        return True
    arguments = _workflow_command_arguments(line)
    if not arguments:
        return False
    if arguments[0] == "unset":
        return any(_workflow_shell_argument_targets_args_array(argument) for argument in arguments[1:])
    if arguments[0] in {"declare", "typeset", "local"}:
        return any(
            _workflow_shell_argument_targets_args_array(argument)
            for argument in arguments[1:]
            if not argument.startswith("-")
        )
    if arguments[0] in {"read", "readarray", "mapfile"}:
        return any(
            _workflow_shell_argument_targets_args_array(argument)
            for argument in arguments[1:]
            if not argument.startswith("-") and not argument.startswith("<")
        )
    return False


def _workflow_shell_argument_targets_args_array(argument: str) -> bool:
    target = argument.split("=", 1)[0]
    return target == "args" or target.startswith("args[")


def _workflow_step_has_executed_production_override_flag(block: str) -> bool:
    heredoc_delimiter: str | None = None
    for raw_line in _workflow_run_command_text(block).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if heredoc_delimiter is not None:
            if line == heredoc_delimiter:
                heredoc_delimiter = None
            continue
        heredoc_delimiter = _workflow_shell_heredoc_delimiter(line)
        if PRODUCTION_OVERRIDE_FLAG in line:
            return True
    return False


def _workflow_step_binds_production_override_env(block: str) -> bool:
    values = _workflow_mapping_direct_scalar_values(
        _workflow_mapping_block(block, "env"),
        PRODUCTION_OVERRIDE_ENV,
    )
    return values == [PRODUCTION_OVERRIDE_ENV_VALUE]


def _workflow_shell_heredoc_delimiter(line: str) -> str | None:
    match = re.search(r"(?<!<)<<-?\s*(?!<)(\S+)", line)
    if not match:
        return None
    delimiter = match.group(1).split(";", 1)[0].strip()
    if len(delimiter) >= 2 and delimiter[0] == delimiter[-1] and delimiter[0] in {"'", '"'}:
        delimiter = delimiter[1:-1]
    return delimiter or None


def _normalize_workflow_if_expression(expression: str) -> str:
    normalized = "".join(expression.split())
    if normalized.startswith("${{") and normalized.endswith("}}"):
        normalized = normalized[3:-2]
    return normalized


def _workflow_has_job_if_gate(workflow_text: str, token: str) -> bool:
    return any(
        _workflow_job_block_has_gate(job_block, token)
        for _, job_block in _workflow_job_blocks(workflow_text)
    )
