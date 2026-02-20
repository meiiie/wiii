"""LMS Integration — Sprint 155: "Cầu Nối". Feature-gated: enable_lms_integration=False."""


def is_lms_enabled() -> bool:
    """Check if LMS integration is enabled in config."""
    from app.core.config import get_settings
    return getattr(get_settings(), "enable_lms_integration", False)
