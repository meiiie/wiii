"""Generic Host Adapter — fallback for unknown host types.

Sprint 222: Universal Context Engine.
Used when no specialized adapter is registered for the host_type.
Produces a simple XML block preserving whatever context the host sent.
"""
from app.engine.context.adapters.base import HostAdapter
from app.engine.context.host_context import HostContext


class GenericHostAdapter(HostAdapter):
    """Fallback adapter for any host type without a dedicated adapter."""

    host_type = "generic"

    def format_context_for_prompt(self, ctx: HostContext) -> str:
        page = ctx.page
        page_type = page.get("type", "unknown")
        page_title = page.get("title", "")

        parts: list[str] = [
            f'<host_context type="{ctx.host_type}" page_type="{page_type}">'
        ]
        parts.append(f"  <page>{page_type} — {page_title}</page>")

        # Content snippet
        if ctx.content and ctx.content.get("snippet"):
            parts.append(f'  <content>{ctx.content["snippet"]}</content>')

        # User state — dump all key=value pairs
        if ctx.user_state:
            items = [
                f"{k}={v}"
                for k, v in ctx.user_state.items()
                if v is not None
            ]
            if items:
                parts.append(f"  <user_state>{'; '.join(items)}</user_state>")

        # Available actions
        if ctx.available_actions:
            labels = [
                a.get("label", a.get("action", ""))
                for a in ctx.available_actions
            ]
            labels = [lb for lb in labels if lb]
            if labels:
                parts.append(
                    f"  <available_actions>{', '.join(labels)}</available_actions>"
                )

        parts.append(
            "  <instruction>Liên hệ nội dung trang khi trả lời.</instruction>"
        )
        parts.append("</host_context>")
        return "\n".join(parts)
