"""
Domain Registry - Central registry for domain plugins.

Singleton pattern for global access to registered domains.
"""

import logging
from typing import Dict, List, Optional

from app.core.singleton import singleton_factory
from app.domains.base import DomainPlugin

logger = logging.getLogger(__name__)


class DomainRegistry:
    """
    Central registry for domain plugins.

    Manages domain plugin lifecycle:
    - Registration at startup
    - Lookup by domain_id
    - Default domain resolution
    """

    def __init__(self):
        self._domains: Dict[str, DomainPlugin] = {}
        self._default_domain_id: Optional[str] = None
        logger.info("DomainRegistry initialized")

    def register(self, domain: DomainPlugin) -> None:
        """
        Register a domain plugin.

        Args:
            domain: DomainPlugin instance to register
        """
        config = domain.get_config()
        domain_id = config.id
        self._domains[domain_id] = domain

        # First registered domain becomes default unless overridden
        if self._default_domain_id is None:
            self._default_domain_id = domain_id

        logger.info("Registered domain: %s (%s)", domain_id, config.name)

    def set_default(self, domain_id: str) -> None:
        """Set the default domain ID."""
        if domain_id in self._domains:
            self._default_domain_id = domain_id
            logger.info("Default domain set to: %s", domain_id)
        else:
            logger.warning("Cannot set default: domain '%s' not registered", domain_id)

    def get(self, domain_id: str) -> Optional[DomainPlugin]:
        """
        Get a domain plugin by ID.

        Args:
            domain_id: Domain identifier

        Returns:
            DomainPlugin or None if not found
        """
        return self._domains.get(domain_id)

    def get_default(self) -> Optional[DomainPlugin]:
        """Get the default domain plugin."""
        if self._default_domain_id:
            return self._domains.get(self._default_domain_id)
        return None

    def get_default_id(self) -> Optional[str]:
        """Get the default domain ID."""
        return self._default_domain_id

    def list_all(self) -> Dict[str, DomainPlugin]:
        """List all registered domains."""
        return dict(self._domains)

    def get_all_keywords(self) -> Dict[str, List[str]]:
        """
        Get routing keywords for all registered domains.

        Returns:
            Dict mapping domain_id -> list of keywords
        """
        result = {}
        for domain_id, domain in self._domains.items():
            config = domain.get_config()
            result[domain_id] = config.routing_keywords
        return result

    def is_registered(self, domain_id: str) -> bool:
        """Check if a domain is registered."""
        return domain_id in self._domains

    @property
    def count(self) -> int:
        """Number of registered domains."""
        return len(self._domains)


get_domain_registry = singleton_factory(DomainRegistry)
