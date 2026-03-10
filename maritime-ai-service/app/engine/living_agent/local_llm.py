"""
Local LLM Client — Async Ollama client for zero-cost autonomous tasks.

Sprint 170: "Linh Hồn Sống"

Provides a lightweight async client for the local Ollama instance.
Used by the heartbeat system, social browser, and skill builder
for 24/7 operation without API costs.

Design:
    - Async HTTP client (httpx) for non-blocking calls
    - Configurable model and endpoint
    - Graceful fallback when Ollama is unavailable
    - Structured output support via system prompt instructions
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Default timeout for local model calls (generous for thinking models)
_DEFAULT_TIMEOUT = 300.0
_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_THINKING_MODEL_PREFIXES = ("qwen3", "deepseek-r1", "qwq")


def _model_supports_thinking(model_name: str) -> bool:
    """Return True when a local Ollama model should receive think=True."""
    model_lower = model_name.lower()
    if model_lower.startswith("qwen3") and "-instruct" in model_lower:
        return False
    return model_lower.startswith(_DEFAULT_THINKING_MODEL_PREFIXES)


class LocalLLMClient:
    """Async client for local Ollama instance.

    Used for autonomous tasks that don't need cloud-grade quality:
    - Content summarization during browsing
    - Daily reflection and journal writing
    - Skill note-taking
    - Emotional state analysis

    Usage:
        client = LocalLLMClient(model="qwen3:4b-instruct-2507-q4_K_M")
        response = await client.generate("Summarize this article...")
        structured = await client.generate_json("Extract key facts...", schema_hint="...")
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        from app.core.config import settings
        self._model = model or settings.living_agent_local_model
        self._base_url = (base_url or settings.ollama_base_url or _DEFAULT_BASE_URL).rstrip("/")
        keep_alive = getattr(settings, "ollama_keep_alive", None)
        if isinstance(keep_alive, str):
            keep_alive = keep_alive.strip() or None
        else:
            keep_alive = None
        self._keep_alive = keep_alive
        self._timeout = timeout
        self._available: Optional[bool] = None
        self._unavailable_logged = False

    @property
    def model(self) -> str:
        return self._model

    async def is_available(self) -> bool:
        """Check if Ollama is running and the model is loaded."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    # Check if our model is available (exact or prefix match)
                    model_base = self._model.split(":")[0]
                    self._available = any(
                        model_base in m for m in models
                    )
                    return self._available
        except Exception as e:
            logger.debug("[LOCAL_LLM] Ollama not available: %s", e)
        self._available = False
        return False

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        think: bool = True,
    ) -> str:
        """Generate text from the local model.

        Args:
            prompt: The user/input prompt.
            system: Optional system prompt.
            temperature: Sampling temperature (0-1).
            max_tokens: Maximum tokens to generate.
            think: Enable thinking mode (slower but higher quality).
                   Set to False for simple tasks like scoring (6x faster).

        Returns:
            Generated text, or empty string if unavailable.
        """
        if self._available is False:
            available = await self.is_available()
            if not available:
                if not self._unavailable_logged:
                    logger.info(
                        "[LOCAL_LLM] Ollama unavailable at %s; skipping local model requests",
                        self._base_url,
                    )
                    self._unavailable_logged = True
                return ""

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self._chat(messages, temperature, max_tokens, think=think)

    async def generate_json(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        think: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Generate structured JSON from the local model.

        Uses lower temperature and JSON format instruction for reliability.
        Defaults to think=False for faster structured extraction.

        Returns:
            Parsed JSON dict, or None if generation/parsing fails.
        """
        json_system = (
            f"{system}\n\n"
            "IMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation."
        ) if system else "Respond ONLY with valid JSON. No markdown, no explanation."

        text = await self.generate(prompt, system=json_system, temperature=temperature, think=think)
        if not text:
            return None

        # Try to extract JSON from response
        text = text.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("[LOCAL_LLM] Failed to parse JSON response: %s...", text[:100])
            return None

    async def summarize(self, text: str, max_words: int = 100) -> str:
        """Summarize text content using the local model.

        Args:
            text: Text to summarize.
            max_words: Target summary length.

        Returns:
            Summary string.
        """
        if not text or len(text) < 50:
            return text

        prompt = (
            f"Tóm tắt nội dung sau trong khoảng {max_words} từ bằng tiếng Việt. "
            f"Giữ lại thông tin quan trọng nhất:\n\n{text[:4000]}"
        )
        return await self.generate(prompt, temperature=0.3, max_tokens=512)

    async def rate_relevance(
        self,
        content: str,
        interests: List[str],
    ) -> float:
        """Rate how relevant content is to Wiii's interests.

        Returns:
            Relevance score from 0.0 to 1.0.
        """
        interests_str = ", ".join(interests[:5])
        prompt = (
            f"Đánh giá mức độ liên quan của nội dung sau với các sở thích: {interests_str}\n\n"
            f"Nội dung: {content[:2000]}\n\n"
            f"Trả lời chỉ một số từ 0.0 đến 1.0 (ví dụ: 0.7). Không giải thích."
        )
        # think=False: simple scoring, no deep reasoning needed (6x faster)
        text = await self.generate(prompt, temperature=0.1, max_tokens=10, think=False)

        try:
            score = float(text.strip().split()[0])
            return max(0.0, min(1.0, score))
        except (ValueError, IndexError):
            return 0.3  # Default moderate relevance

    async def _chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        think: bool = True,
    ) -> str:
        """Execute a chat completion against Ollama API.

        Args:
            think: Enable thinking mode. When True, qwen3 separates reasoning
                   from content (slower, ~40s). When False, reasoning leaks into
                   content but response is 6x faster (~6s). Use False for simple
                   scoring/classification tasks.
        """
        effective_think = think and _model_supports_thinking(self._model)

        # Budget x3 when thinking to account for thinking tokens (discarded).
        num_predict = max_tokens * 3 if effective_think else max_tokens
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "think": effective_think,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
            },
        }
        if self._keep_alive:
            payload["keep_alive"] = self._keep_alive

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                self._available = True
                self._unavailable_logged = False
                return data.get("message", {}).get("content", "")

        except httpx.TimeoutException:
            self._available = False
            logger.warning("[LOCAL_LLM] Request timed out (%.0fs)", self._timeout)
            return ""
        except httpx.HTTPStatusError as e:
            self._available = False
            logger.warning("[LOCAL_LLM] HTTP error: %s", e.response.status_code)
            return ""
        except Exception as e:
            self._available = False
            logger.warning("[LOCAL_LLM] Request failed: %s", e)
            return ""


# =============================================================================
# Singleton
# =============================================================================

_client_instance: Optional[LocalLLMClient] = None


def get_local_llm() -> LocalLLMClient:
    """Get the singleton LocalLLMClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = LocalLLMClient()
        logger.info("[LOCAL_LLM] Client initialized: model=%s", _client_instance.model)
    return _client_instance
