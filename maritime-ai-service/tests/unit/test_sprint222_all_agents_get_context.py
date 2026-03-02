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
