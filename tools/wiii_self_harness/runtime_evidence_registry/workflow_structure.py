"""Read jobs, steps, mappings, and events from workflow text."""

from __future__ import annotations

import re


def _workflow_step_blocks(workflow_text: str) -> list[str]:
    lines = workflow_text.splitlines()
    first_line = next((line for line in lines if line.strip()), "")
    if re.match(r"^\s{6}-\s+(?:name:|uses:|run:|id:)", first_line):
        return [workflow_text]

    blocks: list[str] = []
    index = 0
    while index < len(lines):
        if not re.match(r"^\s{4}steps:\s*(?:#.*)?$", lines[index]):
            index += 1
            continue

        steps_indent = 4
        step_indent = steps_indent + 2
        steps_end = len(lines)
        for end_index in range(index + 1, len(lines)):
            line = lines[end_index]
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= steps_indent:
                steps_end = end_index
                break

        step_starts = [
            step_index
            for step_index in range(index + 1, steps_end)
            if re.match(rf"^\s{{{step_indent}}}-\s+(?:name:|uses:|run:|id:)", lines[step_index])
        ]
        for position, start in enumerate(step_starts):
            end = step_starts[position + 1] if position + 1 < len(step_starts) else steps_end
            blocks.append("\n".join(lines[start:end]))
        index = steps_end
    return blocks


def _workflow_text_before_jobs(workflow_text: str) -> str:
    lines = workflow_text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^jobs:\s*(?:#.*)?$", line):
            return "\n".join(lines[:index])
    return workflow_text


def _workflow_block_scalar_field_equals(block: str, field: str, expected: str) -> bool:
    values = [
        match.group(1).strip().strip("\"'")
        for match in re.finditer(
            rf"(?m)^\s+{re.escape(field)}:\s*([^#\r\n]+?)\s*(?:#.*)?$",
            block,
        )
    ]
    return expected in values


def _workflow_step_scalar_field_equals(block: str, field: str, expected: str) -> bool:
    return expected in _workflow_block_direct_scalar_values(block, field)


def _workflow_block_direct_scalar_values(block: str, field: str) -> list[str]:
    lines = block.splitlines()
    first_line = next((line for line in lines if line.strip()), "")
    if not first_line:
        return []

    first_indent = len(first_line) - len(first_line.lstrip(" "))
    direct_indent = first_indent + 2 if first_line.lstrip().startswith("- ") else first_indent
    values: list[str] = []
    first_match = re.match(
        rf"^\s*-\s+{re.escape(field)}:\s*([^#\r\n]+?)\s*(?:#.*)?$",
        first_line,
    )
    if first_match:
        values.append(first_match.group(1).strip().strip("\"'"))
    values.extend(
        match.group(1).strip().strip("\"'")
        for line in lines[1:]
        if (
            match := re.match(
                rf"^\s{{{direct_indent}}}{re.escape(field)}:"
                r"\s*([^#\r\n]+?)\s*(?:#.*)?$",
                line,
            )
        )
    )
    return values


def _workflow_block_duplicate_direct_fields(block: str, fields: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    allowed = set(fields)
    for field in _workflow_block_direct_field_names(block):
        if field in allowed:
            counts[field] = counts.get(field, 0) + 1
    return [field for field in fields if counts.get(field, 0) > 1]


def _workflow_block_direct_field_names(block: str) -> list[str]:
    lines = block.splitlines()
    first_line = next((line for line in lines if line.strip()), "")
    if not first_line:
        return []

    first_indent = len(first_line) - len(first_line.lstrip(" "))
    direct_indent = first_indent + 2 if first_line.lstrip().startswith("- ") else first_indent
    fields: list[str] = []
    if first_match := re.match(r"^\s*-\s+([A-Za-z0-9_-]+):(?:\s|$)", first_line):
        fields.append(first_match.group(1))
    for line in lines[1:]:
        if match := re.match(rf"^\s{{{direct_indent}}}([A-Za-z0-9_-]+):(?:\s|$)", line):
            fields.append(match.group(1))
    return fields


def _workflow_job_duplicate_direct_fields(job_block: str, fields: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    allowed = set(fields)
    for field in _workflow_job_direct_field_names(job_block):
        if field in allowed:
            counts[field] = counts.get(field, 0) + 1
    return [field for field in fields if counts.get(field, 0) > 1]


def _workflow_job_direct_field_names(job_block: str) -> list[str]:
    lines = job_block.splitlines()
    first_line = next((line for line in lines if line.strip()), "")
    if not first_line:
        return []

    job_indent = len(first_line) - len(first_line.lstrip(" "))
    field_indent = job_indent + 2
    fields: list[str] = []
    for line in lines[1:]:
        if match := re.match(rf"^\s{{{field_indent}}}([A-Za-z-]+):(?:\s|$)", line):
            fields.append(match.group(1))
    return fields


def _workflow_job_direct_scalar_values(job_block: str, field: str) -> list[str]:
    lines = job_block.splitlines()
    first_line = next((line for line in lines if line.strip()), "")
    if not first_line:
        return []

    job_indent = len(first_line) - len(first_line.lstrip(" "))
    field_indent = job_indent + 2
    return [
        match.group(1).strip().strip("\"'")
        for line in lines[1:]
        if (
            match := re.match(
                rf"^\s{{{field_indent}}}{re.escape(field)}:"
                r"\s*([^#\r\n]+?)\s*(?:#.*)?$",
                line,
            )
        )
    ]


def _workflow_mapping_block(block: str, field: str) -> str:
    lines = block.splitlines()
    first_line = next((line for line in lines if line.strip()), "")
    if not first_line:
        return ""
    first_indent = len(first_line) - len(first_line.lstrip(" "))
    direct_indent = first_indent + 2 if first_line.lstrip().startswith("- ") else first_indent
    for index, line in enumerate(lines):
        match = re.match(
            rf"^\s{{{direct_indent}}}{re.escape(field)}:\s*(?:#.*)?$",
            line,
        )
        if not match:
            continue
        end = len(lines)
        for next_index in range(index + 1, len(lines)):
            next_line = lines[next_index]
            if not next_line.strip():
                continue
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            if next_indent <= direct_indent:
                end = next_index
                break
        return "\n".join(lines[index:end])
    return ""


def _workflow_mapping_direct_scalar_values(mapping_block: str, field: str) -> list[str]:
    lines = mapping_block.splitlines()
    if len(lines) < 2:
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

    return [
        match.group(1).strip().strip("\"'")
        for line in lines[1:]
        if (
            match := re.match(
                rf"^\s{{{child_indent}}}{re.escape(field)}:"
                r"\s*([^#\r\n]+?)\s*(?:#.*)?$",
                line,
            )
        )
    ]


def _workflow_mapping_duplicate_direct_fields(
    mapping_block: str,
    fields: list[str],
) -> list[str]:
    counts: dict[str, int] = {}
    allowed = set(fields)
    for field in _workflow_mapping_direct_field_names(mapping_block):
        if field in allowed:
            counts[field] = counts.get(field, 0) + 1
    return [field for field in fields if counts.get(field, 0) > 1]


def _workflow_mapping_direct_field_names(mapping_block: str) -> list[str]:
    lines = mapping_block.splitlines()
    if len(lines) < 2:
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

    return [
        match.group(1)
        for line in lines[1:]
        if (
            match := re.match(
                rf"^\s{{{child_indent}}}([A-Za-z0-9_-]+):(?:\s|$)",
                line,
            )
        )
    ]


def _workflow_uses_refs(workflow_text: str) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for block in _workflow_step_blocks(workflow_text):
        for value in _workflow_block_direct_scalar_values(block, "uses"):
            refs.append(_workflow_split_uses_ref(value))
    return refs


def _workflow_split_uses_ref(value: str) -> tuple[str, str]:
    if "@" not in value:
        return value, ""
    action, ref = value.rsplit("@", 1)
    return action, ref


def _workflow_step_uses_action(block: str, expected_action: str) -> bool:
    for value in _workflow_block_direct_scalar_values(block, "uses"):
        if "@" not in value:
            continue
        action, _ = _workflow_split_uses_ref(value)
        if action == expected_action:
            return True
    return False


def _workflow_checkout_blocks(workflow_text: str) -> list[str]:
    return [
        block
        for block in _workflow_step_blocks(workflow_text)
        if _workflow_step_uses_action(block, "actions/checkout")
    ]


def _workflow_checkout_block_disables_persisted_credentials(checkout_block: str) -> bool:
    return _workflow_mapping_direct_scalar_values(
        _workflow_mapping_block(checkout_block, "with"),
        "persist-credentials",
    ) == ["false"]


def _workflow_block_sets_env_flag(workflow_text: str, flag: str) -> bool:
    for block in _workflow_env_blocks(workflow_text):
        if _workflow_env_block_sets_flag(block, flag):
            return True
    return False


def _workflow_block_sets_unique_env_flag(workflow_text: str, flag: str) -> bool:
    return (
        not _workflow_block_has_duplicate_env_flag(workflow_text, flag)
        and _workflow_block_sets_env_flag(workflow_text, flag)
    )


def _workflow_block_has_duplicate_env_flag(workflow_text: str, flag: str) -> bool:
    return any(
        _workflow_mapping_duplicate_direct_fields(block, [flag])
        for block in _workflow_env_blocks(workflow_text)
    )


def _workflow_env_blocks(workflow_text: str) -> list[str]:
    lines = workflow_text.splitlines()
    blocks: list[str] = []
    active_scalar_indent: int | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if active_scalar_indent is not None:
            if stripped and indent <= active_scalar_indent:
                active_scalar_indent = None
            else:
                index += 1
                continue

        if re.match(r"^\s*(?:[A-Za-z0-9_-]+:|-\s+run:)\s*(?:\||\|-\s*|>|>-\s*)$", line):
            active_scalar_indent = indent
            index += 1
            continue

        if not re.match(r"^\s*env:\s*(?:#.*)?$", line):
            index += 1
            continue

        start = index
        index += 1
        while index < len(lines):
            next_line = lines[index]
            next_stripped = next_line.strip()
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            if next_stripped and next_indent <= indent:
                break
            index += 1
        blocks.append("\n".join(lines[start:index]))
    return blocks


def _workflow_env_block_sets_flag(env_block: str, flag: str) -> bool:
    lines = env_block.splitlines()
    if len(lines) < 2:
        return False

    child_indent = next(
        (
            len(line) - len(line.lstrip(" "))
            for line in lines[1:]
            if line.strip() and not line.strip().startswith("#")
        ),
        None,
    )
    if child_indent is None:
        return False

    return any(
        re.match(
            rf"^\s{{{child_indent}}}{re.escape(flag)}:\s*[\"']?1[\"']?\s*(?:#.*)?$",
            line,
        )
        for line in lines[1:]
    )


def _workflow_contract_job_is_unconditional(workflow_text: str) -> bool:
    contract_block = next(
        (block for job_name, block in _workflow_job_blocks(workflow_text) if job_name == "contract"),
        "",
    )
    return bool(contract_block) and re.search(r"(?m)^\s{4}if:\s*", contract_block) is None


def _workflow_job_needs_contract(job_block: str) -> bool:
    if re.search(r"(?m)^\s{4}needs:\s*contract\s*$", job_block):
        return True
    if re.search(r"(?m)^\s{4}needs:\s*\[[^\]]*\bcontract\b[^\]]*\]\s*$", job_block):
        return True

    lines = job_block.splitlines()
    needs_index = next(
        (index for index, line in enumerate(lines) if re.match(r"^\s{4}needs:\s*$", line)),
        None,
    )
    if needs_index is None:
        return False
    for line in lines[needs_index + 1:]:
        if line.startswith("    ") and not line.startswith("      "):
            break
        if re.match(r"^\s{6}-\s*contract\s*$", line):
            return True
    return False


def _workflow_job_if_text(job_block: str) -> str:
    lines = job_block.splitlines()
    if_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.match(r"^\s{4}if:\s*", line)
        ),
        None,
    )
    if if_index is None:
        return ""

    first_line = lines[if_index]
    parts = first_line.split(":", 1)
    expression = parts[1].strip() if len(parts) == 2 else ""
    if expression and expression not in {">", ">-", "|", "|-"}:
        return expression

    block_lines: list[str] = []
    for line in lines[if_index + 1:]:
        if line.startswith("    ") and not line.startswith("      "):
            break
        block_lines.append(line.strip())
    return "\n".join(block_lines)


def _workflow_top_level_block(workflow_text: str, key: str) -> list[str]:
    lines = workflow_text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.startswith(f"{key}:")),
        None,
    )
    if start is None:
        return []
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and not line.startswith(" "):
            end = index
            break
    return lines[start:end]


def _workflow_top_level_key_count(workflow_text: str, key: str) -> int:
    return len(
        re.findall(
            rf"(?m)^{re.escape(key)}:(?:\s|$)",
            workflow_text,
        )
    )


def _workflow_dispatch_input_block(workflow_text: str, input_name: str) -> list[str]:
    event_block = _workflow_event_block(workflow_text, "workflow_dispatch")
    if not event_block:
        return []
    start = next(
        (index for index, line in enumerate(event_block) if line == f"      {input_name}:"),
        None,
    )
    if start is None:
        return []
    end = len(event_block)
    for index in range(start + 1, len(event_block)):
        line = event_block[index]
        if line.startswith("      ") and not line.startswith("        "):
            end = index
            break
        if line.startswith("  ") and not line.startswith("    "):
            end = index
            break
    return event_block[start:end]


def _workflow_dispatch_input_names(workflow_text: str) -> list[str]:
    event_block = _workflow_event_block(workflow_text, "workflow_dispatch")
    if not event_block:
        return []
    names: list[str] = []
    for line in event_block[1:]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        if match := re.match(r"^      ([A-Za-z0-9_-]+):\s*(?:#.*)?$", line):
            names.append(match.group(1))
    return names


def _workflow_dispatch_duplicate_input_names(workflow_text: str) -> list[str]:
    counts: dict[str, int] = {}
    for name in _workflow_dispatch_input_names(workflow_text):
        counts[name] = counts.get(name, 0) + 1
    return [name for name, count in counts.items() if count > 1]


def _workflow_dispatch_input_duplicate_fields(
    input_block: list[str],
    fields: list[str],
) -> list[str]:
    counts: dict[str, int] = {}
    allowed = set(fields)
    for field in _workflow_dispatch_input_field_names(input_block):
        if field in allowed:
            counts[field] = counts.get(field, 0) + 1
    return [field for field in fields if counts.get(field, 0) > 1]


def _workflow_dispatch_input_field_names(input_block: list[str]) -> list[str]:
    fields: list[str] = []
    for line in input_block[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if match := re.match(r"^([A-Za-z-]+):\s*", stripped):
            fields.append(match.group(1))
    return fields


def _workflow_dispatch_input_is_boolean_default_false(input_block: list[str]) -> bool:
    entries: dict[str, str] = {}
    for line in input_block[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z-]+):\s*(.+?)\s*$", stripped)
        if match:
            entries[match.group(1)] = match.group(2).strip("\"'")
    return entries.get("type") == "boolean" and entries.get("default") == "false"


def _workflow_event_block(workflow_text: str, event_name: str) -> list[str]:
    lines = _workflow_top_level_block(workflow_text, "on")
    if not lines:
        return []
    start = next(
        (index for index, line in enumerate(lines) if line == f"  {event_name}:"),
        None,
    )
    if start is None:
        return []
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    "):
            end = index
            break
        if line and not line.startswith(" "):
            end = index
            break
    return lines[start:end]


def _workflow_event_names(workflow_text: str) -> list[str]:
    lines = _workflow_top_level_block(workflow_text, "on")
    if not lines or lines[0] != "on:":
        return []
    names: list[str] = []
    for line in lines[1:]:
        if line and not line.startswith(" "):
            break
        if match := re.match(r"^  ([A-Za-z0-9_-]+):(?:\s|$)", line):
            names.append(match.group(1))
    return names


def _workflow_duplicate_event_names(workflow_text: str) -> list[str]:
    counts: dict[str, int] = {}
    for name in _workflow_event_names(workflow_text):
        counts[name] = counts.get(name, 0) + 1
    return [name for name, count in counts.items() if count > 1]


def _workflow_event_duplicate_direct_fields(
    workflow_text: str,
    event_name: str,
    fields: list[str],
) -> list[str]:
    block = _workflow_event_block(workflow_text, event_name)
    if not block:
        return []
    counts: dict[str, int] = {}
    allowed = set(fields)
    for field in _workflow_event_direct_field_names(block):
        if field in allowed:
            counts[field] = counts.get(field, 0) + 1
    return [field for field in fields if counts.get(field, 0) > 1]


def _workflow_event_direct_field_names(event_block: list[str]) -> list[str]:
    fields: list[str] = []
    for line in event_block[1:]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        if match := re.match(r"^    ([A-Za-z0-9_-]+):(?:\s|$)", line):
            fields.append(match.group(1))
    return fields


def _workflow_event_has_direct_field(
    workflow_text: str,
    event_name: str,
    field: str,
) -> bool:
    return field in _workflow_event_direct_field_names(
        _workflow_event_block(workflow_text, event_name)
    )


def _workflow_event_filter_values(
    workflow_text: str,
    event_name: str,
    field: str,
) -> set[str]:
    block = _workflow_event_block(workflow_text, event_name)
    if not block:
        return set()
    values: set[str] = set()
    for index, line in enumerate(block[1:], start=1):
        match = re.match(rf"^    {re.escape(field)}:\s*(.*?)\s*(?:#.*)?$", line)
        if not match:
            continue
        raw_value = match.group(1).strip()
        if raw_value:
            values.update(_workflow_inline_filter_values(raw_value))
            return values
        for child_line in block[index + 1:]:
            if child_line.startswith("    ") and not child_line.startswith("      "):
                break
            child_match = re.match(r"^\s*-\s*(.+?)\s*$", child_line)
            if child_match:
                values.add(child_match.group(1).strip("\"'"))
        return values
    return values


def _workflow_inline_filter_values(raw_value: str) -> set[str]:
    value = raw_value.strip().strip("\"'")
    if value.startswith("[") and value.endswith("]"):
        return {
            item.strip().strip("\"'")
            for item in value[1:-1].split(",")
            if item.strip()
        }
    return {value} if value else set()


def _workflow_event_paths(workflow_text: str, event_name: str) -> set[str]:
    block = _workflow_event_block(workflow_text, event_name)
    if not block:
        return set()
    in_paths = False
    paths: set[str] = set()
    for line in block[1:]:
        if line == "    paths:":
            in_paths = True
            continue
        if in_paths and line.startswith("    ") and not line.startswith("      "):
            break
        if in_paths:
            match = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if match:
                paths.add(match.group(1).strip("\"'"))
    return paths


def _workflow_job_blocks(workflow_text: str) -> list[tuple[str, str]]:
    lines = workflow_text.splitlines()
    jobs_line_index = next(
        (index for index, line in enumerate(lines) if line == "jobs:"),
        None,
    )
    if jobs_line_index is None:
        return []
    job_starts: list[tuple[int, str]] = []
    for index in range(jobs_line_index + 1, len(lines)):
        line = lines[index]
        if line and not line.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            job_starts.append((index, match.group(1)))
    blocks: list[tuple[str, str]] = []
    for position, (start, job_name) in enumerate(job_starts):
        end = job_starts[position + 1][0] if position + 1 < len(job_starts) else len(lines)
        blocks.append((job_name, "\n".join(lines[start:end])))
    return blocks


def _workflow_duplicate_job_names(workflow_text: str) -> list[str]:
    counts: dict[str, int] = {}
    for job_name, _ in _workflow_job_blocks(workflow_text):
        counts[job_name] = counts.get(job_name, 0) + 1
    return [job_name for job_name, count in counts.items() if count > 1]
