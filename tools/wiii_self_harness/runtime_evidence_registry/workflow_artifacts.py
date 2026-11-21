"""Match artifact validation and upload steps to registered evidence."""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from .constants import CANONICAL_ARTIFACT_VALIDATOR_PATHS
from .workflow_commands import (
    _text_mentions_bounded_token,
    _workflow_command_arguments,
    _workflow_probe_block_has_guard,
    _workflow_probe_blocks_have_guards,
    _workflow_probe_invocation_blocks,
    _workflow_run_block_invokes_probe,
    _workflow_run_command_text,
)
from .workflow_gates import _workflow_job_if_matches_dispatch_or_schedule_gates
from .workflow_structure import (
    _workflow_block_direct_scalar_values,
    _workflow_block_sets_unique_env_flag,
    _workflow_job_needs_contract,
    _workflow_mapping_block,
    _workflow_mapping_direct_scalar_values,
    _workflow_step_blocks,
    _workflow_step_uses_action,
)


@dataclass(frozen=True)
class DiagnosticUploadSpec:
    requirement_id: str
    artifact: str
    path: str
    artifact_tokens: tuple[str, ...]
    if_no_files_found: str
    retention_days: int


def _workflow_validator_commands(workflow_text: str) -> list[str]:
    commands: list[str] = []
    for block in _workflow_step_blocks(workflow_text):
        if "run:" not in block:
            continue
        command_text = _workflow_run_command_text(block)
        commands.extend(
            line.strip()
            for line in command_text.splitlines()
            if "validate_runtime_evidence_artifact.py" in line
        )
    return commands


def _workflow_upload_artifact_blocks(workflow_text: str) -> list[str]:
    return [
        block
        for block in _workflow_step_blocks(workflow_text)
        if _workflow_step_uses_action(block, "actions/upload-artifact")
    ]


def _workflow_upload_artifact_names(upload_block: str) -> list[str]:
    return _workflow_mapping_direct_scalar_values(
        _workflow_upload_with_block(upload_block),
        "name",
    )


def _workflow_upload_with_block(upload_block: str) -> str:
    return _workflow_mapping_block(upload_block, "with")


def _workflow_upload_with_scalar_field_equals(
    upload_block: str,
    field: str,
    expected: str,
) -> bool:
    return expected in _workflow_mapping_direct_scalar_values(
        _workflow_upload_with_block(upload_block),
        field,
    )


def _workflow_upload_artifact_retention_days(upload_block: str) -> int | None:
    values = _workflow_mapping_direct_scalar_values(
        _workflow_upload_with_block(upload_block),
        "retention-days",
    )
    if not values or not values[0].isdigit():
        return None
    return int(values[0])


def _workflow_upload_artifact_paths(upload_block: str) -> list[str]:
    with_block = _workflow_upload_with_block(upload_block)
    lines = with_block.splitlines()
    if not lines:
        return []
    parent_indent = len(lines[0]) - len(lines[0].lstrip(" "))
    child_indent = next(
        (
            len(line) - len(line.lstrip(" "))
            for line in lines[1:]
            if line.strip()
            and not line.strip().startswith("#")
            and len(line) - len(line.lstrip(" ")) > parent_indent
        ),
        None,
    )
    if child_indent is None:
        return []
    path_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(rf"^\s{{{child_indent}}}path:\s*", line)
        ),
        None,
    )
    if path_index is None:
        return []
    path_line = lines[path_index]
    path_indent = len(path_line) - len(path_line.lstrip(" "))
    value = path_line.split(":", 1)[1].strip()
    if value and value not in {"|", "|-", ">", ">-"}:
        return [value.strip("\"'")]

    paths: list[str] = []
    for line in lines[path_index + 1:]:
        if line.strip() == "":
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= path_indent:
            break
        stripped = line.strip()
        if re.match(r"^[A-Za-z-]+:\s*", stripped):
            break
        paths.append(stripped.strip("\"'"))
    return paths


def _workflow_upload_paths_are_narrow_json(paths: list[str], artifact: str) -> bool:
    if len(paths) != 1:
        return False
    for raw_path in paths:
        normalized = _workflow_normalized_relative_literal(raw_path)
        if not normalized:
            return False
        if any(token in normalized for token in ("*", "?", "[", "]", "{", "}", "$", "%")):
            return False
        if normalized.startswith("~"):
            return False
        posix_path = PurePosixPath(normalized)
        parts = posix_path.parts
        if posix_path.is_absolute() or ".." in parts or not parts:
            return False
        if posix_path.suffix != ".json":
            return False
        return posix_path.name == artifact
    return False


def _workflow_upload_paths_match_expected(
    paths: list[str],
    *,
    artifact: str,
    expected_path: str,
) -> bool:
    return (
        _workflow_upload_paths_are_narrow_json(paths, artifact)
        and _workflow_normalized_relative_literal(paths[0]) == expected_path
    )


def _workflow_upload_block_binds_artifact(
    upload_block: str,
    *,
    artifact: str,
    artifact_token: str,
) -> bool:
    if not _workflow_upload_block_has_artifact_token(upload_block, artifact_token):
        return False
    return _workflow_upload_paths_are_narrow_json(
        _workflow_upload_artifact_paths(upload_block),
        artifact,
    )


def _workflow_upload_block_binds_artifact_path(
    upload_block: str,
    *,
    artifact: str,
    artifact_token: str,
    expected_path: str,
) -> bool:
    if not _workflow_upload_block_has_artifact_token(upload_block, artifact_token):
        return False
    return _workflow_upload_paths_match_expected(
        _workflow_upload_artifact_paths(upload_block),
        artifact=artifact,
        expected_path=expected_path,
    )


def _workflow_upload_block_has_artifact_token(upload_block: str, artifact_token: str) -> bool:
    return artifact_token in _workflow_upload_artifact_names(upload_block)


def _workflow_validation_command_matches(
    command: str,
    *,
    artifact: str,
    requirement_id: str,
) -> bool:
    command_line = re.sub(r"^(?:-\s*)?run:\s*", "", command.strip())
    arguments = _workflow_command_arguments(command_line)
    return _workflow_artifact_validator_arguments_match(
        arguments,
        artifact=artifact,
        requirement_id=requirement_id,
    )


def _workflow_block_validates_artifact(
    block: str,
    *,
    artifact: str,
    requirement_id: str,
) -> bool:
    return any(
        _workflow_validation_command_matches(
            command,
            artifact=artifact,
            requirement_id=requirement_id,
        )
        for command in _workflow_validator_commands(block)
    )


def _workflow_validation_block_expected_upload_path(
    block: str,
    *,
    artifact: str,
    requirement_id: str,
) -> str | None:
    if not _workflow_block_validates_artifact(
        block,
        artifact=artifact,
        requirement_id=requirement_id,
    ):
        return None
    return _workflow_expected_upload_path_for_validation_block(block, artifact)


def _workflow_job_validation_expected_upload_paths(
    job_block: str,
    *,
    artifact: str,
    requirement_id: str,
) -> list[str]:
    paths: list[str] = []
    for block in _workflow_step_blocks(job_block):
        expected_path = _workflow_validation_block_expected_upload_path(
            block,
            artifact=artifact,
            requirement_id=requirement_id,
        )
        if expected_path is not None:
            paths.append(expected_path)
    return paths


def _workflow_job_has_expected_uploads(
    job_block: str,
    *,
    artifact: str,
    artifact_tokens: list[str],
    expected_path: str,
) -> bool:
    upload_blocks = _workflow_upload_artifact_blocks(job_block)
    return all(
        any(
            _workflow_upload_block_binds_artifact_path(
                upload_block,
                artifact=artifact,
                artifact_token=artifact_token,
                expected_path=expected_path,
            )
            for upload_block in upload_blocks
        )
        for artifact_token in artifact_tokens
    )


def _workflow_job_has_bound_validation_upload(
    job_block: str,
    *,
    artifact: str,
    artifact_tokens: list[str],
    requirement_id: str,
) -> bool:
    return any(
        _workflow_job_has_expected_uploads(
            job_block,
            artifact=artifact,
            artifact_tokens=artifact_tokens,
            expected_path=expected_path,
        )
        for expected_path in _workflow_job_validation_expected_upload_paths(
            job_block,
            artifact=artifact,
            requirement_id=requirement_id,
        )
    )


def _workflow_secret_job_matches_registered_requirement(
    job_block: str,
    *,
    requirement_id: str,
    artifact: str,
    artifact_tokens: list[str],
    probe_path: str,
    live_flags: list[str],
    guard_tokens: list[str],
    gate_tokens: list[str],
) -> bool:
    probe_blocks = _workflow_probe_invocation_blocks(job_block, probe_path)
    return (
        all(_workflow_block_sets_unique_env_flag(job_block, flag) for flag in live_flags)
        and bool(probe_blocks)
        and _workflow_probe_blocks_have_guards(
            probe_blocks,
            probe_path=probe_path,
            guard_tokens=guard_tokens,
        )
        and _workflow_job_if_matches_dispatch_or_schedule_gates(job_block, gate_tokens)
        and _workflow_job_needs_contract(job_block)
        and _workflow_job_has_bound_validation_upload(
            job_block,
            artifact=artifact,
            artifact_tokens=artifact_tokens,
            requirement_id=requirement_id,
        )
    )


def _workflow_command_invokes_artifact_validator(command: str) -> bool:
    command_line = re.sub(r"^(?:-\s*)?run:\s*", "", command.strip())
    arguments = _workflow_command_arguments(command_line)
    return _workflow_command_arguments_invoke_artifact_validator(arguments)


def _workflow_command_arguments_invoke_artifact_validator(arguments: list[str]) -> bool:
    return (
        len(arguments) >= 2
        and bool(re.fullmatch(r"python(?:3(?:\.[0-9]+)?)?", arguments[0]))
        and _workflow_command_argument_is_canonical_artifact_validator(arguments[1])
    )


def _workflow_artifact_validator_arguments_match(
    arguments: list[str],
    *,
    artifact: str,
    requirement_id: str,
) -> bool:
    if not _workflow_command_arguments_invoke_artifact_validator(arguments):
        return False
    positionals: list[str] = []
    requirement_ids: list[str] = []
    index = 2
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--requirement-id":
            if index + 1 >= len(arguments):
                return False
            requirement_ids.append(arguments[index + 1])
            index += 2
            continue
        if argument.startswith("--requirement-id="):
            requirement_ids.append(argument.split("=", 1)[1])
            index += 1
            continue
        if argument in {"--registry", "--as-of"}:
            if index + 1 >= len(arguments):
                return False
            index += 2
            continue
        if argument.startswith("--registry=") or argument.startswith("--as-of="):
            index += 1
            continue
        if argument == "--json":
            index += 1
            continue
        if argument.startswith("-"):
            return False
        positionals.append(argument)
        index += 1
    return (
        len(positionals) == 1
        and _workflow_artifact_validator_positional_matches(positionals[0], artifact)
        and requirement_ids == [requirement_id]
    )


def _workflow_artifact_validator_positional_matches(argument: str, artifact: str) -> bool:
    return _workflow_normalized_relative_literal(argument) == artifact


def _workflow_expected_upload_path_for_validation_block(block: str, artifact: str) -> str | None:
    values = _workflow_block_direct_scalar_values(block, "working-directory")
    if len(values) > 1:
        return None
    if not values:
        return artifact

    working_directory = _workflow_safe_working_directory(values[0])
    if working_directory is None:
        return None
    return artifact if not working_directory else f"{working_directory}/{artifact}"


def _workflow_safe_working_directory(value: str) -> str | None:
    normalized = _workflow_normalized_relative_literal(value)
    if normalized in {"", "."}:
        return ""
    if any(token in normalized for token in ("*", "?", "[", "]", "{", "}", "$", "%")):
        return None
    if normalized.startswith("~"):
        return None
    posix_path = PurePosixPath(normalized)
    parts = posix_path.parts
    if posix_path.is_absolute() or ".." in parts or not parts:
        return None
    return posix_path.as_posix()


def _workflow_normalized_relative_literal(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _workflow_command_argument_is_canonical_artifact_validator(argument: str) -> bool:
    normalized_argument = posixpath.normpath(argument.replace("\\", "/"))
    return normalized_argument in CANONICAL_ARTIFACT_VALIDATOR_PATHS


def _workflow_job_has_probe_validation_upload_order(
    job_block: str,
    *,
    probe_path: str,
    artifact: str,
    artifact_tokens: list[str],
    requirement_id: str,
    guard_tokens: list[str],
) -> bool:
    probe_seen = False
    validation_seen = False
    expected_upload_path: str | None = None
    for block in _workflow_step_blocks(job_block):
        if not probe_seen:
            if (
                "run:" in block
                and _workflow_run_block_invokes_probe(block, probe_path)
                and all(
                    _workflow_probe_block_has_guard(block, probe_path, guard_token)
                    for guard_token in guard_tokens
                )
            ):
                probe_seen = True
            continue

        if not validation_seen:
            expected_path = _workflow_validation_block_expected_upload_path(
                block,
                artifact=artifact,
                requirement_id=requirement_id,
            )
            if expected_path is not None:
                validation_seen = True
                expected_upload_path = expected_path
            continue

        if (
            expected_upload_path is not None
            and _workflow_step_uses_action(block, "actions/upload-artifact")
            and all(
                _workflow_upload_block_binds_artifact_path(
                    block,
                    artifact=artifact,
                    artifact_token=artifact_token,
                    expected_path=expected_upload_path,
                )
                for artifact_token in artifact_tokens
            )
        ):
            return True
    return False


def _workflow_job_has_diagnostic_validation_upload_order(
    job_block: str,
    *,
    spec: DiagnosticUploadSpec,
) -> bool:
    validation_seen = False
    for block in _workflow_step_blocks(job_block):
        if not validation_seen:
            if _workflow_block_validates_preflight(
                block,
                artifact=spec.artifact,
                requirement_id=spec.requirement_id,
            ) and _workflow_run_block_removes_preflight_on_validation_failure(
                block,
                spec.artifact,
            ):
                validation_seen = True
            continue

        if (
            _workflow_step_uses_action(block, "actions/upload-artifact")
            and all(
                _workflow_upload_block_binds_artifact_path(
                    block,
                    artifact=spec.artifact,
                    artifact_token=token,
                    expected_path=spec.path,
                )
                for token in spec.artifact_tokens
            )
        ):
            return True
    return False


def _workflow_block_validates_preflight(
    block: str,
    *,
    artifact: str,
    requirement_id: str,
) -> bool:
    if "run:" not in block:
        return False
    command_text = _workflow_run_command_text(block)
    return (
        "validate_runtime_evidence_preflight.py" in command_text
        and _text_mentions_bounded_token(command_text, artifact)
        and _text_mentions_bounded_token(command_text, "--requirement-id")
        and _text_mentions_bounded_token(command_text, requirement_id)
    )


def _workflow_run_block_removes_preflight_on_validation_failure(
    block: str,
    artifact: str,
) -> bool:
    if "run:" not in block:
        return False
    command_text = _workflow_run_command_text(block)
    return (
        _text_mentions_bounded_token(command_text, "preflight_validation_status")
        and _text_mentions_bounded_token(command_text, f"rm -f {artifact}")
        and _text_mentions_bounded_token(command_text, 'exit "${preflight_validation_status}"')
    )
