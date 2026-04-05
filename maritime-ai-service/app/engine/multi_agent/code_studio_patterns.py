"""Shared regex patterns for Code Studio response sanitization."""

from __future__ import annotations

import re

_CODE_STUDIO_ACTION_JSON_RE = re.compile(
    r"""
    \{
        \s*"action"\s*:\s*"[^"]+"
        (?:
            \s*,\s*"action_input"\s*:\s*
            (?:
                "(?:\\.|[^"])*"
                |
                \{.*?\}
                |
                \[.*?\]
                |
                [^}\n]+
            )
        )?
        (?:
            \s*,\s*"thought"\s*:\s*"(?:\\.|[^"])*"
        )?
        \s*
    \}
    """,
    re.DOTALL | re.VERBOSE,
)
_CODE_STUDIO_SANDBOX_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(sandbox:[^)]+\)", re.IGNORECASE)
_CODE_STUDIO_SANDBOX_LINK_RE = re.compile(r"\[[^\]]+\]\(sandbox:[^)]+\)", re.IGNORECASE)
_CODE_STUDIO_SANDBOX_PATH_RE = re.compile(r"(?:sandbox:[^\s)]+|/(?:mnt/data|workspace)/[^\s)]+)")
