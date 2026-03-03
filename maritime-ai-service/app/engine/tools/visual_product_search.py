"""
Visual Product Search Tool — Sprint 200: "Mắt Sản Phẩm"

Identifies products from user-uploaded images using Vision LLM,
then returns structured info (name, brand, model, category, keywords)
for downstream platform search.

Architecture:
    VisionProvider ABC → GeminiVisionProvider (default)
                       → OpenAIVisionProvider (future)
                       → OllamaVisionProvider (future)

    Provider + model resolved from config at call time:
        visual_product_search_provider: "google" | "openai"
        visual_product_search_model:    (empty=provider default)
            Google: gemini-3.1-flash-lite-preview (default),
                    gemini-3-flash-preview, gemini-3-pro-preview,
                    gemini-3.1-pro-preview
            OpenAI: gpt-4o (default), gpt-4o-mini

Feature gate: enable_visual_product_search=False
"""

import abc
import base64
import json
import logging
from typing import Any, Dict

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

# ============================================================================
# Identification prompt (shared across providers)
# ============================================================================

_IDENTIFY_PROMPT = """Analyze this product image carefully and identify:

1. product_name (English): exact product name, model, version
2. product_name_vi (Vietnamese): tên sản phẩm tiếng Việt
3. brand: manufacturer or brand name (empty string if unknown)
4. model: model number if visible on product/packaging (empty string if not visible)
5. category: one of [electronics, fashion, industrial, food, beauty, home, automotive, sports, toys, office, other]
6. estimated_price_range_usd: rough price range as string like "$10-$50"
7. search_keywords: list of 3-5 search keywords optimized for Vietnamese e-commerce platforms
8. search_keywords_en: list of 3-5 English search keywords for international search
9. confidence: 0.0-1.0 how confident you are in the identification

Return ONLY valid JSON. If no product is visible in the image, return:
{"error": "no_product_found", "description": "Brief description of what is in the image"}
"""


# ============================================================================
# Vision Provider Abstraction
# ============================================================================

class VisionProvider(abc.ABC):
    """Abstract base class for vision model providers.

    To add a new provider:
    1. Subclass VisionProvider
    2. Implement identify()
    3. Register in _PROVIDER_REGISTRY below
    """

    @abc.abstractmethod
    def identify(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        model: str,
    ) -> str:
        """Call vision model and return raw text response.

        Args:
            image_bytes: Raw image bytes (already decoded from base64)
            mime_type: MIME type (e.g. "image/jpeg")
            prompt: Full identification prompt
            model: Model name to use

        Returns:
            Raw text response from the model (should be JSON)
        """
        ...


class GeminiVisionProvider(VisionProvider):
    """Google Gemini Vision via google.genai SDK."""

    def identify(self, image_bytes: bytes, mime_type: str, prompt: str, model: str) -> str:
        from app.core.config import get_settings
        from google import genai

        client = genai.Client(api_key=get_settings().google_api_key)
        response = client.models.generate_content(
            model=model,
            contents=[{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}},
                    {"text": prompt},
                ],
            }],
        )
        return response.text.strip()


class OpenAIVisionProvider(VisionProvider):
    """OpenAI GPT-4o Vision via openai SDK (future use)."""

    def identify(self, image_bytes: bytes, mime_type: str, prompt: str, model: str) -> str:
        from app.core.config import get_settings
        import openai

        client = openai.OpenAI(api_key=get_settings().openai_api_key)
        b64_data = base64.b64encode(image_bytes).decode()
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_data}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()


# ============================================================================
# Provider Registry — add new providers here
# ============================================================================

_PROVIDER_REGISTRY: Dict[str, type] = {
    "google": GeminiVisionProvider,
    "openai": OpenAIVisionProvider,
}


def get_vision_provider(provider_name: str) -> VisionProvider:
    """Get a vision provider instance by name.

    Args:
        provider_name: Provider key (e.g. "google", "openai")

    Returns:
        VisionProvider instance

    Raises:
        ValueError: If provider not found in registry
    """
    cls = _PROVIDER_REGISTRY.get(provider_name)
    if cls is None:
        available = ", ".join(sorted(_PROVIDER_REGISTRY.keys()))
        raise ValueError(
            f"Unknown vision provider '{provider_name}'. "
            f"Available: {available}. "
            f"Register new providers in _PROVIDER_REGISTRY."
        )
    return cls()


# ============================================================================
# Default model per provider
# ============================================================================

_DEFAULT_MODELS: Dict[str, str] = {
    "google": "gemini-3.1-flash-lite-preview",
    "openai": "gpt-4o",
}

# All supported Google models (for reference):
# Gemini 3.1: gemini-3.1-flash-lite-preview, gemini-3.1-pro-preview, gemini-3.1-flash-image-preview
# Gemini 3.0: gemini-3-flash-preview, gemini-3-pro-preview


# ============================================================================
# Tool Function
# ============================================================================

def _parse_vision_response(raw_text: str) -> Dict[str, Any]:
    """Parse and validate the vision model's JSON response.

    Handles markdown code fences, missing fields, and error responses.
    """
    text = raw_text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.startswith("```")]
        text = "\n".join(lines).strip()

    result = json.loads(text)

    # Validate / fill defaults for successful identification
    if "error" not in result:
        result.setdefault("product_name", "Unknown Product")
        result.setdefault("product_name_vi", "Sản phẩm không xác định")
        result.setdefault("brand", "")
        result.setdefault("model", "")
        result.setdefault("category", "other")
        result.setdefault("search_keywords", [])
        result.setdefault("search_keywords_en", [])
        result.setdefault("confidence", 0.5)

    return result


def _identify_product_from_image(
    image_data: str,
    image_media_type: str = "image/jpeg",
    context: str = "",
) -> str:
    """Identify a product from an uploaded image using AI Vision.

    Use this when a user uploads/sends a product image and wants to find,
    compare, or search for that product on e-commerce platforms.

    Args:
        image_data: Base64-encoded image data (without data URL prefix)
        image_media_type: MIME type of the image (default: image/jpeg)
        context: Optional user hint about the product (e.g. "tìm cái này ở VN")

    Returns:
        JSON string with product identification: name, brand, model, category,
        search keywords, and confidence score.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()

        if not settings.enable_visual_product_search:
            return json.dumps({
                "error": "visual_product_search_disabled",
                "message": "Visual product search is not enabled",
            }, ensure_ascii=False)

        # Resolve provider + model from config
        provider_name = getattr(settings, "visual_product_search_provider", "google")
        model_name = getattr(settings, "visual_product_search_model", None)
        if not model_name:
            model_name = _DEFAULT_MODELS.get(provider_name, "gemini-3.1-flash-lite-preview")

        # Build prompt
        prompt = _IDENTIFY_PROMPT
        if context:
            prompt += f"\n\nUser context/hint: {context}"

        # Decode image
        image_bytes = base64.b64decode(image_data)

        # Call vision provider
        provider = get_vision_provider(provider_name)
        raw_response = provider.identify(
            image_bytes=image_bytes,
            mime_type=image_media_type,
            prompt=prompt,
            model=model_name,
        )

        # Parse response
        result = _parse_vision_response(raw_response)

        logger.info(
            "[VISUAL_SEARCH] provider=%s model=%s identified=%s confidence=%.2f",
            provider_name,
            model_name,
            result.get("product_name", result.get("error", "unknown")),
            result.get("confidence", 0),
        )

        return json.dumps(result, ensure_ascii=False)

    except json.JSONDecodeError as e:
        logger.warning("[VISUAL_SEARCH] JSON parse failed: %s", e)
        return json.dumps({
            "error": "parse_failed",
            "raw_response": raw_response[:500] if "raw_response" in dir() else "",
            "message": "Could not parse vision model response as JSON",
        }, ensure_ascii=False)

    except Exception as e:
        logger.warning("[VISUAL_SEARCH] Identification failed: %s", e)
        return json.dumps({
            "error": "identification_failed",
            "message": str(e)[:200],
        }, ensure_ascii=False)


# ============================================================================
# Tool Registration
# ============================================================================

def get_visual_product_search_tool() -> StructuredTool:
    """Get the visual product search tool for registration."""
    return StructuredTool.from_function(
        func=_identify_product_from_image,
        name="tool_identify_product_from_image",
        description=(
            "Identify a product from an uploaded image using AI Vision. "
            "Returns product name, brand, model, category, and search keywords. "
            "Use when user sends a product photo and wants to search/compare."
        ),
    )


def get_visual_product_search_tools() -> list:
    """Get all visual product search tools as a list."""
    return [get_visual_product_search_tool()]
