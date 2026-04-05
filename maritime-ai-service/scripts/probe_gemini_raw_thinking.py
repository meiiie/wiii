#!/usr/bin/env python3
"""
Direct Gemini raw-thinking probe for plain-model inspection.

Purpose:
- call Gemini directly through the Google GenAI SDK
- use NO Wiii persona / NO PromptLoader / NO backend pipeline
- enable Gemini thinking with include_thoughts=True
- dump raw response + extracted thought parts so the team can inspect
  what the model itself is doing before any Wiii shaping

Examples:
    python scripts/probe_gemini_raw_thinking.py
    python scripts/probe_gemini_raw_thinking.py --model gemini-3.1-flash --thinking-level deep
    python scripts/probe_gemini_raw_thinking.py --prompt "Phân tích giá dầu hôm nay"
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


DEFAULT_PROMPTS = [
    "Phân tích giá dầu hôm nay.",
    "Giải thích Quy tắc 15 COLREGs.",
]


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
    parser.add_argument(
        "--api-key",
        default=os.getenv("GOOGLE_API_KEY") or settings.google_api_key,
        help="Gemini API key. Defaults to GOOGLE_API_KEY from .env",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("GOOGLE_MODEL") or settings.google_model,
        help="Gemini model name. Example: gemini-3.1-flash",
    )
    parser.add_argument(
        "--thinking-level",
        default="deep",
        help="Thinking level alias: minimal|medium|high|deep. 'deep' maps to HIGH.",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=None,
        help="Optional thinking budget. If provided, sent alongside include_thoughts.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature.",
    )
    parser.add_argument(
        "--prompt",
        action="append",
        default=[],
        help="Prompt to probe. Can be repeated. If omitted, two built-in prompts are used.",
    )
    parser.add_argument(
        "--report-prefix",
        default="GEMINI-RAW-THINKING",
        help="Report filename prefix in .Codex/reports.",
    )
    return parser.parse_args()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S")


def mask_api_key(value: str | None) -> str:
    if not value:
        return "(missing)"
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def compact_text(text: str | None, limit: int = 200) -> str:
    if not text:
        return ""
    joined = " ".join(str(text).split())
    if len(joined) <= limit:
        return joined
    return joined[: limit - 3] + "..."


def thinking_level_from_name(name: str) -> types.ThinkingLevel:
    normalized = (name or "").strip().upper()
    if normalized == "DEEP":
        normalized = "HIGH"
    return types.ThinkingLevel[normalized]


def safe_to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {
            "type": "bytes",
            "length": len(value),
            "preview_hex": value[:16].hex(),
        }
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
        return {
            key: safe_to_jsonable(val)
            for key, val in vars(value).items()
            if not key.startswith("_")
        }
    return repr(value)


def build_generate_config(
    *,
    temperature: float,
    thinking_level: str,
    thinking_budget: int | None,
) -> types.GenerateContentConfig:
    kwargs: dict[str, Any] = {
        "temperature": temperature,
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
                        signature[:32].hex() if isinstance(signature, bytes) else compact_text(str(signature), 80)
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
    thinking_level: str,
    thinking_budget: int | None,
    api_key_masked: str,
    prompts: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Gemini Raw Thinking Probe - {stamp}",
        "",
        "## Config",
        "",
        f"- Model: `{model}`",
        f"- Thinking level: `{thinking_level}`",
        f"- Thinking budget: `{thinking_budget if thinking_budget is not None else '(default)'}`",
        f"- API key: `{api_key_masked}`",
        "- Persona/system prompt: `none`",
        "- Transport: `google.genai direct SDK`",
        "",
    ]
    for index, item in enumerate(prompts, start=1):
        lines.extend(
            [
                f"## Prompt {index}",
                "",
                f"**Prompt**: `{item['prompt']}`",
                "",
                f"**Plain text output**: {item['response_text'] or '(empty)' }",
                "",
                f"**Thought parts found**: `{item['thought_part_count']}`",
                f"**Text parts found**: `{item['text_part_count']}`",
                "",
            ]
        )
        if item["thought_texts"]:
            lines.append("### Thought Parts")
            lines.append("")
            for thought_index, thought in enumerate(item["thought_texts"], start=1):
                lines.append(f"{thought_index}. {thought}")
            lines.append("")
        else:
            lines.append("### Thought Parts")
            lines.append("")
            lines.append("No explicit thought parts were returned by the SDK for this prompt.")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)

    if not args.api_key:
        print("GOOGLE_API_KEY is missing.", file=sys.stderr)
        return 2

    prompts = args.prompt or list(DEFAULT_PROMPTS)
    stamp = utc_stamp()
    json_path = REPORTS_ROOT / f"{args.report_prefix}-{stamp}.json"
    md_path = REPORTS_ROOT / f"{args.report_prefix}-{stamp}.md"

    client = genai.Client(api_key=args.api_key)
    config = build_generate_config(
        temperature=args.temperature,
        thinking_level=args.thinking_level,
        thinking_budget=args.thinking_budget,
    )

    prompt_results: list[dict[str, Any]] = []
    for prompt in prompts:
        response = client.models.generate_content(
            model=args.model,
            contents=prompt,
            config=config,
        )
        parts = extract_parts(response)
        thought_texts = [part.text for part in parts if part.thought and part.text]
        text_texts = [part.text for part in parts if (not part.thought) and part.text]
        prompt_results.append(
            {
                "prompt": prompt,
                "response_text": getattr(response, "text", None) or "",
                "thought_part_count": len(thought_texts),
                "text_part_count": len(text_texts),
                "thought_texts": thought_texts,
                "text_texts": text_texts,
                "parts": [asdict(part) for part in parts],
                "usage_metadata": safe_to_jsonable(getattr(response, "usage_metadata", None)),
                "raw_response": safe_to_jsonable(response),
            }
        )

    report_payload = {
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "model": args.model,
        "thinking_level": args.thinking_level,
        "thinking_budget": args.thinking_budget,
        "temperature": args.temperature,
        "api_key_masked": mask_api_key(args.api_key),
        "persona_prompt": None,
        "system_prompt": None,
        "prompt_results": prompt_results,
    }

    json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        render_markdown(
            stamp=stamp,
            model=args.model,
            thinking_level=args.thinking_level,
            thinking_budget=args.thinking_budget,
            api_key_masked=mask_api_key(args.api_key),
            prompts=prompt_results,
        ),
        encoding="utf-8",
    )

    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    for item in prompt_results:
        print("-" * 72)
        print("PROMPT:", item["prompt"])
        print("Thought parts:", item["thought_part_count"])
        if item["thought_texts"]:
            for idx, thought in enumerate(item["thought_texts"], start=1):
                print(f"  [{idx}] {compact_text(thought, 320)}")
        else:
            print("  (no explicit thought parts returned)")
        print("Text preview:", compact_text(item["response_text"], 320))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
