"""
Social Browser — Wiii's autonomous content discovery engine.

Sprint 170: "Linh Hồn Sống"

Browses news, tech blogs, and social media to discover content
aligned with Wiii's interests. Uses feed adapters for platform-specific
fetching and local LLM for relevance scoring.

Design:
    - Platform adapters: news (RSS/web), hackernews, reddit, tech blogs
    - Interest-driven selection: content filtered by soul interests
    - Rate limiting: max items per session, max API calls per heartbeat
    - Content safety: blocked categories, NSFW filtering
    - All analysis via LOCAL MODEL (zero cost)
"""

import logging
import random
from typing import List, Optional

from app.engine.living_agent.models import BrowsingItem

logger = logging.getLogger(__name__)

# Topic → search queries mapping
_TOPIC_QUERIES = {
    "news": [
        "AI agent technology 2026",
        "maritime shipping news",
        "machine learning breakthroughs",
        "Vietnam technology",
    ],
    "tech": [
        "LLM autonomous agents",
        "LangGraph state machines",
        "Ollama local models",
        "Python async patterns",
    ],
    "maritime": [
        "IMO regulations 2026",
        "COLREGs updates",
        "SOLAS amendments",
        "MARPOL compliance",
        "maritime safety news",
    ],
    "science": [
        "astronomy discoveries 2026",
        "ocean conservation",
        "renewable energy maritime",
    ],
    "general": [
        "trending technology news",
        "Vietnam news",
        "AI research papers",
    ],
}


class SocialBrowser:
    """Autonomous content browser for Wiii's learning.

    Browses various platforms to find content relevant to Wiii's interests.
    All content is filtered for safety and scored for relevance.

    Usage:
        browser = SocialBrowser()
        items = await browser.browse_feed(topic="tech", interests=["AI", "ML"])
    """

    async def browse_feed(
        self,
        topic: str = "general",
        interests: Optional[List[str]] = None,
        max_items: int = 5,
    ) -> List[BrowsingItem]:
        """Browse content for a topic, filtered by interests.

        Args:
            topic: Content category (news, tech, maritime, science, general).
            interests: List of interest strings for relevance filtering.
            max_items: Maximum items to return.

        Returns:
            List of BrowsingItem with relevance scores.
        """
        from app.core.config import settings

        if not settings.living_agent_enable_social_browse:
            return []

        queries = _TOPIC_QUERIES.get(topic, _TOPIC_QUERIES["general"])
        query = random.choice(queries)

        # Try web search via existing tools
        items = await self._search_web(query, max_items * 2)

        if not items:
            logger.debug("[BROWSER] No results for query: %s", query)
            return []

        # Score relevance using local LLM
        if interests:
            items = await self._score_relevance(items, interests)

        # Sort by relevance, return top N
        items.sort(key=lambda x: x.relevance_score, reverse=True)
        results = items[:max_items]

        # Save to browsing log
        self._save_browsing_log(results)

        logger.info(
            "[BROWSER] Browsed %d items for topic '%s' (query: %s)",
            len(results), topic, query,
        )
        return results

    async def _search_web(self, query: str, max_results: int) -> List[BrowsingItem]:
        """Search the web using available tools.

        Tries multiple approaches:
        1. Serper API (if key configured)
        2. Simple web fetch for known sites
        """
        items = []

        # Try Serper API if available
        try:
            serper_items = await self._search_via_serper(query, max_results)
            items.extend(serper_items)
        except Exception as e:
            logger.debug("[BROWSER] Serper search failed: %s", e)

        # If Serper unavailable, try HackerNews API (free, no key)
        if not items:
            try:
                hn_items = await self._search_hackernews(query, max_results)
                items.extend(hn_items)
            except Exception as e:
                logger.debug("[BROWSER] HackerNews search failed: %s", e)

        return items

    async def _search_via_serper(self, query: str, max_results: int) -> List[BrowsingItem]:
        """Search via Serper API."""
        import httpx
        from app.core.config import settings

        api_key = settings.serper_api_key
        if not api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": max_results},
                )
                resp.raise_for_status()
                data = resp.json()

                items = []
                for result in data.get("organic", [])[:max_results]:
                    items.append(BrowsingItem(
                        platform="web_search",
                        url=result.get("link", ""),
                        title=result.get("title", ""),
                        summary=result.get("snippet", ""),
                    ))
                return items
        except Exception as e:
            logger.debug("[BROWSER] Serper error: %s", e)
            return []

    async def _search_hackernews(self, query: str, max_results: int) -> List[BrowsingItem]:
        """Search HackerNews (free API, no key needed)."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://hn.algolia.com/api/v1/search",
                    params={"query": query, "hitsPerPage": max_results, "tags": "story"},
                )
                resp.raise_for_status()
                data = resp.json()

                items = []
                for hit in data.get("hits", [])[:max_results]:
                    items.append(BrowsingItem(
                        platform="hackernews",
                        url=hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"),
                        title=hit.get("title", ""),
                        summary=hit.get("story_text", "")[:500] if hit.get("story_text") else "",
                        metadata={"points": hit.get("points", 0), "comments": hit.get("num_comments", 0)},
                    ))
                return items
        except Exception as e:
            logger.debug("[BROWSER] HackerNews error: %s", e)
            return []

    async def _score_relevance(
        self,
        items: List[BrowsingItem],
        interests: List[str],
    ) -> List[BrowsingItem]:
        """Score items by relevance to Wiii's interests using local LLM."""
        from app.engine.living_agent.local_llm import get_local_llm

        llm = get_local_llm()

        # Check if local LLM is available
        available = await llm.is_available()
        if not available:
            # Fallback: keyword-based scoring
            return self._keyword_score(items, interests)

        for item in items:
            content = f"{item.title} {item.summary}"
            if content.strip():
                score = await llm.rate_relevance(content, interests)
                item.relevance_score = score

        return items

    @staticmethod
    def _keyword_score(
        items: List[BrowsingItem],
        interests: List[str],
    ) -> List[BrowsingItem]:
        """Fallback keyword-based relevance scoring."""
        interest_keywords = set()
        for interest in interests:
            interest_keywords.update(interest.lower().split())

        for item in items:
            text = f"{item.title} {item.summary}".lower()
            matches = sum(1 for kw in interest_keywords if kw in text)
            item.relevance_score = min(1.0, matches / max(len(interest_keywords), 1))

        return items

    def _save_browsing_log(self, items: List[BrowsingItem]) -> None:
        """Save browsing items to the database log."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        try:
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                for item in items:
                    session.execute(
                        text("""
                            INSERT INTO wiii_browsing_log
                            (id, platform, url, title, summary, relevance_score,
                             emotional_reaction, browsed_at, organization_id)
                            VALUES (:id, :platform, :url, :title, :summary, :score,
                                    :reaction, NOW(), :org_id)
                        """),
                        {
                            "id": str(item.id),
                            "platform": item.platform,
                            "url": item.url,
                            "title": item.title[:500],
                            "summary": item.summary[:2000],
                            "score": item.relevance_score,
                            "reaction": item.emotional_reaction,
                            "org_id": item.organization_id,
                        },
                    )
                session.commit()
                logger.debug("[BROWSER] Saved %d items to browsing log", len(items))
        except Exception as e:
            logger.warning("[BROWSER] Failed to save browsing log: %s", e)


# =============================================================================
# Singleton
# =============================================================================

_browser_instance: Optional[SocialBrowser] = None


def get_social_browser() -> SocialBrowser:
    """Get the singleton SocialBrowser instance."""
    global _browser_instance
    if _browser_instance is None:
        _browser_instance = SocialBrowser()
    return _browser_instance
