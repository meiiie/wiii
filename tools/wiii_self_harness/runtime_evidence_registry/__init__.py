"""Load, validate, and report on Wiii runtime evidence obligations."""

from .constants import (
    DEFAULT_REGISTRY,
    REGISTRY_NAME,
    REGISTRY_VALIDATION_SCHEMA_VERSION,
    REPO_ROOT,
)
from .report import RegistryResult, format_summary, normalize_registry_error_code
from .validator import load_registry, validate_registry

__all__ = (
    "DEFAULT_REGISTRY",
    "REGISTRY_NAME",
    "REGISTRY_VALIDATION_SCHEMA_VERSION",
    "REPO_ROOT",
    "RegistryResult",
    "format_summary",
    "load_registry",
    "normalize_registry_error_code",
    "validate_registry",
)
