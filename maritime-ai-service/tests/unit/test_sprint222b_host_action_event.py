"""Sprint 222b Phase 5: HOST_ACTION SSE event type."""
import pytest


class TestHostActionEventType:
    def test_host_action_type_exists(self):
        from app.engine.multi_agent.stream_utils import StreamEventType
        assert hasattr(StreamEventType, "HOST_ACTION")
        assert StreamEventType.HOST_ACTION == "host_action"


class TestCreateHostActionEvent:
    @pytest.mark.asyncio
    async def test_create_host_action_event(self):
        from app.engine.multi_agent.stream_utils import create_host_action_event, StreamEventType
        event = await create_host_action_event(
            request_id="req-001",
            action="create_course",
            params={"name": "An toàn hàng hải"},
        )
        assert event.type == StreamEventType.HOST_ACTION
        assert event.content["id"] == "req-001"
        assert event.content["action"] == "create_course"
        assert event.content["params"]["name"] == "An toàn hàng hải"

    @pytest.mark.asyncio
    async def test_host_action_event_serializable(self):
        from app.engine.multi_agent.stream_utils import create_host_action_event
        import json
        event = await create_host_action_event(
            request_id="req-002",
            action="navigate",
            params={"url": "/course/123"},
            node="direct_response",
        )
        d = event.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        assert "req-002" in json_str
        assert d["node"] == "direct_response"

    @pytest.mark.asyncio
    async def test_host_action_event_no_node(self):
        from app.engine.multi_agent.stream_utils import create_host_action_event
        event = await create_host_action_event(
            request_id="req-003",
            action="show_hint",
            params={},
        )
        assert event.node is None
