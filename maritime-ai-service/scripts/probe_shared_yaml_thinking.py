#!/usr/bin/env python3
"""
Probe Gemini native thinking using ONLY prompt instructions loaded from base/_shared.yaml.

Purpose:
- validate that _shared.yaml is restored and can drive native thinking on its own
- avoid public_thinking_renderer and any gray-rail authoring layer
- dump the exact system prompt assembled from shared.yaml so humans can audit it

Examples:
    python scripts/probe_shared_yaml_thinking.py
    python scripts/probe_shared_yaml_thinking.py --prompt "Giải thích Quy tắc 15 COLREGs"
    python scripts/probe_shared_yaml_thinking.py --model gemini-3.1-flash-lite-preview
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

import yaml
from dotenv import load_dotenv
from google import genai
from google.genai import types


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parent
REPORTS_ROOT = REPO_ROOT / ".Codex" / "reports"
SHARED_YAML_PATH = SERVICE_ROOT / "app" / "prompts" / "base" / "_shared.yaml"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

load_dotenv(SERVICE_ROOT / ".env")
load_dotenv(SERVICE_ROOT / ".env.local")

from app.core.config import settings


DEFAULT_PROMPTS = [
    "Giải thích Quy tắc 15 COLREGs.",
    "Mình tên Nam, nhớ giúp mình nhé.",
    "Phân tích giá dầu hôm nay.",
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
        help="Gemini model name.",
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
        help="Optional thinking budget.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="Sampling temperature.",
    )
    parser.add_argument(
        "--prompt",
        action="append",
        default=[],
        help="Prompt to probe. Can be repeated.",
    )
    parser.add_argument(
        "--report-prefix",
        default="SHARED-YAML-NATIVE-THINKING",
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


def load_shared_yaml() -> dict[str, Any]:
    return yaml.safe_load(SHARED_YAML_PATH.read_text(encoding="utf-8")) or {}


def build_shared_only_system_prompt(shared_cfg: dict[str, Any]) -> str:
    reasoning_cfg = shared_cfg.get("reasoning", {}) or {}
    thinking_cfg = shared_cfg.get("thinking", {}) or {}

    lines = [
        "Bạn đang chạy trong chế độ thử nghiệm prompt: CHỈ dùng shared.yaml nền tảng của Wiii.",
        "Không có character card riêng, không có tutor surface riêng, không có public_thinking_renderer.",
        "Mục tiêu: để model tự nghĩ bằng native thinking nhiều nhất có thể, rồi mới trả lời bằng tiếng Việt.",
        "",
        "== SHARED REASONING ==",
    ]

    for rule in reasoning_cfg.get("rules", []) or []:
        lines.append(f"- {str(rule).strip()}")

    ambiguous_cfg = reasoning_cfg.get("ambiguous_handling", {}) or {}
    ambiguous_desc = (ambiguous_cfg.get("description") or "").strip()
    if ambiguous_desc:
        lines.extend(["", "== AMBIGUOUS HANDLING ==", ambiguous_desc])
    for rule in ambiguous_cfg.get("rules", []) or []:
        lines.append(f"- {str(rule).strip()}")

    thinking_instruction = (thinking_cfg.get("instruction") or "").strip()
    if thinking_instruction:
        lines.extend(["", "== SHARED THINKING INSTRUCTION ==", thinking_instruction])

    lines.extend(
        [
            "",
            "Yêu cầu thêm cho mode thử nghiệm này:",
            "- Nếu model hỗ trợ native thinking, hãy dùng native thinking trước khi trả lời.",
            "- Thinking phải là suy nghĩ thật của model, không dựng lại câu trả lời dưới dạng nháp.",
            "- Không cần cố làm vừa lòng; ưu tiên nghĩ thật, cụ thể, và bám đúng câu hỏi.",
            "- Không cần chèn tag <thinking> nếu native thinking đã được tách bởi API.",
        ]
    )
    return "\n".join(lines).strip()


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
    system_prompt: str,
    prompts: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Shared YAML Native Thinking Probe - {stamp}",
        "",
        "## Config",
        "",
        f"- Model: `{model}`",
        f"- Thinking level: `{thinking_level}`",
        f"- Thinking budget: `{thinking_budget if thinking_budget is not None else '(default)'}`",
        f"- API key: `{api_key_masked}`",
        "- Prompt source: `app/prompts/base/_shared.yaml only`",
        "- Renderer: `not used`",
        "- Persona card: `not used`",
        "",
        "## System Prompt Used",
        "",
        "```text",
        system_prompt,
        "```",
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
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()
    prompts = args.prompt or list(DEFAULT_PROMPTS)
    if not args.api_key:
        raise SystemExit("Missing GOOGLE_API_KEY.")

    shared_cfg = load_shared_yaml()
    system_prompt = build_shared_only_system_prompt(shared_cfg)

    client = genai.Client(api_key=args.api_key)
    config = build_generate_config(
        system_prompt=system_prompt,
        temperature=args.temperature,
        thinking_level=args.thinking_level,
        thinking_budget=args.thinking_budget,
    )

    stamp = utc_stamp()
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)

    prompt_reports: list[dict[str, Any]] = []
    for prompt in prompts:
        response = client.models.generate_content(
            model=args.model,
            contents=prompt,
            config=config,
        )
        parts = extract_parts(response)
        thought_texts = [part.text for part in parts if part.thought and part.text.strip()]
        text_parts = [part.text for part in parts if not part.thought and part.text.strip()]

        prompt_reports.append(
            {
                "prompt": prompt,
                "response_text": getattr(response, "text", "") or "\n".join(text_parts),
                "thought_part_count": len(thought_texts),
                "text_part_count": len(text_parts),
                "thought_texts": thought_texts,
                "text_parts": text_parts,
                "parts": [asdict(part) for part in parts],
                "response_raw": safe_to_jsonable(response),
                "usage_metadata": safe_to_jsonable(getattr(response, "usage_metadata", None)),
            }
        )

    json_payload = {
        "stamp": stamp,
        "model": args.model,
        "thinking_level": args.thinking_level,
        "thinking_budget": args.thinking_budget,
        "api_key_masked": mask_api_key(args.api_key),
        "shared_yaml_path": str(SHARED_YAML_PATH),
        "system_prompt": system_prompt,
        "prompts": prompt_reports,
    }

    json_path = REPORTS_ROOT / f"{args.report_prefix}-{stamp}.json"
    md_path = REPORTS_ROOT / f"{args.report_prefix}-{stamp}.md"

    json_path.write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        render_markdown(
            stamp=stamp,
            model=args.model,
            thinking_level=args.thinking_level,
            thinking_budget=args.thinking_budget,
            api_key_masked=mask_api_key(args.api_key),
            system_prompt=system_prompt,
            prompts=prompt_reports,
        ),
        encoding="utf-8",
    )

    print(str(json_path))
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
