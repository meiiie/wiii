"""Inspect JavaScript probe arguments and output handling without running probes."""

from __future__ import annotations

import re

from .constants import (
    MJS_RAW_FILE_WRITE_FUNCTIONS,
    MJS_RAW_FS_MODULES,
    MJS_RAW_FS_PROMISE_MODULES,
    MJS_RAW_PROMISE_FILE_WRITE_FUNCTIONS,
)


def _mjs_probe_fail_closed_guard_tokens(probe_text: str) -> set[str]:
    code, string_values = _javascript_code_with_string_markers(probe_text)
    marker_pattern = r"__JS_STRING_([0-9]+)__"
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    constants = _javascript_const_string_values(code, string_values)

    flags: set[str] = set()
    expression_pattern = rf"(?:{marker_pattern}|{name_pattern})"
    condition_pattern = re.compile(
        rf"^\s*!\s*process\.argv\.includes\(\s*"
        rf"({expression_pattern})\s*\)\s*$",
        re.DOTALL,
    )
    for condition, body in _javascript_top_level_if_blocks(code):
        match = condition_pattern.fullmatch(condition)
        if not match or re.search(r"\bfail\s*\(", body) is None:
            continue
        token = _javascript_resolve_string_expression(
            match.group(1),
            constants=constants,
            string_values=string_values,
        )
        if token:
            flags.add(token)
    return flags


def _javascript_const_string_values(
    code: str,
    string_values: list[str],
) -> dict[str, str]:
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    declaration_pattern = re.compile(
        rf"(?m)^\s*const\s+({name_pattern})\s*=\s*(?P<expression>[^;\n]+)\s*;",
    )
    declarations = [
        (match.group(1), match.group("expression").strip())
        for match in declaration_pattern.finditer(code)
    ]
    constants: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for name, expression in declarations:
            if name in constants:
                continue
            value = _javascript_resolve_const_string_expression(
                expression,
                constants=constants,
                string_values=string_values,
            )
            if value is None:
                continue
            constants[name] = value
            changed = True
    return constants


def _javascript_resolve_const_string_expression(
    expression: str,
    *,
    constants: dict[str, str],
    string_values: list[str],
) -> str | None:
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    marker_pattern = r"__JS_STRING_[0-9]+__"
    value_parts: list[str] = []
    for part in expression.split("+"):
        cleaned = part.strip()
        if not cleaned:
            return None
        marker_match = re.fullmatch(marker_pattern, cleaned)
        if marker_match:
            value_parts.append(_javascript_resolve_string_marker(cleaned, string_values))
            continue
        if re.fullmatch(name_pattern, cleaned) and cleaned in constants:
            value_parts.append(constants[cleaned])
            continue
        return None
    return "".join(value_parts)


def _javascript_resolve_string_marker(
    marker: str,
    string_values: list[str],
) -> str:
    marker_match = re.fullmatch(r"__JS_STRING_([0-9]+)__", marker)
    if not marker_match:
        return ""
    return string_values[int(marker_match.group(1))]


def _mjs_probe_fail_function_exits_nonzero(probe_text: str) -> bool:
    code, _ = _javascript_code_with_string_markers(probe_text)
    body = _javascript_function_body(code, "fail")
    return bool(body) and _javascript_body_calls_process_exit_nonzero(body)


def _mjs_probe_handles_output_argument(probe_text: str) -> bool:
    code, string_values = _javascript_code_with_string_markers(probe_text)
    return bool(_mjs_probe_output_arg_return_properties(code, string_values))


def _mjs_probe_forwards_output_to_summary_env(probe_text: str) -> bool:
    code, string_values = _javascript_code_with_string_markers(probe_text)
    constants = _javascript_const_string_values(code, string_values)
    output_properties = _mjs_probe_output_arg_return_properties(code, string_values)
    output_vars = _javascript_parse_args_destructured_variables(
        code,
        returned_properties=output_properties,
    )
    if not output_vars:
        return False

    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    env_expressions = [
        re.escape(f"__JS_STRING_{index}__")
        for index, value in enumerate(string_values)
        if value == "WIII_RUNTIME_FLOW_BROWSER_REPLAY_SUMMARY_JSON"
    ]
    env_expressions.extend(
        re.escape(name)
        for name, value in constants.items()
        if value == "WIII_RUNTIME_FLOW_BROWSER_REPLAY_SUMMARY_JSON"
    )
    if not env_expressions:
        return False

    env_expression = "|".join(env_expressions)
    assignment_pattern = rf"(?:\[\s*(?:{env_expression})\s*\]|(?:{env_expression}))\s*:\s*({name_pattern})"
    return any(
        _javascript_spawn_sync_forwards_summary_env(
            arguments,
            assignment_pattern=assignment_pattern,
            output_vars=output_vars,
        )
        for arguments in _javascript_call_argument_lists(code, "spawnSync")
    )


def _javascript_spawn_sync_forwards_summary_env(
    arguments: list[str],
    *,
    assignment_pattern: str,
    output_vars: set[str],
) -> bool:
    if len(arguments) < 3:
        return False
    if arguments[0].strip() != "process.execPath":
        return False
    if "runner" not in arguments[1] or "forwarded" not in arguments[1]:
        return False
    match = re.search(assignment_pattern, arguments[2])
    return bool(match) and match.group(1) in output_vars


def _mjs_probe_raw_file_write_calls(probe_text: str) -> list[str]:
    code, string_values = _javascript_code_with_string_markers(probe_text)
    constants = _javascript_const_string_values(code, string_values)
    direct_names = set(MJS_RAW_FILE_WRITE_FUNCTIONS)
    direct_names.update(_javascript_named_fs_write_imports(code, string_values))
    direct_names.update(
        _javascript_named_fs_promises_write_imports(code, string_values)
    )
    direct_names.update(_javascript_dynamic_fs_write_imports(code, string_values, constants))
    direct_names.update(
        _javascript_dynamic_fs_promises_write_imports(code, string_values, constants)
    )
    direct_names.update(_javascript_require_fs_write_imports(code, string_values, constants))
    direct_names.update(
        _javascript_require_fs_promises_write_imports(code, string_values, constants)
    )
    namespace_names = _javascript_fs_namespace_imports(code, string_values)
    namespace_names.update(
        _javascript_dynamic_fs_namespace_imports(code, string_values, constants)
    )
    namespace_names.update(
        _javascript_require_fs_namespace_imports(code, string_values, constants)
    )
    promise_namespace_names = _javascript_fs_promises_namespace_imports(
        code,
        string_values,
    )
    promise_namespace_names.update(
        _javascript_dynamic_fs_promises_namespace_imports(code, string_values, constants)
    )
    promise_namespace_names.update(
        _javascript_require_fs_promises_namespace_imports(code, string_values, constants)
    )
    promise_namespace_names.update(
        _javascript_dynamic_fs_promises_member_imports(code, string_values, constants)
    )
    promise_namespace_names.update(
        _javascript_require_fs_promises_member_imports(code, string_values, constants)
    )

    calls: set[str] = set()
    for name in direct_names:
        if re.search(rf"\b{re.escape(name)}\s*\(", code):
            calls.add(name)

    for function_name in MJS_RAW_FILE_WRITE_FUNCTIONS:
        if _javascript_inline_module_function_call(
            code,
            string_values,
            constants,
            module_values=MJS_RAW_FS_MODULES,
            function_name=function_name,
        ):
            calls.add(f"inline.{function_name}")
    for function_name in MJS_RAW_PROMISE_FILE_WRITE_FUNCTIONS:
        if _javascript_inline_module_function_call(
            code,
            string_values,
            constants,
            module_values=MJS_RAW_FS_PROMISE_MODULES,
            function_name=function_name,
        ):
            calls.add(f"inline.{function_name}")
        if _javascript_inline_module_promises_function_call(
            code,
            string_values,
            constants,
            module_values=MJS_RAW_FS_MODULES,
            function_name=function_name,
        ):
            calls.add(f"inline.promises.{function_name}")

    for namespace in namespace_names:
        for function_name in MJS_RAW_FILE_WRITE_FUNCTIONS:
            if _javascript_namespace_function_call(
                code,
                namespace=namespace,
                function_name=function_name,
                string_values=string_values,
                constants=constants,
            ):
                calls.add(f"{namespace}.{function_name}")
        for function_name in ("appendFile", "writeFile"):
            if _javascript_namespace_promises_function_call(
                code,
                namespace=namespace,
                function_name=function_name,
                string_values=string_values,
                constants=constants,
            ):
                calls.add(f"{namespace}.promises.{function_name}")
    for namespace in promise_namespace_names:
        for function_name in MJS_RAW_PROMISE_FILE_WRITE_FUNCTIONS:
            if _javascript_namespace_function_call(
                code,
                namespace=namespace,
                function_name=function_name,
                string_values=string_values,
                constants=constants,
            ):
                calls.add(f"{namespace}.{function_name}")
    return sorted(calls)


def _javascript_named_fs_write_imports(
    code: str,
    string_values: list[str],
) -> set[str]:
    names: set[str] = set()
    module_pattern = _javascript_string_module_pattern(string_values, MJS_RAW_FS_MODULES)
    if not module_pattern:
        return names
    import_pattern = re.compile(
        rf"\bimport\s+(?:[A-Za-z_$][A-Za-z0-9_$]*\s*,\s*)?"
        rf"\{{(?P<body>[^}}]+)\}}\s*from\s*(?:{module_pattern})\s*;",
    )
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    for match in import_pattern.finditer(code):
        for part in match.group("body").split(","):
            cleaned = part.strip()
            if not cleaned:
                continue
            import_match = re.match(
                rf"^(?P<imported>{name_pattern})"
                rf"(?:\s+as\s+(?P<local>{name_pattern}))?$",
                cleaned,
            )
            if not import_match:
                continue
            imported = import_match.group("imported")
            if imported not in MJS_RAW_FILE_WRITE_FUNCTIONS:
                continue
            names.add(import_match.group("local") or imported)
    return names


def _javascript_named_fs_promises_write_imports(
    code: str,
    string_values: list[str],
) -> set[str]:
    names: set[str] = set()
    module_pattern = _javascript_string_module_pattern(
        string_values,
        MJS_RAW_FS_PROMISE_MODULES,
    )
    if not module_pattern:
        return names
    import_pattern = re.compile(
        rf"\bimport\s+(?:[A-Za-z_$][A-Za-z0-9_$]*\s*,\s*)?"
        rf"\{{(?P<body>[^}}]+)\}}\s*from\s*(?:{module_pattern})\s*;",
    )
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    for match in import_pattern.finditer(code):
        for part in match.group("body").split(","):
            cleaned = part.strip()
            if not cleaned:
                continue
            import_match = re.match(
                rf"^(?P<imported>{name_pattern})"
                rf"(?:\s+as\s+(?P<local>{name_pattern}))?$",
                cleaned,
            )
            if not import_match:
                continue
            imported = import_match.group("imported")
            if imported not in MJS_RAW_PROMISE_FILE_WRITE_FUNCTIONS:
                continue
            names.add(import_match.group("local") or imported)
    return names


def _javascript_dynamic_fs_write_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_MODULES,
    )
    return _javascript_dynamic_named_imports(
        code,
        module_pattern=module_pattern,
        imported_names=MJS_RAW_FILE_WRITE_FUNCTIONS,
    )


def _javascript_dynamic_fs_promises_write_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_PROMISE_MODULES,
    )
    return _javascript_dynamic_named_imports(
        code,
        module_pattern=module_pattern,
        imported_names=MJS_RAW_PROMISE_FILE_WRITE_FUNCTIONS,
    )


def _javascript_require_fs_write_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_MODULES,
    )
    return _javascript_require_named_imports(
        code,
        module_pattern=module_pattern,
        imported_names=MJS_RAW_FILE_WRITE_FUNCTIONS,
    )


def _javascript_require_fs_promises_write_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_PROMISE_MODULES,
    )
    return _javascript_require_named_imports(
        code,
        module_pattern=module_pattern,
        imported_names=MJS_RAW_PROMISE_FILE_WRITE_FUNCTIONS,
    )


def _javascript_dynamic_fs_promises_member_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_MODULES,
    )
    return _javascript_dynamic_named_imports(
        code,
        module_pattern=module_pattern,
        imported_names={"promises"},
    )


def _javascript_require_fs_promises_member_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_MODULES,
    )
    return _javascript_require_named_imports(
        code,
        module_pattern=module_pattern,
        imported_names={"promises"},
    )


def _javascript_dynamic_named_imports(
    code: str,
    *,
    module_pattern: str,
    imported_names: set[str],
) -> set[str]:
    if not module_pattern:
        return set()
    import_pattern = re.compile(
        rf"\b(?:const|let|var)\s*\{{(?P<body>[^}}]+)\}}\s*=\s*"
        rf"(?:await\s+)?import\s*\(\s*(?:{module_pattern})\s*\)\s*;",
    )
    names: set[str] = set()
    for match in import_pattern.finditer(code):
        names.update(
            _javascript_destructured_binding_names(
                match.group("body"),
                imported_names=imported_names,
            )
        )
    return names


def _javascript_require_named_imports(
    code: str,
    *,
    module_pattern: str,
    imported_names: set[str],
) -> set[str]:
    if not module_pattern:
        return set()
    import_pattern = re.compile(
        rf"\b(?:const|let|var)\s*\{{(?P<body>[^}}]+)\}}\s*=\s*"
        rf"require\s*\(\s*(?:{module_pattern})\s*\)\s*;",
    )
    names: set[str] = set()
    for match in import_pattern.finditer(code):
        names.update(
            _javascript_destructured_binding_names(
                match.group("body"),
                imported_names=imported_names,
            )
        )
    return names


def _javascript_destructured_binding_names(
    body: str,
    *,
    imported_names: set[str],
) -> set[str]:
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    names: set[str] = set()
    for part in body.split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        cleaned = _javascript_binding_without_default_initializer(cleaned)
        import_match = re.match(
            rf"^(?P<imported>{name_pattern})"
            rf"(?:\s*:\s*(?P<local>{name_pattern}))?$",
            cleaned,
        )
        if not import_match:
            continue
        imported = import_match.group("imported")
        if imported not in imported_names:
            continue
        names.add(import_match.group("local") or imported)
    return names


def _javascript_fs_namespace_imports(
    code: str,
    string_values: list[str],
) -> set[str]:
    names: set[str] = set()
    module_pattern = _javascript_string_module_pattern(string_values, MJS_RAW_FS_MODULES)
    if not module_pattern:
        return names
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    namespace_pattern = re.compile(
        rf"\bimport\s+\*\s+as\s+({name_pattern})\s+from\s*"
        rf"(?:{module_pattern})\s*;",
    )
    default_pattern = re.compile(
        rf"\bimport\s+({name_pattern})\s+from\s*(?:{module_pattern})\s*;",
    )
    for match in namespace_pattern.finditer(code):
        names.add(match.group(1))
    for match in default_pattern.finditer(code):
        names.add(match.group(1))
    named_default_pattern = re.compile(
        rf"\bimport\s*\{{(?P<body>[^}}]+)\}}\s*from\s*"
        rf"(?:{module_pattern})\s*;",
    )
    for match in named_default_pattern.finditer(code):
        names.update(_javascript_default_binding_names(match.group("body")))
    return names


def _javascript_dynamic_fs_namespace_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_MODULES,
    )
    names = _javascript_dynamic_namespace_imports(code, module_pattern=module_pattern)
    names.update(
        _javascript_dynamic_default_namespace_imports(
            code,
            module_pattern=module_pattern,
        )
    )
    return names


def _javascript_require_fs_namespace_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_MODULES,
    )
    return _javascript_require_namespace_imports(code, module_pattern=module_pattern)


def _javascript_fs_promises_namespace_imports(
    code: str,
    string_values: list[str],
) -> set[str]:
    names: set[str] = set()
    raw_module_pattern = _javascript_string_module_pattern(
        string_values,
        MJS_RAW_FS_MODULES,
    )
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    if raw_module_pattern:
        import_pattern = re.compile(
            rf"\bimport\s+(?:{name_pattern}\s*,\s*)?"
            rf"\{{(?P<body>[^}}]+)\}}\s*from\s*(?:{raw_module_pattern})\s*;",
        )
        for match in import_pattern.finditer(code):
            for part in match.group("body").split(","):
                cleaned = part.strip()
                if not cleaned:
                    continue
                import_match = re.match(
                    rf"^(?P<imported>{name_pattern})"
                    rf"(?:\s+as\s+(?P<local>{name_pattern}))?$",
                    cleaned,
                )
                if not import_match or import_match.group("imported") != "promises":
                    continue
                names.add(import_match.group("local") or "promises")

    promise_module_pattern = _javascript_string_module_pattern(
        string_values,
        MJS_RAW_FS_PROMISE_MODULES,
    )
    if not promise_module_pattern:
        return names
    namespace_pattern = re.compile(
        rf"\bimport\s+\*\s+as\s+({name_pattern})\s+from\s*"
        rf"(?:{promise_module_pattern})\s*;",
    )
    default_pattern = re.compile(
        rf"\bimport\s+({name_pattern})\s+from\s*"
        rf"(?:{promise_module_pattern})\s*;",
    )
    for match in namespace_pattern.finditer(code):
        names.add(match.group(1))
    for match in default_pattern.finditer(code):
        names.add(match.group(1))
    return names


def _javascript_dynamic_fs_promises_namespace_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_PROMISE_MODULES,
    )
    names = _javascript_dynamic_namespace_imports(code, module_pattern=module_pattern)
    names.update(
        _javascript_dynamic_default_namespace_imports(
            code,
            module_pattern=module_pattern,
        )
    )
    return names


def _javascript_require_fs_promises_namespace_imports(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
) -> set[str]:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        MJS_RAW_FS_PROMISE_MODULES,
    )
    return _javascript_require_namespace_imports(code, module_pattern=module_pattern)


def _javascript_dynamic_namespace_imports(
    code: str,
    *,
    module_pattern: str,
) -> set[str]:
    if not module_pattern:
        return set()
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    pattern = re.compile(
        rf"\b(?:const|let|var)\s+({name_pattern})\s*=\s*"
        rf"(?:await\s+)?import\s*\(\s*(?:{module_pattern})\s*\)\s*;",
    )
    return {match.group(1) for match in pattern.finditer(code)}


def _javascript_dynamic_default_namespace_imports(
    code: str,
    *,
    module_pattern: str,
) -> set[str]:
    if not module_pattern:
        return set()
    pattern = re.compile(
        rf"\b(?:const|let|var)\s*\{{(?P<body>[^}}]+)\}}\s*=\s*"
        rf"(?:await\s+)?import\s*\(\s*(?:{module_pattern})\s*\)\s*;",
    )
    names: set[str] = set()
    for match in pattern.finditer(code):
        names.update(_javascript_default_binding_names(match.group("body")))
    return names


def _javascript_default_binding_names(body: str) -> set[str]:
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    names: set[str] = set()
    for part in body.split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        cleaned = _javascript_binding_without_default_initializer(cleaned)
        match = re.match(
            rf"^default(?:\s+as|\s*:)\s+(?P<local>{name_pattern})$",
            cleaned,
        )
        if match:
            names.add(match.group("local"))
    return names


def _javascript_binding_without_default_initializer(binding: str) -> str:
    return binding.split("=", 1)[0].strip()


def _javascript_require_namespace_imports(
    code: str,
    *,
    module_pattern: str,
) -> set[str]:
    if not module_pattern:
        return set()
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    pattern = re.compile(
        rf"\b(?:const|let|var)\s+({name_pattern})\s*=\s*"
        rf"require\s*\(\s*(?:{module_pattern})\s*\)\s*;",
    )
    return {match.group(1) for match in pattern.finditer(code)}


def _javascript_inline_module_function_call(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
    *,
    module_values: set[str],
    function_name: str,
) -> bool:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        module_values,
    )
    if not module_pattern:
        return False
    access_pattern = _javascript_property_access_pattern(
        function_name,
        string_values,
        constants=constants,
    )
    default_access_pattern = _javascript_property_access_pattern(
        "default",
        string_values,
        constants=constants,
    )
    call_pattern = rf"(?:{access_pattern}|{default_access_pattern}\s*{access_pattern})"
    return any(
        re.search(rf"{module_expression}\s*{call_pattern}\s*\(", code)
        for module_expression in _javascript_inline_module_expressions(module_pattern)
    )


def _javascript_inline_module_promises_function_call(
    code: str,
    string_values: list[str],
    constants: dict[str, str],
    *,
    module_values: set[str],
    function_name: str,
) -> bool:
    module_pattern = _javascript_string_or_const_pattern(
        string_values,
        constants,
        module_values,
    )
    if not module_pattern:
        return False
    promises_access_pattern = _javascript_property_access_pattern(
        "promises",
        string_values,
        constants=constants,
    )
    function_access_pattern = _javascript_property_access_pattern(
        function_name,
        string_values,
        constants=constants,
    )
    default_access_pattern = _javascript_property_access_pattern(
        "default",
        string_values,
        constants=constants,
    )
    promise_chain_pattern = rf"{promises_access_pattern}\s*{function_access_pattern}"
    call_pattern = (
        rf"(?:{promise_chain_pattern}|"
        rf"{default_access_pattern}\s*{promise_chain_pattern})"
    )
    return any(
        re.search(rf"{module_expression}\s*{call_pattern}\s*\(", code)
        for module_expression in _javascript_inline_module_expressions(module_pattern)
    )


def _javascript_inline_module_expressions(module_pattern: str) -> list[str]:
    return [
        rf"require\s*\(\s*(?:{module_pattern})\s*\)",
        rf"\(\s*await\s+import\s*\(\s*(?:{module_pattern})\s*\)\s*\)",
    ]


def _javascript_namespace_function_call(
    code: str,
    *,
    namespace: str,
    function_name: str,
    string_values: list[str],
    constants: dict[str, str],
) -> bool:
    access_pattern = _javascript_property_access_pattern(
        function_name,
        string_values,
        constants=constants,
    )
    default_access_pattern = _javascript_property_access_pattern(
        "default",
        string_values,
        constants=constants,
    )
    return bool(
        re.search(
            rf"\b{re.escape(namespace)}\s*"
            rf"(?:{access_pattern}|{default_access_pattern}\s*{access_pattern})"
            rf"\s*\(",
            code,
        )
    )


def _javascript_namespace_promises_function_call(
    code: str,
    *,
    namespace: str,
    function_name: str,
    string_values: list[str],
    constants: dict[str, str],
) -> bool:
    promises_access_pattern = _javascript_property_access_pattern(
        "promises",
        string_values,
        constants=constants,
    )
    function_access_pattern = _javascript_property_access_pattern(
        function_name,
        string_values,
        constants=constants,
    )
    default_access_pattern = _javascript_property_access_pattern(
        "default",
        string_values,
        constants=constants,
    )
    promise_chain_pattern = (
        rf"{promises_access_pattern}\s*{function_access_pattern}"
    )
    return bool(
        re.search(
            rf"\b{re.escape(namespace)}\s*"
            rf"(?:{promise_chain_pattern}|"
            rf"{default_access_pattern}\s*{promise_chain_pattern})"
            rf"\s*\(",
            code,
        )
    )


def _javascript_property_access_pattern(
    property_name: str,
    string_values: list[str],
    *,
    constants: dict[str, str],
) -> str:
    patterns = [rf"(?:\?\.|\.)\s*{re.escape(property_name)}"]
    bracket_pattern = _javascript_string_module_pattern(string_values, {property_name})
    if bracket_pattern:
        bracket_access = rf"\[\s*(?:{bracket_pattern})\s*\]"
        optional_bracket_access = rf"\?\.\s*\[\s*(?:{bracket_pattern})\s*\]"
        patterns.append(rf"(?:{bracket_access}|{optional_bracket_access})")
    constant_pattern = "|".join(
        re.escape(name)
        for name, value in constants.items()
        if value == property_name
    )
    if constant_pattern:
        bracket_access = rf"\[\s*(?:{constant_pattern})\s*\]"
        optional_bracket_access = rf"\?\.\s*\[\s*(?:{constant_pattern})\s*\]"
        patterns.append(rf"(?:{bracket_access}|{optional_bracket_access})")
    return rf"(?:{'|'.join(patterns)})"


def _javascript_string_or_const_pattern(
    string_values: list[str],
    constants: dict[str, str],
    values: set[str],
) -> str:
    patterns = [
        re.escape(f"__JS_STRING_{index}__")
        for index, value in enumerate(string_values)
        if value in values
    ]
    patterns.extend(
        re.escape(name)
        for name, value in constants.items()
        if value in values
    )
    return "|".join(patterns)


def _javascript_string_module_pattern(
    string_values: list[str],
    modules: set[str],
) -> str:
    return "|".join(
        re.escape(f"__JS_STRING_{index}__")
        for index, value in enumerate(string_values)
        if value in modules
    )


def _mjs_probe_output_arg_return_properties(
    code: str,
    string_values: list[str],
) -> set[str]:
    if "process.argv" not in code:
        return set()

    parse_args_body = _javascript_function_body(code, "parseArgs")
    if not parse_args_body:
        return set()

    out_markers = [
        re.escape(f"__JS_STRING_{index}__")
        for index, value in enumerate(string_values)
        if value == "--out"
    ]
    out_equals_markers = [
        re.escape(f"__JS_STRING_{index}__")
        for index, value in enumerate(string_values)
        if value == "--out="
    ]
    if not out_markers or not out_equals_markers:
        return set()

    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    exact_arg_pattern = re.compile(
        rf"^\s*(?:\b{name_pattern}\s*===\s*(?:{'|'.join(out_markers)})|"
        rf"(?:{'|'.join(out_markers)})\s*===\s*\b{name_pattern})\s*$"
    )
    prefixed_arg_pattern = re.compile(
        rf"^\s*\b{name_pattern}\.startsWith\(\s*"
        rf"(?:{'|'.join(out_equals_markers)})\s*\)\s*$"
    )
    exact_assignments: set[str] = set()
    prefixed_assignments: set[str] = set()
    for condition, body in _javascript_if_blocks(parse_args_body):
        if exact_arg_pattern.fullmatch(condition):
            exact_assignments.update(_javascript_argv_next_value_assignments(body))
        if prefixed_arg_pattern.fullmatch(condition):
            prefixed_assignments.update(
                _javascript_string_prefix_slice_assignments(
                    body,
                    prefix_markers=out_equals_markers,
                )
            )

    output_variables = exact_assignments & prefixed_assignments
    if not output_variables:
        return set()
    return _javascript_returned_object_properties_for_variables(
        parse_args_body,
        output_variables,
    )


def _javascript_argv_next_value_assignments(body: str) -> set[str]:
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    pattern = re.compile(
        rf"\b({name_pattern})\s*=\s*argv\s*\[\s*{name_pattern}\s*\+\s*1\s*\]"
    )
    return {match.group(1) for match in pattern.finditer(body)}


def _javascript_string_prefix_slice_assignments(
    body: str,
    *,
    prefix_markers: list[str],
) -> set[str]:
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    prefix_expression = "|".join(prefix_markers)
    pattern = re.compile(
        rf"\b({name_pattern})\s*=\s*{name_pattern}\.slice\(\s*"
        rf"(?:{prefix_expression})\.length\s*\)"
    )
    return {match.group(1) for match in pattern.finditer(body)}


def _javascript_returned_object_properties_for_variables(
    body: str,
    variables: set[str],
) -> set[str]:
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    properties: set[str] = set()
    for match in re.finditer(r"\breturn\s*\{(?P<body>[^}]+)\}\s*;", body):
        for part in match.group("body").split(","):
            cleaned = part.strip()
            if not cleaned:
                continue
            if ":" in cleaned:
                property_name, local_name = [
                    item.strip()
                    for item in cleaned.split(":", 1)
                ]
            else:
                property_name = cleaned
                local_name = cleaned
            property_match = re.match(rf"^({name_pattern})\b", property_name)
            local_match = re.match(rf"^({name_pattern})\b", local_name)
            if (
                property_match
                and local_match
                and local_match.group(1) in variables
            ):
                properties.add(property_match.group(1))
    return properties


def _javascript_parse_args_destructured_variables(
    code: str,
    *,
    returned_properties: set[str],
) -> set[str]:
    name_pattern = r"[A-Za-z_$][A-Za-z0-9_$]*"
    variables: set[str] = set()
    destructure_pattern = re.compile(
        r"\bconst\s*\{(?P<body>[^}]+)\}\s*=\s*parseArgs\s*\(\s*"
        r"process\.argv\.slice\s*\(\s*2\s*\)\s*\)\s*;"
    )
    for match in destructure_pattern.finditer(code):
        for part in match.group("body").split(","):
            cleaned = part.strip()
            if not cleaned:
                continue
            if ":" in cleaned:
                property_name, local_name = [
                    item.strip()
                    for item in cleaned.split(":", 1)
                ]
            else:
                property_name = cleaned
                local_name = cleaned
            property_match = re.match(rf"^({name_pattern})\b", property_name)
            if not property_match or property_match.group(1) not in returned_properties:
                continue
            name_match = re.match(rf"^({name_pattern})\b", local_name)
            if name_match:
                variables.add(name_match.group(1))
    return variables


def _javascript_function_body(code: str, function_name: str) -> str:
    match = re.search(
        rf"\bfunction\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{",
        code,
    )
    if not match:
        return ""
    body_start = match.end()
    depth = 1
    index = body_start
    while index < len(code):
        char = code[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return code[body_start:index]
        index += 1
    return ""


def _javascript_body_calls_process_exit_nonzero(body: str) -> bool:
    for match in re.finditer(r"\bprocess\.exit\s*\(\s*([0-9]+)\s*\)", body):
        if int(match.group(1)) > 0:
            return True
    return False


def _javascript_top_level_if_blocks(code: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    depth = 0
    index = 0
    while index < len(code):
        if depth == 0 and _javascript_word_at(code, index, "if"):
            parsed = _javascript_parse_if_block(code, index)
            if parsed is not None:
                condition, body, next_index = parsed
                blocks.append((condition, body))
                index = next_index
                continue
        char = code[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(depth - 1, 0)
        index += 1
    return blocks


def _javascript_if_blocks(code: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    index = 0
    while index < len(code):
        if _javascript_word_at(code, index, "if"):
            parsed = _javascript_parse_if_block(code, index)
            if parsed is not None:
                condition, body, next_index = parsed
                blocks.append((condition, body))
                index = next_index
                continue
        index += 1
    return blocks


def _javascript_call_argument_lists(code: str, function_name: str) -> list[list[str]]:
    calls: list[list[str]] = []
    for match in re.finditer(rf"\b{re.escape(function_name)}\s*\(", code):
        open_index = code.find("(", match.start())
        if open_index < 0:
            continue
        close_index = _javascript_matching_delimiter(code, open_index, "(", ")")
        if close_index is None:
            continue
        calls.append(_javascript_top_level_comma_parts(code[open_index + 1:close_index]))
    return calls


def _javascript_top_level_comma_parts(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())
    for index, char in enumerate(text):
        if char in pairs:
            depth += 1
        elif char in closing:
            depth = max(depth - 1, 0)
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _javascript_parse_if_block(code: str, index: int) -> tuple[str, str, int] | None:
    cursor = index + len("if")
    cursor = _javascript_skip_whitespace(code, cursor)
    if cursor >= len(code) or code[cursor] != "(":
        return None
    condition_end = _javascript_matching_delimiter(code, cursor, "(", ")")
    if condition_end is None:
        return None
    condition = code[cursor + 1:condition_end]
    cursor = _javascript_skip_whitespace(code, condition_end + 1)
    if cursor >= len(code) or code[cursor] != "{":
        return None
    body_end = _javascript_matching_delimiter(code, cursor, "{", "}")
    if body_end is None:
        return None
    return condition, code[cursor + 1:body_end], body_end + 1


def _javascript_matching_delimiter(
    code: str,
    start: int,
    open_char: str,
    close_char: str,
) -> int | None:
    depth = 1
    index = start + 1
    while index < len(code):
        char = code[index]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _javascript_skip_whitespace(code: str, index: int) -> int:
    while index < len(code) and code[index].isspace():
        index += 1
    return index


def _javascript_word_at(code: str, index: int, word: str) -> bool:
    end = index + len(word)
    if code[index:end] != word:
        return False
    before = code[index - 1] if index > 0 else ""
    after = code[end] if end < len(code) else ""
    identifier_chars = "_$"
    return (
        not before.isalnum()
        and before not in identifier_chars
        and not after.isalnum()
        and after not in identifier_chars
    )


def _javascript_resolve_string_expression(
    expression: str,
    *,
    constants: dict[str, str],
    string_values: list[str],
) -> str:
    marker_match = re.fullmatch(r"__JS_STRING_([0-9]+)__", expression)
    if marker_match:
        return string_values[int(marker_match.group(1))]
    return constants.get(expression, "")


def _javascript_code_with_string_markers(source: str) -> tuple[str, list[str]]:
    output: list[str] = []
    string_values: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if char == "/" and next_char == "/":
            output.extend("  ")
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                output.append(" ")
                index += 1
            continue
        if char == "/" and next_char == "*":
            output.extend("  ")
            index += 2
            while index < len(source):
                if source[index] == "*" and index + 1 < len(source) and source[index + 1] == "/":
                    output.extend("  ")
                    index += 2
                    break
                output.append("\n" if source[index] in "\r\n" else " ")
                index += 1
            continue
        if char == "`":
            output.append(" ")
            index += 1
            escaped = False
            while index < len(source):
                current = source[index]
                output.append("\n" if current in "\r\n" else " ")
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == "`":
                    index += 1
                    break
                index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            value: list[str] = []
            index += 1
            escaped = False
            while index < len(source):
                current = source[index]
                if escaped:
                    value.extend(["\\", current])
                    escaped = False
                    index += 1
                    continue
                if current == "\\":
                    escaped = True
                    index += 1
                    continue
                if current == quote:
                    index += 1
                    break
                value.append(current)
                index += 1
            marker = f"__JS_STRING_{len(string_values)}__"
            string_values.append("".join(value))
            output.append(marker)
            continue
        output.append(char)
        index += 1
    return "".join(output), string_values
