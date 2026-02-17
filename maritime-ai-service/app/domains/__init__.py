"""
Domain Plugin System - Wiii.

Provides plugin infrastructure for multi-domain AI tutoring.
Each domain is a self-contained package with config, prompts, skills, and tools.

Architecture:
    app/domains/
    +-- base.py          # DomainPlugin ABC, DomainConfig, SkillManifest
    +-- registry.py      # DomainRegistry singleton
    +-- loader.py        # Auto-discovery from domains/*/domain.yaml
    +-- router.py        # Query -> domain_id resolution
    +-- maritime/        # First domain plugin
    +-- _template/       # Skeleton for new domains
"""

from app.domains.base import DomainPlugin, DomainConfig, SkillManifest
from app.domains.registry import DomainRegistry, get_domain_registry
from app.domains.loader import DomainLoader
from app.domains.router import DomainRouter, get_domain_router

__all__ = [
    "DomainPlugin",
    "DomainConfig",
    "SkillManifest",
    "DomainRegistry",
    "get_domain_registry",
    "DomainLoader",
    "DomainRouter",
    "get_domain_router",
]
