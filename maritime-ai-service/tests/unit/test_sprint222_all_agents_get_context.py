"""Sprint 222: Verify ALL agent paths include host_context_prompt."""
import pytest
import inspect


def test_direct_response_uses_host_context_prompt():
    """graph.py direct response path should use host_context_prompt."""
    from app.engine.multi_agent import graph
    source = inspect.getsource(graph)
    assert "host_context_prompt" in source


def test_memory_agent_uses_host_context_prompt():
    """memory_agent.py should read state host_context_prompt."""
    from app.engine.multi_agent.agents import memory_agent
    source = inspect.getsource(memory_agent)
    assert "host_context_prompt" in source
    assert "operator_context_prompt" in source


def test_answer_generator_accepts_host_context_prompt():
    """answer_generator should have host_context_prompt parameter."""
    from app.engine.agentic_rag.answer_generator import AnswerGenerator
    sig = inspect.signature(AnswerGenerator.generate_response)
    assert "host_context_prompt" in sig.parameters


def test_supervisor_synthesize_uses_host_context_prompt():
    """supervisor.synthesize() should include host_context_prompt."""
    from app.engine.multi_agent import supervisor
    source = inspect.getsource(supervisor.SupervisorAgent.synthesize)
    assert "host_context_prompt" in source
    assert "host_capabilities_prompt" in source
    assert "operator_context_prompt" in source


def test_tutor_agent_uses_operator_context_prompt():
    """tutor_node should receive operator-context prompt too."""
    from app.engine.multi_agent.agents import tutor_node

    source = inspect.getsource(tutor_node)
    assert "operator_context_prompt" in source


def test_rag_agent_uses_operator_context_prompt():
    """rag_node should receive operator-context prompt too."""
    from app.engine.multi_agent.agents import rag_node

    source = inspect.getsource(rag_node)
    assert "operator_context_prompt" in source
