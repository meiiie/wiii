"""
Sprint 195: BM25 Skill Search — Fast Keyword-Based Skill Discovery

Provides BM25 (Best Matching 25) ranking over skill catalog for efficient
tool discovery at scale. Pre-filter before expensive semantic/LLM ranking.

Architecture:
  - In-memory inverted index built from skill names, descriptions, triggers
  - BM25 scoring with tunable k1 (term frequency saturation) and b (length normalization)
  - Vietnamese-aware tokenization (splits on whitespace + common Vietnamese particles)
  - Thread-safe, rebuilds index on skill catalog refresh

Integration:
  - Called by IntelligentToolSelector as Step 0 (before category filter)
  - Also available standalone via get_skill_search().search(query)

Performance:
  - Index build: O(n) where n = skill count
  - Query: O(q * d) where q = query terms, d = avg docs per term
  - Target: <5ms for 100+ skills, <20ms for 500+ skills
"""

import logging
import math
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Module-level singleton
_search_instance: Optional["SkillSearch"] = None
_search_lock = threading.Lock()

# BM25 parameters
_DEFAULT_K1 = 1.5    # Term frequency saturation (1.2-2.0 typical)
_DEFAULT_B = 0.75    # Length normalization (0.75 standard)

# Vietnamese stop words (common particles that don't carry search intent)
_VIETNAMESE_STOP_WORDS: Set[str] = {
    "là", "và", "của", "có", "được", "cho", "trong", "với", "một",
    "không", "này", "đã", "các", "từ", "về", "theo", "để", "khi",
    "thì", "tại", "bởi", "cũng", "như", "đó", "hay", "hoặc", "nếu",
    "sẽ", "đang", "vào", "ra", "lên", "bị", "nên", "mà", "rồi",
    "trên", "dưới", "qua", "lại", "đi", "do", "vì", "thế", "còn",
    # English stop words
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "and", "or", "not", "this", "that", "it", "as", "if", "but",
}


def get_skill_search() -> "SkillSearch":
    """Get or create the singleton SkillSearch."""
    global _search_instance
    if _search_instance is None:
        with _search_lock:
            if _search_instance is None:
                _search_instance = SkillSearch()
    return _search_instance


@dataclass
class SearchResult:
    """A single BM25 search result."""
    skill_id: str
    score: float
    matched_terms: List[str] = field(default_factory=list)


@dataclass
class _DocEntry:
    """Internal: indexed document for a skill."""
    skill_id: str
    tokens: List[str]
    token_freq: Dict[str, int] = field(default_factory=dict)
    length: int = 0


class SkillSearch:
    """
    BM25-based skill search engine.

    Builds an inverted index from skill metadata (name, description, triggers,
    category) and provides fast ranked search.

    Usage:
        search = get_skill_search()
        search.build_index(skills)  # From UnifiedSkillIndex.get_all()
        results = search.search("tìm sản phẩm shopee", limit=10)
    """

    def __init__(self, k1: float = _DEFAULT_K1, b: float = _DEFAULT_B):
        self._k1 = k1
        self._b = b
        self._lock = threading.Lock()

        # Index state
        self._docs: Dict[str, _DocEntry] = {}
        self._inverted_index: Dict[str, Set[str]] = defaultdict(set)  # term → skill_ids
        self._doc_count: int = 0
        self._avg_doc_length: float = 0.0
        self._idf_cache: Dict[str, float] = {}
        self._indexed: bool = False

    def build_index(self, skills: list) -> int:
        """
        Build the BM25 inverted index from skill manifests.

        Args:
            skills: List of UnifiedSkillManifest (or any object with
                    id, name, description, triggers, category attributes)

        Returns:
            Number of skills indexed.
        """
        with self._lock:
            self._docs.clear()
            self._inverted_index.clear()
            self._idf_cache.clear()

            total_length = 0

            for skill in skills:
                skill_id = getattr(skill, 'id', str(skill))

                # Build searchable text from all relevant fields
                text_parts = [
                    getattr(skill, 'name', '') or '',
                    getattr(skill, 'description', '') or '',
                    getattr(skill, 'description_short', '') or '',
                    ' '.join(getattr(skill, 'triggers', []) or []),
                    getattr(skill, 'category', '') or '',
                    getattr(skill, 'domain_id', '') or '',
                ]
                full_text = ' '.join(text_parts)
                tokens = self._tokenize(full_text)

                if not tokens:
                    continue

                # Build term frequency map
                tf: Dict[str, int] = defaultdict(int)
                for token in tokens:
                    tf[token] += 1

                doc = _DocEntry(
                    skill_id=skill_id,
                    tokens=tokens,
                    token_freq=dict(tf),
                    length=len(tokens),
                )
                self._docs[skill_id] = doc
                total_length += doc.length

                # Build inverted index
                for token in set(tokens):
                    self._inverted_index[token].add(skill_id)

            self._doc_count = len(self._docs)
            self._avg_doc_length = (
                total_length / self._doc_count if self._doc_count > 0 else 1.0
            )

            # Pre-compute IDF for all terms
            for term, doc_ids in self._inverted_index.items():
                df = len(doc_ids)
                # IDF with smoothing: log((N - df + 0.5) / (df + 0.5) + 1)
                self._idf_cache[term] = math.log(
                    (self._doc_count - df + 0.5) / (df + 0.5) + 1.0
                )

            self._indexed = True

        logger.info(
            "BM25 skill index built: %d skills, %d unique terms, avg_length=%.1f",
            self._doc_count, len(self._inverted_index), self._avg_doc_length,
        )
        return self._doc_count

    def search(
        self,
        query: str,
        limit: int = 20,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """
        Search skills using BM25 ranking.

        Args:
            query: Search query string
            limit: Maximum results to return
            min_score: Minimum BM25 score threshold

        Returns:
            List of SearchResult, sorted by score descending.
        """
        if not self._indexed or not query or not query.strip():
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Score each candidate document
        scores: Dict[str, float] = defaultdict(float)
        matched_terms: Dict[str, List[str]] = defaultdict(list)

        for term in query_tokens:
            if term not in self._inverted_index:
                continue

            idf = self._idf_cache.get(term, 0.0)
            if idf <= 0:
                continue

            for skill_id in self._inverted_index[term]:
                doc = self._docs[skill_id]
                tf = doc.token_freq.get(term, 0)

                # BM25 formula
                numerator = tf * (self._k1 + 1)
                denominator = tf + self._k1 * (
                    1 - self._b + self._b * (doc.length / self._avg_doc_length)
                )
                score = idf * (numerator / denominator)

                scores[skill_id] += score
                if term not in matched_terms[skill_id]:
                    matched_terms[skill_id].append(term)

        # Sort and filter
        results = [
            SearchResult(
                skill_id=sid,
                score=score,
                matched_terms=matched_terms[sid],
            )
            for sid, score in scores.items()
            if score > min_score
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def search_ids(self, query: str, limit: int = 20) -> List[str]:
        """Convenience: return just skill IDs from search results."""
        return [r.skill_id for r in self.search(query, limit)]

    @property
    def is_indexed(self) -> bool:
        """Whether the index has been built."""
        return self._indexed

    @property
    def doc_count(self) -> int:
        """Number of indexed skills."""
        return self._doc_count

    def reset(self) -> None:
        """Clear the index (for testing)."""
        with self._lock:
            self._docs.clear()
            self._inverted_index.clear()
            self._idf_cache.clear()
            self._doc_count = 0
            self._avg_doc_length = 0.0
            self._indexed = False

    # ------------------------------------------------------------------
    # Tokenization
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing.

        Vietnamese-aware: splits on whitespace and punctuation,
        lowercases, removes stop words. Preserves Vietnamese diacritics.
        """
        if not text:
            return []

        # Lowercase and normalize
        text = text.lower().strip()

        # Split on non-alphanumeric (preserving Vietnamese diacritics)
        # \w in Python includes Unicode word chars (accented letters)
        tokens = re.findall(r'[\w]+', text, re.UNICODE)

        # Remove stop words and very short tokens
        tokens = [
            t for t in tokens
            if t not in _VIETNAMESE_STOP_WORDS and len(t) >= 2
        ]

        return tokens
