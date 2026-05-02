from types import SimpleNamespace


def test_host_ui_route_without_host_caps_does_not_force_generic_tools(monkeypatch):
    from app.engine.multi_agent import tool_collection as module

    monkeypatch.setattr(module.settings, "enable_character_tools", False, raising=False)
    monkeypatch.setattr(module.settings, "enable_lms_integration", True, raising=False)
    monkeypatch.setattr(module.settings, "enable_host_actions", True, raising=False)
    monkeypatch.setattr(module.settings, "enable_structured_visuals", True, raising=False)

    def fake_load_attr(module_name: str, attr_name: str):
        if module_name.endswith("utility_tools"):
            return SimpleNamespace(name=attr_name)
        if module_name.endswith("web_search_tools"):
            return SimpleNamespace(name=attr_name)
        if module_name.endswith("agent_tools") and attr_name == "RAG_KNOWLEDGE_TOOL":
            return SimpleNamespace(name="tool_rag_knowledge")
        if module_name.endswith("lms_tools") and attr_name == "get_all_lms_tools":
            return lambda role="student": [SimpleNamespace(name="tool_lms_courses")]
        if module_name.endswith("direct_intent"):
            mapping = {
                "_normalize_for_intent": lambda query: str(query).lower(),
                "_needs_direct_knowledge_search": lambda _query: False,
            }
            return mapping[attr_name]
        raise AssertionError(f"Unexpected load: {module_name}.{attr_name}")

    monkeypatch.setattr(module, "_load_attr", fake_load_attr)

    tools, force_tools = module._collect_direct_tools(
        "Wiii oi, nut Kham pha khoa hoc o dau?",
        state={"routing_metadata": {"intent": "host_ui_navigation"}, "context": {}},
    )

    assert tools == []
    assert force_tools is False


def test_host_ui_route_scopes_to_host_action_tools(monkeypatch):
    from app.engine.multi_agent import tool_collection as module

    monkeypatch.setattr(module.settings, "enable_character_tools", False, raising=False)
    monkeypatch.setattr(module.settings, "enable_lms_integration", True, raising=False)
    monkeypatch.setattr(module.settings, "enable_host_actions", True, raising=False)
    monkeypatch.setattr(module.settings, "enable_structured_visuals", True, raising=False)

    host_tools = [
        SimpleNamespace(name="host_action__ui_highlight"),
        SimpleNamespace(name="host_action__ui_click"),
    ]

    def fake_load_attr(module_name: str, attr_name: str):
        if module_name.endswith("utility_tools"):
            return SimpleNamespace(name=attr_name)
        if module_name.endswith("web_search_tools"):
            return SimpleNamespace(name=attr_name)
        if module_name.endswith("agent_tools") and attr_name == "RAG_KNOWLEDGE_TOOL":
            return SimpleNamespace(name="tool_rag_knowledge")
        if module_name.endswith("lms_tools") and attr_name == "get_all_lms_tools":
            return lambda role="student": [SimpleNamespace(name="tool_lms_courses")]
        if module_name.endswith("action_tools") and attr_name == "generate_host_action_tools":
            return lambda *args, **kwargs: host_tools
        if module_name.endswith("direct_intent"):
            mapping = {
                "_normalize_for_intent": lambda query: str(query).lower(),
                "_needs_direct_knowledge_search": lambda _query: False,
            }
            return mapping[attr_name]
        raise AssertionError(f"Unexpected load: {module_name}.{attr_name}")

    monkeypatch.setattr(module, "_load_attr", fake_load_attr)

    tools, force_tools = module._collect_direct_tools(
        "Wiii oi, nut Kham pha khoa hoc o dau?",
        state={
            "routing_metadata": {"intent": "host_ui_navigation"},
            "context": {},
            "host_capabilities": {"tools": [{"name": "ui.highlight"}]},
        },
    )

    assert [tool.name for tool in tools] == [
        "host_action__ui_highlight",
        "host_action__ui_click",
    ]
    assert force_tools is True
