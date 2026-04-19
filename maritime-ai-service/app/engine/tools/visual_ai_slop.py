"""AI Slop detection for visual HTML output.

Inspired by Claude Design's "avoid AI slop" guidelines — patterns that make
output look obviously AI-generated. This module provides programmatic checks
that can be used by the visual verifier and quality scoring pipeline.

Anti-patterns detected:
- Gradient overuse (linear-gradient on everything)
- Emoji spam (excessive emoji in non-brand context)
- "AI card" trope (rounded corners + left-border accent)
- Banned fonts as primary (Inter, Roboto, Arial, system-ui)
- Purple-blue gradient hero sections
- Data slop (unnecessary stats/numbers that add no value)
- Symmetric cookie-cutter section layouts
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(slots=True)
class SlopViolation:
    """A single AI slop anti-pattern violation."""

    rule: str
    severity: str  # "high" | "medium" | "low"
    message: str


def check_ai_slop_patterns(html: str) -> list[SlopViolation]:
    """Check HTML output against AI slop anti-patterns.

    Returns list of violations found. Empty list = clean output.
    """
    violations: list[SlopViolation] = []
    lowered = html.lower()

    # 1. Gradient overuse (>3 gradients in one page)
    gradient_count = (
        lowered.count("linear-gradient")
        + lowered.count("radial-gradient")
        + lowered.count("conic-gradient")
    )
    if gradient_count > 3:
        violations.append(SlopViolation(
            rule="gradient_overuse",
            severity="high",
            message=f"Found {gradient_count} gradients — AI-generated pages tend to overuse them. "
                    "Use solid colors or at most 1-2 subtle gradients.",
        ))

    # 2. Emoji spam (>5 emoji in non-brand context)
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F9FF"  # Misc Symbols and Pictographs + Emoticons
        "\U00002600-\U000027BF"  # Misc symbols
        "\U0001FA00-\U0001FA6F"  # Chess, symbols
        "\U0001FA70-\U0001FAFF"  # Symbols Extended-A
        "]+",
        re.UNICODE,
    )
    emoji_matches = emoji_pattern.findall(html)
    emoji_count = sum(len(m) for m in emoji_matches)
    if emoji_count > 5:
        violations.append(SlopViolation(
            rule="emoji_spam",
            severity="medium",
            message=f"Found {emoji_count} emoji — excessive emoji is a common AI slop marker. "
                    "Use only if brand explicitly requires it.",
        ))

    # 3. "AI card" trope: rounded corners + left-border accent + gradient
    has_border_left = "border-left" in lowered
    has_border_radius = "border-radius" in lowered
    has_gradient = gradient_count > 0
    if has_border_left and has_border_radius and has_gradient:
        violations.append(SlopViolation(
            rule="ai_card_trope",
            severity="medium",
            message="Combination of border-left + border-radius + gradient detected — "
                    "the classic 'AI card' pattern. Vary your card styles.",
        ))

    # 4. Banned fonts as primary
    banned_fonts = ("inter", "roboto", "arial", "system-ui", "fraunces")
    for font in banned_fonts:
        # Check font-family declarations (not in comments)
        font_patterns = [
            f"font-family: {font}",
            f"font-family:{font}",
            f"font-family: '{font}'",
            f"font-family:'{font}'",
            f'font-family: "{font}"',
        ]
        for pattern in font_patterns:
            if pattern in lowered:
                violations.append(SlopViolation(
                    rule="banned_font",
                    severity="low",
                    message=f"'{font}' is an overused AI-default font. "
                            "Use a distinctive font like 'DM Sans', 'Outfit', 'Sora', "
                            "or Wiii's system font stack.",
                ))
                break
        else:
            continue
        break  # Only report first banned font

    # 5. Purple-blue gradient hero section
    purple_colors = ("#8b5cf6", "#7c3aed", "#6d28d9", "#a855f7", "#9333ea")
    has_purple = any(c in lowered for c in purple_colors) or "purple" in lowered
    hero_keywords = ("hero", "banner", "jumbotron", "headline-section")
    has_hero = any(kw in lowered for kw in hero_keywords)
    if "linear-gradient" in lowered and has_purple and has_hero:
        violations.append(SlopViolation(
            rule="purple_gradient_hero",
            severity="high",
            message="Purple-blue gradient hero section — the most recognizable AI slop pattern. "
                    "Use Wiii warm palette (#D97757, #85CDCA, #FFD166) instead.",
        ))

    # 6. Data slop: too many stat/number cards without context
    stat_patterns = [
        'class="stat',
        'class="metric',
        'class="counter',
        'class="kpi',
        "stat-card",
        "metric-card",
    ]
    stat_count = sum(lowered.count(p) for p in stat_patterns)
    if stat_count > 6:
        violations.append(SlopViolation(
            rule="data_slop",
            severity="medium",
            message=f"Found {stat_count} stat/metric elements — 'data slop' makes output feel "
                    "like an AI dashboard template. Only include metrics that earn their place.",
        ))

    # 7. Cookie-cutter sections (heading + icon + description pattern repeated)
    section_pattern = re.compile(
        r'<div[^>]*class="[^"]*(?:feature|service|benefit|card)[^"]*"[^>]*>.*?'
        r'<h[23][^>]*>.*?</h[23]>.*?'
        r'<p[^>]*>.*?</p>',
        re.DOTALL | re.IGNORECASE,
    )
    section_matches = section_pattern.findall(html)
    if len(section_matches) > 4:
        violations.append(SlopViolation(
            rule="cookie_cutter_sections",
            severity="low",
            message=f"Found {len(section_matches)} similar section patterns — "
                    "AI tends to repeat the same heading+icon+description structure. "
                    "Vary layout, density, and visual treatment.",
        ))

    # 8. Emoji in structural UI elements (buttons, headings, labels)
    # Emoji in user content (p, td, li) is acceptable — but UI chrome must be emoji-free.
    structural_emoji_pattern = re.compile(
        r'<(?:button|h[1-6]|label|legend|caption|summary)[^>]*>'
        r'[^<]*'
        r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FAFF]',
        re.UNICODE,
    )
    structural_emoji_matches = structural_emoji_pattern.findall(html)
    if structural_emoji_matches:
        violations.append(SlopViolation(
            rule="emoji_in_code_elements",
            severity="high",
            message=f"Found {len(structural_emoji_matches)} emoji in structural UI elements "
                    "(buttons, headings, labels). Use inline SVG icons instead of emoji — "
                    "they are more professional and theme-adaptive.",
        ))

    return violations


def check_ai_slop_summary(html: str) -> dict[str, list[str]]:
    """Return a summary of AI slop check — {severity: [messages]}.

    Useful for logging and verification reports.
    """
    violations = check_ai_slop_patterns(html)
    summary: dict[str, list[str]] = {"high": [], "medium": [], "low": []}
    for v in violations:
        summary.setdefault(v.severity, []).append(v.message)
    return summary
