"""Inspect Python probe arguments and output handling without running probes."""

from __future__ import annotations

import ast
import re

from .constants import PRODUCTION_OVERRIDE_FLAG


def _probe_supports_production_override(probe_text: str) -> bool:
    return (
        PRODUCTION_OVERRIDE_FLAG in probe_text
        and re.search(r"\ballow_production\b", probe_text) is not None
    )


def _python_probe_argparse_store_true_flags(probe_text: str) -> set[str]:
    try:
        tree = ast.parse(probe_text)
    except SyntaxError:
        return set()

    flags: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        has_store_true = any(
            keyword.arg == "action"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "store_true"
            for keyword in node.keywords
        )
        if not has_store_true:
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                flags.add(argument.value)
    return flags


def _python_probe_argparse_flags(probe_text: str) -> set[str]:
    try:
        tree = ast.parse(probe_text)
    except SyntaxError:
        return set()

    flags: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                flags.add(argument.value)
    return flags


def _python_probe_imports_runtime_evidence_output_helper(probe_text: str) -> bool:
    try:
        tree = ast.parse(probe_text)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "runtime_evidence_output":
            continue
        if any(alias.name == "emit_json_payload" for alias in node.names):
            return True
    return False


def _python_probe_calls_output_helper_with_output_path(probe_text: str) -> bool:
    try:
        tree = ast.parse(probe_text)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "emit_json_payload":
            continue
        if len(node.args) >= 2 and not _ast_value_is_none(node.args[1]):
            return True
        for keyword in node.keywords:
            if keyword.arg == "out_path" and not _ast_value_is_none(keyword.value):
                return True
    return False


def _ast_value_is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _python_probe_raw_file_write_calls(probe_text: str) -> list[str]:
    try:
        tree = ast.parse(probe_text)
    except SyntaxError:
        return []

    json_aliases = _python_imported_module_aliases(tree, "json")
    json_dump_names = _python_imported_member_aliases(tree, "json", {"dump"})
    os_aliases = _python_imported_module_aliases(tree, "os")
    os_write_names = _python_imported_member_aliases(tree, "os", {"open", "write"})
    file_open_names = {"open"}
    file_open_names.update(_python_imported_member_aliases(tree, "io", {"open"}))
    file_open_names.update(_python_imported_member_aliases(tree, "codecs", {"open"}))
    file_open_names.update(_python_imported_member_aliases(tree, "builtins", {"open"}))
    string_constants = _python_string_constants(tree)

    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _ast_call_is_json_dump(
            node,
            json_aliases=json_aliases,
            json_dump_names=json_dump_names,
        ):
            calls.add("json.dump")
        if raw_os_call := _ast_os_raw_file_write_call(
            node,
            os_aliases=os_aliases,
            os_write_names=os_write_names,
        ):
            calls.add(raw_os_call)
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in {"write_text", "write_bytes"}:
                calls.add(node.func.attr)
            elif node.func.attr == "open" and _python_open_call_can_write(
                node,
                string_constants=string_constants,
            ):
                calls.add("open")
        elif isinstance(node.func, ast.Name) and node.func.id in file_open_names:
            if _python_open_call_can_write(
                node,
                string_constants=string_constants,
            ):
                calls.add("open")
    return sorted(calls)


def _python_imported_module_aliases(tree: ast.AST, module_name: str) -> set[str]:
    aliases = {module_name}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name == module_name:
                aliases.add(alias.asname or alias.name)
    return aliases


def _python_imported_member_aliases(
    tree: ast.AST,
    module_name: str,
    member_names: set[str],
) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != module_name:
            continue
        for alias in node.names:
            if alias.name in member_names:
                aliases.add(alias.asname or alias.name)
    return aliases


def _python_string_constants(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            value: ast.AST
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
                if value is None:
                    continue
            else:
                continue
            resolved = _python_resolve_string_expression(
                value,
                string_constants=constants,
            )
            if resolved is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in constants:
                    constants[target.id] = resolved
                    changed = True
    return constants


def _python_resolve_string_expression(
    node: ast.AST,
    *,
    string_constants: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return string_constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _python_resolve_string_expression(
            node.left,
            string_constants=string_constants,
        )
        right = _python_resolve_string_expression(
            node.right,
            string_constants=string_constants,
        )
        if left is not None and right is not None:
            return left + right
    return None


def _python_open_call_can_write(
    node: ast.Call,
    *,
    string_constants: dict[str, str],
) -> bool:
    if len(node.args) >= 2:
        return _python_file_mode_can_write(
            node.args[1],
            string_constants=string_constants,
        )
    for keyword in node.keywords:
        if keyword.arg == "mode":
            return _python_file_mode_can_write(
                keyword.value,
                string_constants=string_constants,
            )
    return False


def _python_file_mode_can_write(
    node: ast.AST,
    *,
    string_constants: dict[str, str],
) -> bool:
    mode = _python_resolve_string_expression(
        node,
        string_constants=string_constants,
    )
    if mode is None:
        return False
    return any(marker in mode for marker in ("w", "a", "x", "+"))


def _ast_call_is_json_dump(
    node: ast.Call,
    *,
    json_aliases: set[str],
    json_dump_names: set[str],
) -> bool:
    if isinstance(node.func, ast.Name) and node.func.id in json_dump_names:
        return True
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "dump"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in json_aliases
    )


def _ast_os_raw_file_write_call(
    node: ast.Call,
    *,
    os_aliases: set[str],
    os_write_names: set[str],
) -> str | None:
    if isinstance(node.func, ast.Name) and node.func.id in os_write_names:
        return f"os.{node.func.id}"
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr in {"open", "write"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in os_aliases
    ):
        return f"os.{node.func.attr}"
    return None
