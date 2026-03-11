"""app.core.config package — re-exports everything from sub-modules for backward compatibility.

All existing imports continue to work unchanged:
    from app.core.config import settings
    from app.core.config import Settings, get_settings
    from app.core.config import DatabaseConfig, LLMConfig, RAGConfig, ...
"""

from app.core.config.database import DatabaseConfig
from app.core.config.llm import LLMConfig
from app.core.config.rag import RAGConfig
from app.core.config.memory import MemoryConfig
from app.core.config.product_search import ProductSearchConfig
from app.core.config.thinking import ThinkingConfig
from app.core.config.character import CharacterConfig
from app.core.config.cache import CacheConfig
from app.core.config.living_agent import LivingAgentConfig
from app.core.config.lms import LMSIntegrationConfig
from app.core.config._settings import Settings, get_settings, settings

__all__ = [
    # Nested config group classes
    "DatabaseConfig",
    "LLMConfig",
    "RAGConfig",
    "MemoryConfig",
    "ProductSearchConfig",
    "ThinkingConfig",
    "CharacterConfig",
    "CacheConfig",
    "LivingAgentConfig",
    "LMSIntegrationConfig",
    # Main settings
    "Settings",
    "get_settings",
    "settings",
]
