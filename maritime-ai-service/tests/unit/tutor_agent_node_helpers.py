import sys
import types
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Break circular import: multi_agent.__init__ → graph → agents → tutor_node
# → services.__init__ → chat_service → multi_agent.graph
_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
if not _had_cs:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.engine.multi_agent.agent_config import AgentConfigRegistry

if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Lazy import inside _build_system_prompt() does:
#   from app.domains.registry import get_domain_registry
# Patch at SOURCE module.
DOMAIN_REGISTRY_PATCH = "app.domains.registry.get_domain_registry"

_SENTINEL = object()


def _make_tutor(llm=None, llm_with_tools=_SENTINEL):
    """Create TutorAgentNode with mocked LLM and tools.

    Args:
        llm: Mock for self._llm. None = unavailable.
        llm_with_tools: Mock for self._llm_with_tools.
            _SENTINEL (default) = use whatever _init_llm() produces.
            None = explicitly set _llm_with_tools to None (for testing unavailable).
            MagicMock = override with that mock.
    """
    with patch.object(
        AgentConfigRegistry, "get_llm", return_value=llm,
    ), patch(
        "app.engine.multi_agent.agents.tutor_node.get_prompt_loader",
    ) as mock_loader_fn:
        mock_loader = MagicMock()
        mock_loader.build_system_prompt.return_value = "You are Wiii Tutor."
        mock_loader_fn.return_value = mock_loader

        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode
        node = TutorAgentNode()

        # Override _llm_with_tools if explicitly specified
        if llm_with_tools is not _SENTINEL:
            node._llm_with_tools = llm_with_tools

        return node


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


@pytest.fixture
def base_state():
    return {
        "query": "Giải thích COLREGs Rule 13",
        "context": {
            "user_name": "Minh",
            "user_role": "student",
            "pronoun_style": {"user_called": "em", "ai_self": "thầy"},
        },
        "learning_context": {},
    }
