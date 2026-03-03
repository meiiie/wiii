"""
Sprint 224: Magic Link Email Service — Resend wrapper.

Sends magic link emails using Resend API.
"""
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import resend
except ImportError:
    resend = None  # type: ignore


MAGIC_LINK_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; color: #1a1a1a;">
  <div style="text-align: center; margin-bottom: 32px;">
    <h1 style="font-size: 24px; font-weight: 600; margin: 0;">Đăng nhập Wiii</h1>
  </div>
  <p style="font-size: 16px; line-height: 1.6;">Xin chào,</p>
  <p style="font-size: 16px; line-height: 1.6;">Click nút bên dưới để đăng nhập vào Wiii. Link có hiệu lực trong <strong>10 phút</strong>.</p>
  <div style="text-align: center; margin: 32px 0;">
    <a href="{url}" style="display: inline-block; padding: 14px 32px; background-color: #E8713A; color: white; text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: 600;">
      Đăng nhập Wiii
    </a>
  </div>
  <p style="font-size: 14px; color: #666; line-height: 1.5;">Nếu bạn không yêu cầu đăng nhập, hãy bỏ qua email này.</p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 32px 0;">
  <p style="font-size: 12px; color: #999; text-align: center;">by The Wiii Lab</p>
</body>
</html>
"""


def build_magic_link_html(verify_url: str) -> str:
    """Build HTML email body with magic link button."""
    return MAGIC_LINK_HTML_TEMPLATE.format(url=verify_url)


async def send_magic_link_email(to_email: str, verify_url: str) -> bool:
    """Send magic link email via Resend.

    Returns True if sent successfully, False on error.
    """
    if resend is None:
        logger.error("resend package not installed — cannot send magic link email")
        return False

    try:
        resend.api_key = settings.resend_api_key
        html = build_magic_link_html(verify_url)
        resend.Emails.send({
            "from": settings.magic_link_from_email,
            "to": to_email,
            "subject": "Đăng nhập Wiii",
            "html": html,
        })
        logger.info("Magic link email sent to %s", to_email)
        return True
    except Exception as e:
        logger.error("Failed to send magic link email to %s: %s", to_email, e)
        return False
