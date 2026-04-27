"""Guards for WiiiRunner node registration surfaces."""

from __future__ import annotations


def _make_node(name: str):
    async def node(state):
        state.setdefault("_visited", []).append(name)
        return state

    return node


def test_runner_registers_nodes_from_runtime_node_surface(monkeypatch):
    import app.engine.multi_agent.runner as runner_mod
    import app.engine.multi_agent.runtime_nodes as runtime_nodes

    node_names = {
        "guardian_node": "guardian",
        "supervisor_node": "supervisor",
        "rag_node": "rag",
        "tutor_node": "tutor",
        "memory_node": "memory",
        "direct_response_node": "direct",
        "code_studio_node": "code_studio",
        "synthesizer_node": "synthesizer",
        "parallel_dispatch_node": "parallel",
        "colleague_agent_node": "colleague",
        "product_search_node": "product_search",
    }
    sentinels = {
        attr_name: _make_node(label)
        for attr_name, label in node_names.items()
    }

    monkeypatch.setattr(runner_mod, "_RUNNER", None)
    for attr_name, node in sentinels.items():
        monkeypatch.setattr(runtime_nodes, attr_name, node)

    runner = runner_mod.get_wiii_runner()

    assert runner._nodes["guardian"] is sentinels["guardian_node"]
    assert runner._nodes["supervisor"] is sentinels["supervisor_node"]
    assert runner._nodes["rag_agent"] is sentinels["rag_node"]
    assert runner._nodes["tutor_agent"] is sentinels["tutor_node"]
    assert runner._nodes["memory_agent"] is sentinels["memory_node"]
    assert runner._nodes["direct"] is sentinels["direct_response_node"]
    assert runner._nodes["code_studio_agent"] is sentinels["code_studio_node"]
    assert runner._nodes["synthesizer"] is sentinels["synthesizer_node"]
    assert (
        runner._feature_nodes["parallel_dispatch"][0]
        is sentinels["parallel_dispatch_node"]
    )
    assert runner._feature_nodes["colleague_agent"][0] is sentinels["colleague_agent_node"]
    assert runner._feature_nodes["product_search_agent"][0] is sentinels["product_search_node"]
