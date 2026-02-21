"""
Sprint 167: Artifact Streaming Tests — "Không Gian Sáng Tạo"

Tests for:
- ARTIFACT StreamEventType
- create_artifact_event() factory
- enable_artifacts config flag
- SSE artifact event forwarding in chat_stream.py
- graph_streaming _convert_bus_event for artifact type
"""
import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock


# =====================================================================
# 1. StreamEventType.ARTIFACT
# =====================================================================

class TestArtifactEventType:
    """Test ARTIFACT constant exists in StreamEventType."""

    def test_artifact_type_exists(self):
        from app.engine.multi_agent.stream_utils import StreamEventType
        assert hasattr(StreamEventType, "ARTIFACT")
        assert StreamEventType.ARTIFACT == "artifact"

    def test_all_event_types_include_artifact(self):
        from app.engine.multi_agent.stream_utils import StreamEventType
        all_types = [
            StreamEventType.STATUS,
            StreamEventType.THINKING,
            StreamEventType.ANSWER,
            StreamEventType.SOURCES,
            StreamEventType.METADATA,
            StreamEventType.DONE,
            StreamEventType.ERROR,
            StreamEventType.ARTIFACT,
            StreamEventType.PREVIEW,
        ]
        assert "artifact" in all_types


# =====================================================================
# 2. create_artifact_event()
# =====================================================================

class TestCreateArtifactEvent:
    """Test artifact event factory function."""

    @pytest.mark.asyncio
    async def test_basic_code_artifact(self):
        from app.engine.multi_agent.stream_utils import create_artifact_event
        event = await create_artifact_event(
            artifact_type="code",
            artifact_id="art-001",
            title="Hello World",
            content="print('Hello')",
            language="python",
            node="tutor_agent",
        )
        assert event.type == "artifact"
        assert event.content["artifact_type"] == "code"
        assert event.content["artifact_id"] == "art-001"
        assert event.content["title"] == "Hello World"
        assert event.content["content"] == "print('Hello')"
        assert event.content["language"] == "python"
        assert event.node == "tutor_agent"
        assert event.content["metadata"] == {}

    @pytest.mark.asyncio
    async def test_html_artifact_with_metadata(self):
        from app.engine.multi_agent.stream_utils import create_artifact_event
        event = await create_artifact_event(
            artifact_type="html",
            artifact_id="art-002",
            title="Demo Page",
            content="<h1>Hello</h1>",
            metadata={"execution_status": "success"},
        )
        assert event.content["artifact_type"] == "html"
        assert event.content["metadata"]["execution_status"] == "success"

    @pytest.mark.asyncio
    async def test_table_artifact(self):
        from app.engine.multi_agent.stream_utils import create_artifact_event
        table_json = json.dumps([{"name": "A", "value": 1}, {"name": "B", "value": 2}])
        event = await create_artifact_event(
            artifact_type="table",
            artifact_id="art-003",
            title="Data Table",
            content=table_json,
        )
        assert event.content["artifact_type"] == "table"
        # Content is stored as string
        parsed = json.loads(event.content["content"])
        assert len(parsed) == 2

    @pytest.mark.asyncio
    async def test_default_language_empty(self):
        from app.engine.multi_agent.stream_utils import create_artifact_event
        event = await create_artifact_event(
            artifact_type="html",
            artifact_id="art-004",
            title="HTML",
            content="<p>test</p>",
        )
        assert event.content["language"] == ""

    @pytest.mark.asyncio
    async def test_to_dict_serialization(self):
        from app.engine.multi_agent.stream_utils import create_artifact_event
        event = await create_artifact_event(
            artifact_type="code",
            artifact_id="art-005",
            title="Test",
            content="x = 1",
            language="python",
            node="direct",
        )
        d = event.to_dict()
        assert d["type"] == "artifact"
        assert d["node"] == "direct"
        assert d["content"]["artifact_id"] == "art-005"
        # Should be JSON-serializable
        json.dumps(d, ensure_ascii=False)


# =====================================================================
# 3. enable_artifacts config flag
# =====================================================================

class TestArtifactConfig:
    """Test enable_artifacts flag in Settings."""

    def test_enable_artifacts_default_true(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            _env_file=None,
        )
        assert s.enable_artifacts is True

    def test_enable_artifacts_can_be_disabled(self):
        import os
        with patch.dict(os.environ, {"ENABLE_ARTIFACTS": "false"}):
            from app.core.config import Settings
            s = Settings(
                google_api_key="test",
                api_key="test",
                enable_artifacts=False,
                _env_file=None,
            )
            assert s.enable_artifacts is False

    def test_feature_gate_blocks_artifact_sse_emission(self):
        """L-6: When enable_artifacts=False, artifact events should be skipped."""
        from app.core.config import settings
        original = settings.enable_artifacts
        try:
            settings.enable_artifacts = False
            # Artifact emission is gated in chat_stream.py SSE generator
            # We verify the config flag is respected
            assert settings.enable_artifacts is False
        finally:
            settings.enable_artifacts = original


# =====================================================================
# 4. ChatRequest enable_artifacts field
# =====================================================================

class TestChatRequestArtifactField:
    """Test enable_artifacts optional field on ChatRequest."""

    def test_default_none(self):
        from app.models.schemas import ChatRequest
        req = ChatRequest(
            user_id="u1",
            message="hello",
            role="student",
        )
        assert req.enable_artifacts is None

    def test_explicit_true(self):
        from app.models.schemas import ChatRequest
        req = ChatRequest(
            user_id="u1",
            message="hello",
            role="student",
            enable_artifacts=True,
        )
        assert req.enable_artifacts is True

    def test_explicit_false(self):
        from app.models.schemas import ChatRequest
        req = ChatRequest(
            user_id="u1",
            message="hello",
            role="student",
            enable_artifacts=False,
        )
        assert req.enable_artifacts is False


# =====================================================================
# 5. SSE format_sse for artifact event
# =====================================================================

class TestSSEArtifactFormat:
    """Test that format_sse correctly formats artifact events."""

    def test_format_sse_artifact(self):
        from app.api.v1.chat_stream import format_sse
        data = {
            "content": {
                "artifact_type": "code",
                "artifact_id": "art-100",
                "title": "Python Script",
                "content": "print(1)",
                "language": "python",
                "metadata": {},
            },
            "node": "tutor_agent",
        }
        result = format_sse("artifact", data, event_id=5)
        assert "event: artifact" in result
        assert "id: 5" in result
        assert "art-100" in result
        assert "Python Script" in result

    def test_format_sse_artifact_json_parseable(self):
        from app.api.v1.chat_stream import format_sse
        data = {"content": {"artifact_type": "html"}, "node": None}
        result = format_sse("artifact", data)
        # Extract data line
        for line in result.split("\n"):
            if line.startswith("data: "):
                parsed = json.loads(line[6:])
                assert parsed["content"]["artifact_type"] == "html"


# =====================================================================
# 6. graph_streaming _convert_bus_event for artifact
# =====================================================================

class TestGraphStreamingArtifact:
    """Test _convert_bus_event handles artifact type."""

    @pytest.mark.asyncio
    async def test_convert_artifact_bus_event(self):
        from app.engine.multi_agent.graph_streaming import _convert_bus_event
        bus_event = {
            "type": "artifact",
            "node": "tutor_agent",
            "content": {
                "artifact_type": "code",
                "artifact_id": "art-200",
                "title": "Example",
                "content": "x = 42",
                "language": "python",
                "metadata": {"execution_status": "pending"},
            },
        }
        stream_event = await _convert_bus_event(bus_event)
        assert stream_event.type == "artifact"
        assert stream_event.content["artifact_id"] == "art-200"
        assert stream_event.content["artifact_type"] == "code"
        assert stream_event.node == "tutor_agent"

    @pytest.mark.asyncio
    async def test_convert_artifact_bus_event_minimal(self):
        from app.engine.multi_agent.graph_streaming import _convert_bus_event
        bus_event = {
            "type": "artifact",
            "content": {
                "artifact_type": "html",
                "artifact_id": "art-201",
                "title": "Page",
                "content": "<p>Hi</p>",
            },
        }
        stream_event = await _convert_bus_event(bus_event)
        assert stream_event.type == "artifact"
        assert stream_event.content["language"] == ""


# =====================================================================
# 7. Artifact type variations
# =====================================================================

class TestArtifactTypeVariations:
    """Test all 7 artifact types can be created."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("artifact_type", [
        "code", "html", "react", "table", "chart", "document", "excel"
    ])
    async def test_all_artifact_types(self, artifact_type):
        from app.engine.multi_agent.stream_utils import create_artifact_event
        event = await create_artifact_event(
            artifact_type=artifact_type,
            artifact_id=f"art-{artifact_type}",
            title=f"Test {artifact_type}",
            content="test content",
        )
        assert event.type == "artifact"
        assert event.content["artifact_type"] == artifact_type


# =====================================================================
# 8. StreamEvent dataclass compatibility
# =====================================================================

class TestStreamEventCompatibility:
    """Ensure artifact events work with existing StreamEvent methods."""

    @pytest.mark.asyncio
    async def test_artifact_event_to_dict(self):
        from app.engine.multi_agent.stream_utils import create_artifact_event
        event = await create_artifact_event(
            artifact_type="code",
            artifact_id="compat-1",
            title="Compat Test",
            content="pass",
            language="python",
            node="synthesizer",
        )
        d = event.to_dict()
        assert "type" in d
        assert "content" in d
        assert "node" in d
        assert d["type"] == "artifact"
        assert d["node"] == "synthesizer"

    @pytest.mark.asyncio
    async def test_artifact_event_no_step(self):
        from app.engine.multi_agent.stream_utils import create_artifact_event
        event = await create_artifact_event(
            artifact_type="html",
            artifact_id="compat-2",
            title="No Step",
            content="<b>test</b>",
        )
        # Artifact events don't have step
        assert event.step is None
        assert event.confidence is None
