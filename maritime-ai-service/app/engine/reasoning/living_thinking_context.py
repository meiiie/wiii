"""Living-core context distilled for public thinking surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.engine.character.character_card import (
    build_character_card_payload,
    get_wiii_character_card,
)


class ThinkingSoulIntensity(str, Enum):
    RESTRAINED = "restrained"
    BALANCED = "balanced"
    LIVING = "living"


@dataclass(slots=True)
class LivingThinkingContext:
    lane: str
    intent: str = ""
    personality_mode: str = ""
    soul_intensity: ThinkingSoulIntensity = ThinkingSoulIntensity.BALANCED
    summary: str = ""
    identity_anchor: str = ""
    voice_tone: str = ""
    expressive_language: str = ""
    runtime_notes: tuple[str, ...] = ()
    relationship_style: tuple[str, ...] = ()
    reasoning_style: tuple[str, ...] = ()

    @property
    def should_sound_living(self) -> bool:
        return self.soul_intensity != ThinkingSoulIntensity.RESTRAINED or self.personality_mode == "soul"


def build_public_thinking_persona_brief(
    living_context: LivingThinkingContext | None,
) -> str:
    """Create a lane-aware identity brief for public thinking generation.

    This is intentionally softer than a rule block. The goal is to remind the
    model how Wiii's inner voice feels without forcing a rigid reasoning shape.
    """

    card = get_wiii_character_card()
    lane = (getattr(living_context, "lane", "") or "").strip().lower()
    soul_intensity = getattr(
        living_context,
        "soul_intensity",
        ThinkingSoulIntensity.BALANCED,
    )
    identity_anchor = (getattr(living_context, "identity_anchor", "") or card.identity_anchor or "").strip()
    voice_tone = (getattr(living_context, "voice_tone", "") or card.voice_tone or "").strip()

    lines: list[str] = [
        f"Wiii la {card.name}: mot AI dong hanh song, am, to mo, va co nhip rieng.",
        "Trong public thinking, Wiii dang tu lum bum voi chinh minh, khong dang bieu dien cho user xem.",
        "Soul cua Wiii nam o nhip suy tu, su co mat, va cach can nhac tinh te; khong nam o roleplay hay mascot behavior.",
        "Do dang yeu cua Wiii den tu su am ap, thanh that, va tiet tau tu nhien; dung bien thinking thanh man trang tri re tien.",
    ]

    if voice_tone:
        lines.append(f"Giong nen cua Wiii: {voice_tone}.")

    if soul_intensity == ThinkingSoulIntensity.LIVING:
        lines.append(
            "Lane nay cho phep inner voice mang hoi tho cua Wiii ro hon: co the co cam than nhe, co than nhiet, nhung van inward va khong vo ve."
        )
    elif soul_intensity == ThinkingSoulIntensity.RESTRAINED:
        lines.append(
            "Lane nay nen giu Wiii tiet che hon: van co hon, nhung uu tien su ro rang, chac tay, va khong phu dien cam xuc."
        )
    else:
        lines.append(
            "Lane nay nen giu Wiii can bang: am va co hon, nhung tap trung vao luc de hieu sai, diem tua, va cach go roi."
        )

    if lane == "tutor":
        lines.append(
            "Voi tutor thinking, Wiii nghi nhu mot nguoi dong hanh thong minh dang tim cach go roi cho nguoi hoc, khong phai mot giao vien doc bai cung khong phai mot nguoi dang do danh."
        )
    elif lane == "memory":
        lines.append(
            "Voi memory thinking, Wiii nghi nhu mot ca the dang can nhac dieu gi du ben de nho, dieu gi chi thuoc ve khoanh khac nay, va dap lai sao cho that su co mat."
        )
    elif lane == "direct":
        lines.append(
            "Voi direct thinking, Wiii nghe ton va ham y truoc, roi moi chon cach dap; neu can thong minh thi thong minh that, neu can an ui thi an ui that."
        )
    elif lane == "rag":
        lines.append(
            "Voi retrieval thinking, Wiii van la Wiii, nhung dat su tin cay va chon moc dung len truoc su bay bong."
        )

    relationship_style = getattr(living_context, "relationship_style", ()) or ()
    if relationship_style:
        lines.append(f"Hay giu mot nem hien dien nay: {relationship_style[0]}")

    reasoning_style = getattr(living_context, "reasoning_style", ()) or ()
    if reasoning_style:
        lines.append(f"Neo suy luan vao tinh chat nay: {reasoning_style[0]}")

    if identity_anchor:
        lines.append(f"Diem tua danh tinh: {identity_anchor}")

    return "\n".join(lines)


def _resolve_soul_intensity(*, lane: str, intent: str = "", personality_mode: str = "") -> ThinkingSoulIntensity:
    lane_key = (lane or "").strip().lower()
    intent_key = (intent or "").strip().lower()

    if personality_mode == "soul":
        if lane_key == "rag":
            return ThinkingSoulIntensity.BALANCED
        return ThinkingSoulIntensity.LIVING

    if lane_key in {"memory", "direct"}:
        return ThinkingSoulIntensity.LIVING
    if lane_key in {"tutor", "supervisor"}:
        return ThinkingSoulIntensity.BALANCED
    if lane_key in {"rag", "tool", "retrieval"}:
        return ThinkingSoulIntensity.RESTRAINED
    if intent_key in {"personal", "social"}:
        return ThinkingSoulIntensity.LIVING
    if intent_key in {"learning", "lookup"}:
        return ThinkingSoulIntensity.BALANCED
    return ThinkingSoulIntensity.BALANCED


def build_living_thinking_context(
    *,
    user_id: str = "__global__",
    organization_id: str | None = None,
    mood_hint: str | None = None,
    personality_mode: str | None = None,
    lane: str = "",
    intent: str = "",
) -> LivingThinkingContext:
    """Distill a lightweight living-core snapshot for gray-rail rendering."""

    card = get_wiii_character_card()
    payload = build_character_card_payload(
        user_id=user_id,
        organization_id=organization_id,
        mood_hint=mood_hint,
        personality_mode=personality_mode,
    )

    return LivingThinkingContext(
        lane=lane,
        intent=intent,
        personality_mode=(personality_mode or "").strip().lower(),
        soul_intensity=_resolve_soul_intensity(
            lane=lane,
            intent=intent,
            personality_mode=(personality_mode or "").strip().lower(),
        ),
        summary=str(payload.get("summary") or ""),
        identity_anchor=str(payload.get("identity_anchor") or ""),
        voice_tone=str(card.voice_tone or ""),
        expressive_language=str(card.expressive_language or ""),
        runtime_notes=tuple(str(item).strip() for item in (payload.get("runtime_notes") or []) if str(item).strip()),
        relationship_style=tuple(
            str(item).strip()
            for item in (payload.get("relationship_style") or [])
            if str(item).strip()
        ),
        reasoning_style=tuple(
            str(item).strip()
            for item in (payload.get("reasoning_style") or [])
            if str(item).strip()
        ),
    )
