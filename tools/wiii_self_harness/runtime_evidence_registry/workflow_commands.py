"""Inspect workflow shell commands, probe invocations, and test execution."""

from __future__ import annotations

import re
import shlex
from pathlib import PurePosixPath

from .workflow_structure import (
    _workflow_checkout_block_disables_persisted_credentials,
    _workflow_job_blocks,
    _workflow_step_blocks,
    _workflow_step_uses_action,
)


def _normalize_shell_continuations(text: str) -> str:
    return re.sub(r"\\\r?\n\s*", " ", text)


def _strip_unquoted_shell_comments(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        in_single_quote = False
        in_double_quote = False
        escaped = False
        comment_index: int | None = None
        for index, char in enumerate(line):
            if escaped:
                escaped = False
                continue
            if char == "\\" and not in_single_quote:
                escaped = True
                continue
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                continue
            if char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                continue
            if (
                char == "#"
                and not in_single_quote
                and not in_double_quote
                and (index == 0 or line[index - 1].isspace())
            ):
                comment_index = index
                break
        cleaned_lines.append(line if comment_index is None else line[:comment_index].rstrip())
    return "\n".join(cleaned_lines)


def _workflow_run_command_text(block: str) -> str:
    normalized_block = _normalize_shell_continuations(block).replace("\\", "/")
    return _strip_unquoted_shell_comments(normalized_block)


def _text_mentions_bounded_token(text: str, token: str) -> bool:
    normalized_text = text.replace("\\", "/")
    normalized_token = token.replace("\\", "/")
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9_./-]){re.escape(normalized_token)}(?![A-Za-z0-9_./-])",
            normalized_text,
        )
    )


def _workflow_probe_invocation_blocks(workflow_text: str, probe_path: str) -> list[str]:
    return [
        block
        for block in _workflow_step_blocks(workflow_text)
        if "run:" in block and _workflow_run_block_invokes_probe(block, probe_path)
    ]


def _workflow_probe_blocks_have_guards(
    probe_blocks: list[str],
    *,
    probe_path: str,
    guard_tokens: list[str],
) -> bool:
    return all(
        any(
            _workflow_probe_block_has_guard(probe_block, probe_path, guard_token)
            for probe_block in probe_blocks
        )
        for guard_token in guard_tokens
    )


def _workflow_probe_block_has_guard(
    block: str,
    probe_path: str,
    guard_token: str,
) -> bool:
    return any(
        guard_token in arguments[2:]
        for arguments in _workflow_probe_command_argument_lists(block, probe_path)
    )


def _workflow_probe_block_writes_artifact(
    block: str,
    *,
    probe_path: str,
    artifact: str,
) -> bool:
    for arguments in _workflow_probe_command_argument_lists(block, probe_path):
        for index, argument in enumerate(arguments[2:]):
            if argument == "--out":
                out_index = index + 3
                if out_index < len(arguments) and arguments[out_index] == artifact:
                    return True
            if argument.startswith("--out=") and argument.split("=", 1)[1] == artifact:
                return True
    return False


def _workflow_run_block_invokes_probe(block: str, probe_path: str) -> bool:
    return bool(_workflow_probe_command_lines(block, probe_path))


def _workflow_probe_command_lines(block: str, probe_path: str) -> list[str]:
    normalized_probe_path = probe_path.replace("\\", "/")
    suffix = PurePosixPath(normalized_probe_path).suffix
    path_tokens = _workflow_probe_path_tokens(normalized_probe_path)
    return [
        line
        for line in _workflow_run_command_lines(block)
        if _workflow_command_line_invokes_probe(
            line,
            suffix=suffix,
            path_tokens=path_tokens,
        )
    ]


def _workflow_probe_command_argument_lists(block: str, probe_path: str) -> list[list[str]]:
    normalized_probe_path = probe_path.replace("\\", "/")
    suffix = PurePosixPath(normalized_probe_path).suffix
    path_tokens = _workflow_probe_path_tokens(normalized_probe_path)
    return [
        arguments
        for line in _workflow_run_command_lines(block)
        if _workflow_command_arguments_invoke_probe(
            arguments := _workflow_command_arguments(line),
            suffix=suffix,
            path_tokens=path_tokens,
        )
    ]


def _workflow_command_line_invokes_probe(
    command_line: str,
    *,
    suffix: str,
    path_tokens: set[str],
) -> bool:
    arguments = _workflow_command_arguments(command_line)
    return _workflow_command_arguments_invoke_probe(
        arguments,
        suffix=suffix,
        path_tokens=path_tokens,
    )


def _workflow_command_arguments_invoke_probe(
    arguments: list[str],
    *,
    suffix: str,
    path_tokens: set[str],
) -> bool:
    if len(arguments) < 2:
        return False
    if _workflow_command_arguments_have_shell_control(arguments):
        return False
    runner = arguments[0]
    if suffix == ".py":
        if not re.fullmatch(r"python(?:3(?:\.[0-9]+)?)?", runner):
            return False
    elif suffix == ".mjs":
        if runner != "node":
            return False
    else:
        return False
    return _workflow_command_argument_matches_path(arguments[1], path_tokens)


def _workflow_command_arguments_have_shell_control(arguments: list[str]) -> bool:
    shell_tokens = (";", "&&", "||", "|", "&")
    return any(any(token in argument for token in shell_tokens) for argument in arguments)


def _workflow_command_arguments(command_line: str) -> list[str]:
    try:
        return [argument.replace("\\", "/") for argument in shlex.split(command_line)]
    except ValueError:
        return []


def _workflow_command_argument_matches_path(
    argument: str,
    path_tokens: set[str],
) -> bool:
    normalized_argument = argument.replace("\\", "/")
    normalized_candidates = {
        normalized_argument,
        normalized_argument.removeprefix("./"),
        str(PurePosixPath(normalized_argument)),
    }
    return any(candidate in path_tokens for candidate in normalized_candidates)


def _workflow_run_block_starts_with_strict_shell(block: str) -> bool:
    if "run: |" not in block:
        return True
    lines = block.splitlines()
    run_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^\s*(?:-\s*)?run:\s*\|\s*$", line)
        ),
        None,
    )
    if run_index is None:
        return True
    for line in lines[run_index + 1:]:
        stripped = line.strip()
        if not stripped:
            continue
        return stripped == "set -euo pipefail"
    return False


def _workflow_job_checks_out_before_probe(job_block: str, probe_path: str) -> bool:
    checkout_seen = False
    for block in _workflow_step_blocks(job_block):
        if _workflow_step_uses_action(block, "actions/checkout"):
            if _workflow_checkout_block_disables_persisted_credentials(block):
                checkout_seen = True
            continue
        if "run:" in block and _workflow_run_block_invokes_probe(block, probe_path):
            return checkout_seen
    return False


def _workflow_repo_path_tokens(repo_path: str) -> set[str]:
    normalized_path = repo_path.replace("\\", "/")
    tokens = {normalized_path}
    for prefix in ("maritime-ai-service/", "wiii-desktop/"):
        if normalized_path.startswith(prefix):
            tokens.add(normalized_path[len(prefix):])
    return {token for token in tokens if token}


def _workflow_probe_path_tokens(probe_path: str) -> set[str]:
    return _workflow_repo_path_tokens(probe_path)


def _workflow_contract_test_path_tokens(test_path: str) -> set[str]:
    return _workflow_repo_path_tokens(test_path)


def _workflow_run_block_mentions_path_token(block: str, path_tokens: set[str]) -> bool:
    command_text = _workflow_run_command_text(block)
    return any(
        _text_mentions_bounded_token(command_text, token)
        for token in path_tokens
    )


def _workflow_runs_contract_test(workflow_text: str, test_path: str) -> bool:
    normalized_test_path = test_path.replace("\\", "/")
    path_tokens = _workflow_contract_test_path_tokens(normalized_test_path)
    suffix = PurePosixPath(normalized_test_path).suffix
    for block in _workflow_step_blocks(workflow_text):
        if "run:" not in block:
            continue
        if not _workflow_run_block_mentions_path_token(block, path_tokens):
            continue
        if any(
            _workflow_command_line_runs_contract_test(
                line,
                suffix=suffix,
                path_tokens=path_tokens,
            )
            for line in _workflow_run_command_lines(block)
        ):
            return True
    return False


def _workflow_contract_job_runs_test(workflow_text: str, test_path: str) -> bool:
    contract_block = next(
        (block for job_name, block in _workflow_job_blocks(workflow_text) if job_name == "contract"),
        "",
    )
    if not contract_block:
        return False
    return _workflow_runs_contract_test(contract_block, test_path)


def _workflow_contract_job_runs_node_script(workflow_text: str, script_path: str) -> bool:
    contract_block = next(
        (block for job_name, block in _workflow_job_blocks(workflow_text) if job_name == "contract"),
        "",
    )
    if not contract_block:
        return False
    path_tokens = _workflow_contract_test_path_tokens(script_path)
    for block in _workflow_step_blocks(contract_block):
        if "run:" not in block:
            continue
        if not _workflow_run_block_mentions_path_token(block, path_tokens):
            continue
        if any(
            _workflow_command_line_runs_node_script(line, path_tokens=path_tokens)
            for line in _workflow_run_command_lines(block)
        ):
            return True
    return False


def _workflow_contract_job_checks_out_before_test(
    workflow_text: str,
    test_path: str,
) -> bool:
    contract_block = next(
        (block for job_name, block in _workflow_job_blocks(workflow_text) if job_name == "contract"),
        "",
    )
    if not contract_block:
        return False
    return _workflow_job_checks_out_before_contract_test(contract_block, test_path)


def _workflow_job_checks_out_before_contract_test(job_block: str, test_path: str) -> bool:
    path_tokens = _workflow_contract_test_path_tokens(test_path)
    suffix = PurePosixPath(test_path.replace("\\", "/")).suffix
    checkout_seen = False
    for block in _workflow_step_blocks(job_block):
        if _workflow_step_uses_action(block, "actions/checkout"):
            if _workflow_checkout_block_disables_persisted_credentials(block):
                checkout_seen = True
            continue
        if "run:" not in block:
            continue
        if not _workflow_run_block_mentions_path_token(block, path_tokens):
            continue
        if any(
            _workflow_command_line_runs_contract_test(
                line,
                suffix=suffix,
                path_tokens=path_tokens,
            )
            for line in _workflow_run_command_lines(block)
        ):
            return checkout_seen
    return False


def _workflow_run_command_lines(block: str) -> list[str]:
    lines: list[str] = []
    for raw_line in _workflow_run_command_text(block).splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        match = re.match(r"^(?:-\s*)?run:\s*(.*?)\s*$", stripped)
        if match:
            inline_command = match.group(1).strip()
            if inline_command and inline_command not in {"|", "|-", ">", ">-"}:
                lines.append(inline_command)
            continue
        lines.append(stripped)
    return lines


def _workflow_command_line_runs_contract_test(
    command_line: str,
    *,
    suffix: str,
    path_tokens: set[str],
) -> bool:
    if not any(_text_mentions_bounded_token(command_line, token) for token in path_tokens):
        return False
    runner_pattern = (
        re.compile(r"^(?:python\s+-m\s+)?pytest(?:\s|$)")
        if suffix == ".py"
        else re.compile(r"^(?:npx\s+)?vitest(?:\s|$)")
    )
    return bool(runner_pattern.search(command_line))


def _workflow_command_line_runs_node_script(
    command_line: str,
    *,
    path_tokens: set[str],
) -> bool:
    arguments = _workflow_command_arguments(command_line)
    if len(arguments) < 2:
        return False
    if _workflow_command_arguments_have_shell_control(arguments):
        return False
    return arguments[0] == "node" and _workflow_command_argument_matches_path(
        arguments[1],
        path_tokens,
    )


def _workflow_command_enables_shell_xtrace(command_line: str) -> bool:
    try:
        arguments = shlex.split(command_line, posix=True)
    except ValueError:
        return False
    if not arguments:
        return False
    command = arguments[0]
    if command == "set":
        return any(
            argument.startswith("-")
            and not argument.startswith("--")
            and "x" in argument[1:]
            for argument in arguments[1:]
        ) or ("-o" in arguments[1:] and "xtrace" in arguments[1:])
    if command in {"bash", "sh"}:
        return any(
            argument.startswith("-")
            and not argument.startswith("--")
            and "x" in argument[1:]
            for argument in arguments[1:]
        )
    return False
