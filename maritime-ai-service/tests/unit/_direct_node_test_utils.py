"""Shared helpers for provider-independent DirectNode unit tests."""

from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, patch


@contextmanager
def patched_direct_node_runtime(
    response_text: str,
    *,
    captured_messages: list | None = None,
    mock_llm: MagicMock | None = None,
    collect_tools: tuple[list, bool] | None = ([], False),
    required_tool_names: set[str] | frozenset[str] | None = frozenset(),
    patch_bind: bool = True,
):
    """Keep DirectNode behavior under test while removing provider dependency.

    DirectNode tests generally care about prompt construction, domain notices,
    and final state. The provider failover/tool-round seam is integration
    territory, so unit tests stub it unless they explicitly need real binding.
    """
    llm = mock_llm or MagicMock()
    llm.bind_tools.return_value = llm

    async def fake_execute_direct_tool_rounds(
        _llm_with_tools,
        _llm_auto,
        messages,
        _tools,
        _push_event,
        **_kwargs,
    ):
        if captured_messages is not None:
            captured_messages.extend(messages)
        return MagicMock(content=response_text, tool_calls=[]), messages, []

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                return_value=llm,
            )
        )
        stack.enter_context(
            patch(
                "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_native_llm",
                return_value=None,
            )
        )
        stack.enter_context(patch("app.engine.multi_agent.graph._get_effective_provider", return_value=None))
        stack.enter_context(patch("app.engine.multi_agent.graph._get_explicit_user_provider", return_value=None))
        stack.enter_context(
            patch(
                "app.engine.multi_agent.graph._execute_direct_tool_rounds",
                side_effect=fake_execute_direct_tool_rounds,
            )
        )
        stack.enter_context(
            patch(
                "app.services.output_processor.extract_thinking_from_response",
                return_value=(response_text, None),
            )
        )
        if collect_tools is not None:
            stack.enter_context(
                patch(
                    "app.engine.multi_agent.graph._collect_direct_tools",
                    return_value=collect_tools,
                )
            )
        if required_tool_names is not None:
            stack.enter_context(
                patch(
                    "app.engine.multi_agent.graph._direct_required_tool_names",
                    return_value=required_tool_names,
                )
            )
        if patch_bind:
            stack.enter_context(
                patch(
                    "app.engine.multi_agent.graph._bind_direct_tools",
                    return_value=(llm, llm, None),
                )
            )
        yield llm
