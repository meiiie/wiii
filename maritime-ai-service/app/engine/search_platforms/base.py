"""
Search Platform Adapter — Abstract Base Class + Data Models

Sprint 149: "Cắm & Chạy" — Plugin Architecture for Product Search

Pattern: Inspired by app/domains/ plugin system (DomainPlugin ABC + DomainLoader).
Each platform implements SearchPlatformAdapter to normalize search results.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """Backend technology used by a platform adapter."""
    SERPER = "serper"                # Serper.dev Google Shopping endpoint
    SERPER_SITE = "serper_site"      # Serper.dev with site: filter
    NATIVE_API = "native_api"        # Official platform API (e.g. TikTok Research)
    APIFY = "apify"                  # Apify scraping actors
    CUSTOM = "custom"                # Custom implementation
    BROWSER = "browser"              # Playwright headless browser + LLM extraction


@dataclass
class PlatformConfig:
    """Configuration for a search platform adapter."""
    id: str                                     # e.g. "google_shopping", "shopee"
    display_name: str                           # e.g. "Google Shopping", "Shopee"
    backend: BackendType
    fallback_backend: Optional[BackendType] = None
    site_filter: Optional[str] = None           # e.g. "site:shopee.vn"
    requires_auth: bool = False
    enabled: bool = True
    tool_description_vi: str = ""               # Vietnamese tool docstring
    max_results_default: int = 20


@dataclass
class ProductSearchResult:
    """Normalized search result from any platform."""
    platform: str
    title: str
    price: str = ""
    extracted_price: Optional[float] = None
    link: str = ""
    seller: str = ""
    rating: Optional[float] = None
    sold_count: Optional[int] = None
    reviews: Optional[int] = None
    image: str = ""
    snippet: str = ""
    source: str = ""
    delivery: str = ""
    location: str = ""

    def to_dict(self) -> dict:
        """Convert to dict, omitting None/empty values for compact JSON."""
        d = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "" and v != 0:
                d[k] = v
            elif k in ("platform", "title"):
                d[k] = v
        return d


class SearchPlatformAdapter(ABC):
    """
    Abstract base class for search platform adapters.

    Subclasses must implement:
    - get_config() → PlatformConfig
    - search_sync(query, max_results) → List[ProductSearchResult]
    """

    @abstractmethod
    def get_config(self) -> PlatformConfig:
        """Return platform configuration."""
        ...

    @abstractmethod
    def search_sync(self, query: str, max_results: int = 20, page: int = 1) -> List[ProductSearchResult]:
        """Execute synchronous search and return normalized results.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            page: Page number (1-based). Not all backends support pagination.
        """
        ...

    def get_tool_name(self) -> str:
        """LangChain tool name — auto-derived from platform ID."""
        return f"tool_search_{self.get_config().id}"

    def get_tool_description(self) -> str:
        """Tool description for LLM function calling."""
        config = self.get_config()
        if config.tool_description_vi:
            return config.tool_description_vi
        return f"Search {config.display_name} for products."

    def validate_credentials(self) -> bool:
        """Check if required credentials are available. Override for auth platforms."""
        return True
