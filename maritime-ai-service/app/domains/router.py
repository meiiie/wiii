"""
Domain Router - Resolves which domain a query belongs to.

Resolution order:
1. Explicit domain_id in request -> use it
2. Session sticky domain -> use it
3. Keyword match across all domains -> use best match
4. Default domain from config
"""

import logging
import unicodedata
from typing import Optional

from app.core.singleton import singleton_factory
from app.domains.registry import get_domain_registry

logger = logging.getLogger(__name__)


class DomainRouter:
    """
    Routes queries to the appropriate domain.

    Fast O(n) keyword matching across all registered domains.
    """

    async def resolve(
        self,
        query: str,
        explicit_domain_id: Optional[str] = None,
        session_domain: Optional[str] = None,
        allowed_domains: Optional[list[str]] = None,
    ) -> str:
        """
        Resolve the domain_id for a query.

        Priority:
        1. Explicit domain_id (from request body or header)
        2. Session sticky domain (same domain within a session)
        3. Keyword match across all registered domains
        4. Default domain

        Sprint 24: If allowed_domains is provided (multi-tenant), the resolved
        domain must be in the list. If not, falls back to org default or global
        default.

        Args:
            query: User query text
            explicit_domain_id: Domain ID from request (if provided)
            session_domain: Domain ID from current session (if any)
            allowed_domains: Org-scoped allowed domains (None = no filtering)

        Returns:
            Resolved domain_id string
        """
        registry = get_domain_registry()

        def _is_allowed(domain_id: str) -> bool:
            """Check if domain is in org-scoped allowed list."""
            if allowed_domains is None:
                return True  # No filtering
            return domain_id in allowed_domains

        # 1. Explicit domain_id
        if explicit_domain_id and registry.is_registered(explicit_domain_id):
            if _is_allowed(explicit_domain_id):
                logger.debug("Domain resolved (explicit): %s", explicit_domain_id)
                return explicit_domain_id
            else:
                logger.warning(
                    "Domain '%s' not in allowed_domains "
                    "%s, falling through",
                    explicit_domain_id, allowed_domains,
                )

        # 2. Session sticky
        if session_domain and registry.is_registered(session_domain):
            if _is_allowed(session_domain):
                logger.debug("Domain resolved (session): %s", session_domain)
                return session_domain

        # 3. Keyword match
        matched = self._keyword_match(query)
        if matched and _is_allowed(matched):
            logger.debug("Domain resolved (keyword): %s", matched)
            return matched

        # 4. Default
        default_id = registry.get_default_id()
        if default_id and _is_allowed(default_id):
            logger.debug("Domain resolved (default): %s", default_id)
            return default_id

        # 5. First allowed domain (org fallback)
        if allowed_domains:
            for ad in allowed_domains:
                if registry.is_registered(ad):
                    logger.debug("Domain resolved (org fallback): %s", ad)
                    return ad

        # Absolute fallback
        from app.core.config import settings
        fallback = settings.default_domain
        logger.warning("No domain resolved, using '%s' as fallback", fallback)
        return fallback

    @staticmethod
    def _strip_diacritics(text: str) -> str:
        """Strip Vietnamese diacritics for fuzzy keyword matching.

        Handles common Vietnamese chars: à→a, ắ→a, ơ→o, ư→u, đ→d, etc.
        """
        # Special-case đ/Đ which NFD doesn't decompose
        text = text.replace("đ", "d").replace("Đ", "D")
        # Decompose then strip combining marks
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def _keyword_match(self, query: str) -> Optional[str]:
        """
        Match query against all domain routing keywords.

        Matches both with and without Vietnamese diacritics so
        "bien bao" matches keyword "biển báo".

        Returns domain_id with the most keyword matches, or None.
        """
        registry = get_domain_registry()
        all_keywords = registry.get_all_keywords()

        if not all_keywords:
            return None

        query_lower = query.lower()
        query_stripped = self._strip_diacritics(query_lower)
        best_domain = None
        best_score = 0

        for domain_id, keywords in all_keywords.items():
            score = 0
            for keyword in keywords:
                # Keywords can be comma-separated alternatives
                alternatives = [k.strip().lower() for k in keyword.split(",")]
                for alt in alternatives:
                    alt_stripped = self._strip_diacritics(alt)
                    if alt in query_lower or alt_stripped in query_stripped:
                        score += 1
            if score > best_score:
                best_score = score
                best_domain = domain_id

        return best_domain if best_score > 0 else None


get_domain_router = singleton_factory(DomainRouter)
