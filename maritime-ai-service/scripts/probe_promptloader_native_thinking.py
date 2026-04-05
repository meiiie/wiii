#!/usr/bin/env python3
"""
Probe Gemini native thinking using PromptLoader.build_system_prompt().

Purpose:
- keep native thinking owned by the model
- inject Wiii's current prompt stack more faithfully than shared-only mode
- inspect the exact system prompt used after PromptLoader composes:
  shared.yaml + persona YAML + runtime card + soul/mood/context
- avoid public_thinking_renderer and other post-hoc gray-rail authoring
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parent
REPORTS_ROOT = REPO_ROOT / ".Codex" / "reports"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

load_dotenv(SERVICE_ROOT / ".env")
load_dotenv(SERVICE_ROOT / ".env.local")

from app.core.config import settings
from app.prompts.prompt_loader import PromptLoader


@dataclass
class ExtractedPart:
    candidate_index: int
    part_index: int
    kind: str
    text: str
    thought: bool
    thought_signature_present: bool
    thought_signature_preview: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", default=os.getenv("GOOGLE_API_KEY") or settings.google_api_key)
    parser.add_argument("--model", default=os.getenv("GOOGLE_MODEL") or settings.google_model)
    parser.add_argument("--thinking-level", default="deep")
    parser.add_argument("--thinking-budget", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--role", default="tutor")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--report-prefix", default="PROMPTLOADER-NATIVE-THINKING")
    parser.add_argument("--user-name", default=None)
    parser.add_argument("--user-id", default="probe-user")
    parser.add_argument("--organization-id", default=None)
    parser.add_argument("--mood-hint", default="Người dùng đang cần một nhịp giải thích rõ và có cảm giác được đồng hành.")
    parser.add_argument("--personality-mode", default="soul")
    parser.add_argument("--conversation-summary", default=None)
    parser.add_argument("--user-fact", action="append", default=[])
    parser.add_argument("--recent-phrase", action="append", default=[])
    parser.add_argument("--is-follow-up", action="store_true")
    parser.add_argument("--name-usage-count", type=int, default=0)
    parser.add_argument("--total-responses", type=int, default=0)
    return parser.parse_args()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")


def mask_api_key(value: str | None) -> str:
    if not value:
        return "(missing)"
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def thinking_level_from_name(name: str) -> types.ThinkingLevel:
    normalized = (name or "").strip().upper()
    if normalized == "DEEP":
        normalized = "HIGH"
    return types.ThinkingLevel[normalized]


def safe_to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"type": "bytes", "length": len(value), "preview_hex": value[:16].hex()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [safe_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [safe_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): safe_to_jsonable(val) for key, val in value.items()}
    if hasattr(value, "model_dump"):
        try:
            return safe_to_jsonable(value.model_dump(mode="json", exclude_none=False))
        except Exception:
            try:
                return safe_to_jsonable(value.model_dump())
            except Exception:
                pass
    if hasattr(value, "__dict__"):
        return {key: safe_to_jsonable(val) for key, val in vars(value).items() if not key.startswith("_")}
    return repr(value)


def build_generate_config(
    *,
    system_prompt: str,
    temperature: float,
    thinking_level: str,
    thinking_budget: int | None,
) -> types.GenerateContentConfig:
    kwargs: dict[str, Any] = {
        "temperature": temperature,
        "system_instruction": system_prompt,
        "thinking_config": types.ThinkingConfig(
            thinking_level=thinking_level_from_name(thinking_level),
            include_thoughts=True,
        ),
    }
    if thinking_budget is not None:
        kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=thinking_level_from_name(thinking_level),
            thinking_budget=thinking_budget,
            include_thoughts=True,
        )
    return types.GenerateContentConfig(**kwargs)


def extract_parts(response: Any) -> list[ExtractedPart]:
    extracted: list[ExtractedPart] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate_index, candidate in enumerate(candidates):
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part_index, part in enumerate(parts):
            text = getattr(part, "text", None) or ""
            thought = bool(getattr(part, "thought", False))
            signature = getattr(part, "thought_signature", None)
            extracted.append(
                ExtractedPart(
                    candidate_index=candidate_index,
                    part_index=part_index,
                    kind="thought" if thought else "text",
                    text=text,
                    thought=thought,
                    thought_signature_present=signature is not None,
                    thought_signature_preview=(
                        signature[:32].hex() if isinstance(signature, bytes) else str(signature)[:80]
                    )
                    if signature is not None
                    else "",
                )
            )
    return extracted


def render_markdown(
    *,
    stamp: str,
    model: str,
    role: str,
    api_key_masked: str,
    system_prompt: str,
    prompt: str,
    thought_texts: list[str],
    response_text: str,
) -> str:
    lines = [
        f"# PromptLoader Native Thinking Probe - {stamp}",
        "",
        "## Config",
        "",
        f"- Model: `{model}`",
        f"- Role: `{role}`",
        f"- API key: `{api_key_masked}`",
        "- Source: `PromptLoader.build_system_prompt()`",
        "- Renderer: `not used`",
        "",
        "## System Prompt Used",
        "",
        "```text",
        system_prompt,
        "```",
        "",
        "## User Prompt",
        "",
        f"`{prompt}`",
        "",
        "## Thought Parts",
        "",
    ]
    if thought_texts:
        for idx, thought in enumerate(thought_texts, start=1):
            lines.extend([f"### Thought {idx}", "", "```text", thought, "```", ""])
    else:
        lines.append("(none)")
        lines.append("")
    lines.extend(["## Final Answer", "", "```text", response_text or "", "```", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if not args.api_key:
        raise SystemExit("Missing GOOGLE_API_KEY.")

    loader = PromptLoader()
    system_prompt = loader.build_system_prompt(
        args.role,
        user_name=args.user_name,
        conversation_summary=args.conversation_summary,
        user_facts=args.user_fact or None,
        recent_phrases=args.recent_phrase or None,
        is_follow_up=bool(args.is_follow_up),
        name_usage_count=args.name_usage_count,
        total_responses=args.total_responses,
        mood_hint=args.mood_hint,
        personality_mode=args.personality_mode,
        user_id=args.user_id,
        organization_id=args.organization_id,
    )

    client = genai.Client(api_key=args.api_key)
    config = build_generate_config(
        system_prompt=system_prompt,
        temperature=args.temperature,
        thinking_level=args.thinking_level,
        thinking_budget=args.thinking_budget,
    )

    response = client.models.generate_content(
        model=args.model,
        contents=args.prompt,
        config=config,
    )

    parts = extract_parts(response)
    thought_texts = [part.text for part in parts if part.thought and part.text.strip()]
    text_parts = [part.text for part in parts if not part.thought and part.text.strip()]
    response_text = getattr(response, "text", "") or "\n".join(text_parts)

    stamp = utc_stamp()
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)

    payload = {
        "stamp": stamp,
        "model": args.model,
        "role": args.role,
        "api_key_masked": mask_api_key(args.api_key),
        "user_name": args.user_name,
        "user_id": args.user_id,
        "organization_id": args.organization_id,
        "mood_hint": args.mood_hint,
        "personality_mode": args.personality_mode,
        "conversation_summary": args.conversation_summary,
        "user_facts": args.user_fact,
        "recent_phrases": args.recent_phrase,
        "is_follow_up": bool(args.is_follow_up),
        "name_usage_count": args.name_usage_count,
        "total_responses": args.total_responses,
        "prompt": args.prompt,
        "system_prompt": system_prompt,
        "thought_texts": thought_texts,
        "response_text": response_text,
        "parts": [asdict(part) for part in parts],
        "response_raw": safe_to_jsonable(response),
        "usage_metadata": safe_to_jsonable(getattr(response, "usage_metadata", None)),
    }

    json_path = REPORTS_ROOT / f"{args.report_prefix}-{stamp}.json"
    md_path = REPORTS_ROOT / f"{args.report_prefix}-{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        render_markdown(
            stamp=stamp,
            model=args.model,
            role=args.role,
            api_key_masked=mask_api_key(args.api_key),
            system_prompt=system_prompt,
            prompt=args.prompt,
            thought_texts=thought_texts,
            response_text=response_text,
        ),
        encoding="utf-8",
    )

    print(str(json_path))
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
