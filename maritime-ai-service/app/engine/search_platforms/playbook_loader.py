"""Site Playbook Loader — discovers and loads per-platform YAML configs.

Pattern inspired by Firecrawl Web Agent's site playbooks:
externalize scraping config (URLs, selectors, strategies) into YAML
so new platforms can be added without code changes.

Feature-gated by settings.enable_site_playbooks (default: False).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_PLAYBOOKS_DIR = Path(__file__).parent / "playbooks"


# ---------------------------------------------------------------------------
# Data models for playbook config
# ---------------------------------------------------------------------------


@dataclass
class PlaybookSiteConfig:
    """URL and pagination config for a platform."""
    base_url: str = ""
    url_template: str = ""
    query_encoding: str = "percent"  # "plus" | "percent" | "raw"
    pagination: str = "query_param"  # "query_param" | "path" | "scroll" | "none"


@dataclass
class PlaybookRequestConfig:
    """HTTP request config."""
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    follow_redirects: bool = True


@dataclass
class PlaybookExtractionConfig:
    """Content extraction config — CSS selectors or API paths."""
    type: str = "html_css"  # "html_css" | "llm" | "graphql_intercept" | "api_json" | "hybrid"
    selectors: Dict[str, str] = field(default_factory=dict)
    fallback_selectors: Dict[str, List[str]] = field(default_factory=dict)
    field_mapping: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlaybookStrategyConfig:
    """Backend selection and fallback strategy."""
    preferred_backend: str = ""
    reason: str = ""
    fallback_chain: List[str] = field(default_factory=list)


@dataclass
class SitePlaybook:
    """Complete playbook for a single platform."""
    platform_id: str
    display_name: str
    backend: str
    enabled: bool = True
    priority: int = 0
    site: PlaybookSiteConfig = field(default_factory=PlaybookSiteConfig)
    request: PlaybookRequestConfig = field(default_factory=PlaybookRequestConfig)
    extraction: PlaybookExtractionConfig = field(default_factory=PlaybookExtractionConfig)
    strategy: PlaybookStrategyConfig = field(default_factory=PlaybookStrategyConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class PlaybookLoader:
    """Discovers and loads site playbooks from YAML files.

    Lazy-loads on first access. Supports hot-reload for development.
    """

    def __init__(self, playbooks_dir: Optional[Path] = None):
        self._playbooks_dir = playbooks_dir or _DEFAULT_PLAYBOOKS_DIR
        self._cache: Dict[str, SitePlaybook] = {}
        self._loaded: bool = False

    def _ensure_loaded(self) -> None:
        """Lazy-load all .playbook.yaml files on first access."""
        if self._loaded:
            return
        self._loaded = True
        if not self._playbooks_dir.exists():
            logger.debug("[PLAYBOOK] Directory not found: %s", self._playbooks_dir)
            return
        for yaml_file in self._playbooks_dir.rglob("*.playbook.yaml"):
            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not raw or not isinstance(raw, dict):
                    continue
                playbook = self._parse_playbook(raw)
                self._cache[playbook.platform_id] = playbook
                logger.debug("[PLAYBOOK] Loaded: %s (%s)", playbook.platform_id, yaml_file.name)
            except Exception as e:
                logger.warning("[PLAYBOOK] Failed to load %s: %s", yaml_file.name, e)
        logger.info("[PLAYBOOK] Loaded %d playbooks from %s", len(self._cache), self._playbooks_dir)

    def _parse_playbook(self, raw: Dict[str, Any]) -> SitePlaybook:
        """Parse a raw YAML dict into a SitePlaybook."""
        site_raw = raw.get("site", {})
        request_raw = raw.get("request", {})
        extraction_raw = raw.get("extraction", {})
        strategy_raw = raw.get("strategy", {})

        return SitePlaybook(
            platform_id=raw.get("platform_id", ""),
            display_name=raw.get("display_name", ""),
            backend=raw.get("backend", "custom"),
            enabled=raw.get("enabled", True),
            priority=raw.get("priority", 0),
            site=PlaybookSiteConfig(
                base_url=site_raw.get("base_url", ""),
                url_template=site_raw.get("url_template", ""),
                query_encoding=site_raw.get("query_encoding", "percent"),
                pagination=site_raw.get("pagination", "query_param"),
            ),
            request=PlaybookRequestConfig(
                method=request_raw.get("method", "GET"),
                headers=request_raw.get("headers", {}),
                timeout_seconds=request_raw.get("timeout_seconds", 30),
                follow_redirects=request_raw.get("follow_redirects", True),
            ),
            extraction=PlaybookExtractionConfig(
                type=extraction_raw.get("type", "html_css"),
                selectors=extraction_raw.get("selectors", {}),
                fallback_selectors=extraction_raw.get("fallback_selectors", {}),
                field_mapping=extraction_raw.get("field_mapping", {}),
            ),
            strategy=PlaybookStrategyConfig(
                preferred_backend=strategy_raw.get("preferred_backend", ""),
                reason=strategy_raw.get("reason", ""),
                fallback_chain=strategy_raw.get("fallback_chain", []),
            ),
        )

    def get(self, platform_id: str) -> Optional[SitePlaybook]:
        """Get playbook by platform ID."""
        self._ensure_loaded()
        return self._cache.get(platform_id)

    def get_all(self) -> List[SitePlaybook]:
        """Get all loaded playbooks."""
        self._ensure_loaded()
        return list(self._cache.values())

    def get_for_domain(self, domain: str) -> Optional[SitePlaybook]:
        """Look up playbook by matching domain against base_url patterns."""
        self._ensure_loaded()
        domain_lower = domain.lower()
        for pb in self._cache.values():
            if domain_lower in pb.site.base_url.lower():
                return pb
        return None

    def reload(self) -> int:
        """Force reload all playbooks (for hot-reload in dev)."""
        self._cache.clear()
        self._loaded = False
        self._ensure_loaded()
        return len(self._cache)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_LOADER: Optional[PlaybookLoader] = None


def get_playbook_loader() -> PlaybookLoader:
    """Get or create the PlaybookLoader singleton."""
    global _LOADER
    if _LOADER is None:
        _LOADER = PlaybookLoader()
    return _LOADER
