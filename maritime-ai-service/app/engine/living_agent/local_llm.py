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

# Default timeout for local model calls (generous for large models)
_DEFAULT_TIMEOUT = 120.0
_DEFAULT_BASE_URL = "http://localhost:11434"


class LocalLLMClient:
    """Async client for local Ollama instance.

    Used for autonomous tasks that don't need cloud-grade quality:
    - Content summarization during browsing
    - Daily reflection and journal writing
    - Skill note-taking
    - Emotional state analysis

    Usage:
        client = LocalLLMClient(model="qwen3:8b")
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
        self._timeout = timeout
        self._available: Optional[bool] = None

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
    ) -> str:
        """Generate text from the local model.

        Args:
            prompt: The user/input prompt.
            system: Optional system prompt.
            temperature: Sampling temperature (0-1).
            max_tokens: Maximum tokens to generate.

        Returns:
            Generated text, or empty string if unavailable.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self._chat(messages, temperature, max_tokens)

    async def generate_json(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
    ) -> Optional[Dict[str, Any]]:
        """Generate structured JSON from the local model.

        Uses lower temperature and JSON format instruction for reliability.

        Returns:
            Parsed JSON dict, or None if generation/parsing fails.
        """
        json_system = (
            f"{system}\n\n"
            "IMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation."
        ) if system else "Respond ONLY with valid JSON. No markdown, no explanation."

        text = await self.generate(prompt, system=json_system, temperature=temperature)
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
        text = await self.generate(prompt, temperature=0.1, max_tokens=10)

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
    ) -> str:
        """Execute a chat completion against Ollama API."""
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")

        except httpx.TimeoutException:
            logger.warning("[LOCAL_LLM] Request timed out (%.0fs)", self._timeout)
            return ""
        except httpx.HTTPStatusError as e:
            logger.warning("[LOCAL_LLM] HTTP error: %s", e.response.status_code)
            return ""
        except Exception as e:
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
