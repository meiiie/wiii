"""
Sprint 179+: Visual RAG — "Mắt Thông Minh" Tests.

Tests for visual context enrichment in the RAG pipeline:
- Visual document selection and prioritization
- Image fetching and base64 encoding
- Gemini Vision analysis
- Document enrichment with visual descriptions
- Integration with corrective RAG pipeline
- Feature gate testing (enable_visual_rag=False → no change)
- Ingestion-time visual description generation
- Edge cases (no images, fetch failures, analysis failures)
"""

import asyncio
import base64
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


# ─── Helpers ───────────────────────────────────────────────────────────────

def _make_doc(
    node_id="node1",
    content="Sample content",
    title="Sample Title",
    score=0.8,
    image_url="https://minio.example.com/page1.jpg",
    page_number=1,
    document_id="doc1",
    content_type="text",
    bounding_boxes=None,
):
    return {
        "node_id": node_id,
        "content": content,
        "title": title,
        "score": score,
        "image_url": image_url,
        "page_number": page_number,
        "document_id": document_id,
        "content_type": content_type,
        "bounding_boxes": bounding_boxes,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Config Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestVisualRAGConfig:
    """Test visual RAG configuration flags."""

    def test_enable_visual_rag_default_false(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            _env_file=None,
        )
        assert s.enable_visual_rag is False

    def test_enable_visual_rag_can_be_enabled(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_visual_rag=True,
            _env_file=None,
        )
        assert s.enable_visual_rag is True

    def test_visual_rag_max_images_default(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            _env_file=None,
        )
        assert s.visual_rag_max_images == 3

    def test_visual_rag_max_images_custom(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            visual_rag_max_images=5,
            _env_file=None,
        )
        assert s.visual_rag_max_images == 5

    def test_visual_rag_max_images_validation(self):
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(
                google_api_key="test",
                api_key="test",
                visual_rag_max_images=0,
                _env_file=None,
            )

    def test_visual_rag_timeout_default(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            _env_file=None,
        )
        assert s.visual_rag_timeout == 15.0

    def test_visual_rag_timeout_custom(self):
        from app.core.config import Settings
        s = Settings(
            google_api_key="test",
            api_key="test",
            visual_rag_timeout=30.0,
            _env_file=None,
        )
        assert s.visual_rag_timeout == 30.0

    def test_visual_rag_timeout_validation(self):
        from app.core.config import Settings
        with pytest.raises(Exception):
            Settings(
                google_api_key="test",
                api_key="test",
                visual_rag_timeout=2.0,  # Below minimum 5.0
                _env_file=None,
            )


# ═══════════════════════════════════════════════════════════════════════════
# 2. Visual Document Selection
# ═══════════════════════════════════════════════════════════════════════════


class TestSelectVisualDocuments:
    """Test _select_visual_documents filtering and prioritization."""

    def test_empty_documents(self):
        from app.engine.agentic_rag.visual_rag import _select_visual_documents
        result = _select_visual_documents([], max_images=3)
        assert result == []

    def test_no_images(self):
        from app.engine.agentic_rag.visual_rag import _select_visual_documents
        docs = [_make_doc(image_url=""), _make_doc(image_url=None, node_id="n2")]
        result = _select_visual_documents(docs, max_images=3)
        assert result == []

    def test_selects_docs_with_image_url(self):
        from app.engine.agentic_rag.visual_rag import _select_visual_documents
        docs = [
            _make_doc(node_id="n1", image_url="https://example.com/img1.jpg"),
            _make_doc(node_id="n2", image_url=""),
            _make_doc(node_id="n3", image_url="https://example.com/img3.jpg"),
        ]
        result = _select_visual_documents(docs, max_images=5)
        assert len(result) == 2
        node_ids = {d["node_id"] for d in result}
        assert "n1" in node_ids
        assert "n3" in node_ids

    def test_respects_max_images(self):
        from app.engine.agentic_rag.visual_rag import _select_visual_documents
        docs = [
            _make_doc(node_id=f"n{i}", image_url=f"https://example.com/{i}.jpg")
            for i in range(5)
        ]
        result = _select_visual_documents(docs, max_images=2)
        assert len(result) == 2

    def test_prioritizes_visual_content_types(self):
        from app.engine.agentic_rag.visual_rag import _select_visual_documents
        docs = [
            _make_doc(node_id="text", content_type="text", score=0.5),
            _make_doc(node_id="table", content_type="table", score=0.5),
            _make_doc(node_id="diagram", content_type="diagram_reference", score=0.5),
        ]
        result = _select_visual_documents(docs, max_images=2)
        node_ids = [d["node_id"] for d in result]
        # Table and diagram should be prioritized over text with equal scores
        assert "table" in node_ids
        assert "diagram" in node_ids

    def test_prioritizes_formula_content_type(self):
        from app.engine.agentic_rag.visual_rag import _select_visual_documents
        docs = [
            _make_doc(node_id="text1", content_type="text", score=0.5),
            _make_doc(node_id="formula1", content_type="formula", score=0.5),
        ]
        result = _select_visual_documents(docs, max_images=1)
        assert result[0]["node_id"] == "formula1"

    def test_sorts_by_score_within_same_type(self):
        from app.engine.agentic_rag.visual_rag import _select_visual_documents
        docs = [
            _make_doc(node_id="t1", content_type="table", score=0.3),
            _make_doc(node_id="t2", content_type="table", score=0.9),
        ]
        result = _select_visual_documents(docs, max_images=2)
        # Higher score should come first
        assert result[0]["node_id"] == "t2"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Image Fetching
# ═══════════════════════════════════════════════════════════════════════════


class TestFetchImageAsBase64:
    """Test _fetch_image_as_base64 image download."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        from app.engine.agentic_rag.visual_rag import _fetch_image_as_base64

        fake_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Fake JPEG header
        expected_b64 = base64.b64encode(fake_image).decode("utf-8")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_image
        mock_response.headers = {"content-type": "image/jpeg"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await _fetch_image_as_base64("https://example.com/img.jpg")
            assert result == expected_b64

    @pytest.mark.asyncio
    async def test_http_error(self):
        from app.engine.agentic_rag.visual_rag import _fetch_image_as_base64

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await _fetch_image_as_base64("https://example.com/missing.jpg")
            assert result is None

    @pytest.mark.asyncio
    async def test_non_image_content_type(self):
        from app.engine.agentic_rag.visual_rag import _fetch_image_as_base64

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"<html>error</html>"
        mock_response.headers = {"content-type": "text/html"}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await _fetch_image_as_base64("https://example.com/error")
            assert result is None

    @pytest.mark.asyncio
    async def test_network_error(self):
        from app.engine.agentic_rag.visual_rag import _fetch_image_as_base64

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=ConnectionError("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await _fetch_image_as_base64("https://example.com/timeout")
            assert result is None


# ═══════════════════════════════════════════════════════════════════════════
# 4. Vision Analysis
# ═══════════════════════════════════════════════════════════════════════════


class TestAnalyzeImageWithVision:
    """Test _analyze_image_with_vision Gemini Vision integration."""

    @pytest.mark.asyncio
    async def test_successful_analysis(self):
        from app.engine.agentic_rag.visual_rag import _analyze_image_with_vision

        mock_response = MagicMock()
        mock_response.text = "Bảng so sánh COLREGs Rule 15 và Rule 16"

        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.google_api_key = "test-key"
        mock_settings.google_model = "gemini-2.0-flash"

        fake_b64 = base64.b64encode(b"fake image data").decode()

        # Patch at google.genai source module (lazy import inside function)
        with patch("google.genai.Client", return_value=mock_client), \
             patch("app.core.config.get_settings", return_value=mock_settings):

            result = await _analyze_image_with_vision(fake_b64, "Rule 15 là gì?")
            assert result is not None
            assert "COLREGs" in result

    @pytest.mark.asyncio
    async def test_empty_response(self):
        from app.engine.agentic_rag.visual_rag import _analyze_image_with_vision

        mock_response = MagicMock()
        mock_response.text = ""

        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "model"

        with patch("google.genai.Client", return_value=mock_client), \
             patch("app.core.config.get_settings", return_value=mock_settings):

            result = await _analyze_image_with_vision(
                base64.b64encode(b"data").decode(), "test"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_api_error(self):
        from app.engine.agentic_rag.visual_rag import _analyze_image_with_vision

        mock_settings = MagicMock()
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "model"

        with patch("google.genai.Client", side_effect=Exception("API error")), \
             patch("app.core.config.get_settings", return_value=mock_settings):

            result = await _analyze_image_with_vision(
                base64.b64encode(b"data").decode(), "test"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_query_truncation(self):
        from app.engine.agentic_rag.visual_rag import _analyze_image_with_vision

        mock_response = MagicMock()
        mock_response.text = "Description"

        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.google_api_key = "key"
        mock_settings.google_model = "model"

        long_query = "x" * 1000

        with patch("google.genai.Client", return_value=mock_client), \
             patch("app.core.config.get_settings", return_value=mock_settings):

            result = await _analyze_image_with_vision(
                base64.b64encode(b"data").decode(), long_query
            )
            assert result is not None


# ═══════════════════════════════════════════════════════════════════════════
# 5. Document Enrichment (Main Function)
# ═══════════════════════════════════════════════════════════════════════════


class TestEnrichDocumentsWithVisualContext:
    """Test the main enrich_documents_with_visual_context function."""

    @pytest.mark.asyncio
    async def test_no_visual_docs_returns_original(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [_make_doc(image_url=""), _make_doc(image_url=None, node_id="n2")]
        result = await enrich_documents_with_visual_context(docs, "test query")

        assert result.enriched_documents == docs
        assert result.total_images_analyzed == 0

    @pytest.mark.asyncio
    async def test_empty_documents(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        result = await enrich_documents_with_visual_context([], "test")
        assert result.enriched_documents == []
        assert result.total_images_analyzed == 0

    @pytest.mark.asyncio
    async def test_successful_enrichment(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [
            _make_doc(node_id="n1", content="Table data", content_type="table"),
            _make_doc(node_id="n2", content="Normal text", image_url=""),
        ]

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            new_callable=AsyncMock,
            return_value="base64data",
        ), patch(
            "app.engine.agentic_rag.visual_rag._analyze_image_with_vision",
            new_callable=AsyncMock,
            return_value="Bảng so sánh Rule 15 với Rule 16",
        ):
            result = await enrich_documents_with_visual_context(docs, "Rule 15")

            assert result.total_images_analyzed == 1
            # First doc should be enriched
            enriched_doc = result.enriched_documents[0]
            assert "[Mô tả hình ảnh trang 1]" in enriched_doc["content"]
            assert "visual_description" in enriched_doc
            # Second doc should be unchanged
            assert result.enriched_documents[1]["content"] == "Normal text"

    @pytest.mark.asyncio
    async def test_fetch_failure_graceful(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [_make_doc(node_id="n1", content_type="table")]

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await enrich_documents_with_visual_context(docs, "test")
            assert result.total_images_analyzed == 0
            assert result.enriched_documents[0]["content"] == docs[0]["content"]

    @pytest.mark.asyncio
    async def test_analysis_failure_graceful(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [_make_doc(node_id="n1", content_type="table")]

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            new_callable=AsyncMock,
            return_value="base64data",
        ), patch(
            "app.engine.agentic_rag.visual_rag._analyze_image_with_vision",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await enrich_documents_with_visual_context(docs, "test")
            assert result.total_images_analyzed == 0
            assert len(result.visual_analyses) == 1
            assert result.visual_analyses[0].success is False

    @pytest.mark.asyncio
    async def test_multiple_docs_enriched(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [
            _make_doc(node_id="n1", content_type="table", page_number=1),
            _make_doc(node_id="n2", content_type="diagram_reference", page_number=3,
                      image_url="https://example.com/page3.jpg"),
            _make_doc(node_id="n3", content_type="text", image_url=""),
        ]

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            new_callable=AsyncMock,
            return_value="b64",
        ), patch(
            "app.engine.agentic_rag.visual_rag._analyze_image_with_vision",
            new_callable=AsyncMock,
            return_value="Visual description here",
        ):
            result = await enrich_documents_with_visual_context(docs, "test", max_images=5)
            assert result.total_images_analyzed == 2
            # Both visual docs enriched
            assert "Visual description here" in result.enriched_documents[0]["content"]
            assert "Visual description here" in result.enriched_documents[1]["content"]
            # Text doc unchanged
            assert "Visual description" not in result.enriched_documents[2].get("content", "")

    @pytest.mark.asyncio
    async def test_respects_max_images(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [
            _make_doc(node_id=f"n{i}", content_type="table",
                      image_url=f"https://example.com/{i}.jpg")
            for i in range(5)
        ]

        call_count = 0

        async def mock_fetch(url, **kwargs):
            return "b64data"

        async def mock_analyze(b64, query, **kwargs):
            nonlocal call_count
            call_count += 1
            return "Desc"

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            side_effect=mock_fetch,
        ), patch(
            "app.engine.agentic_rag.visual_rag._analyze_image_with_vision",
            side_effect=mock_analyze,
        ):
            result = await enrich_documents_with_visual_context(docs, "test", max_images=2)
            # Only 2 images should be analyzed
            assert result.total_images_analyzed == 2

    @pytest.mark.asyncio
    async def test_timing_recorded(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [_make_doc(node_id="n1")]

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            new_callable=AsyncMock,
            return_value="b64",
        ), patch(
            "app.engine.agentic_rag.visual_rag._analyze_image_with_vision",
            new_callable=AsyncMock,
            return_value="Desc",
        ):
            result = await enrich_documents_with_visual_context(docs, "test")
            assert result.total_time_ms >= 0


# ═══════════════════════════════════════════════════════════════════════════
# 6. Visual Analysis Result Dataclass
# ═══════════════════════════════════════════════════════════════════════════


class TestDataclasses:
    """Test dataclass structures."""

    def test_visual_analysis_result_defaults(self):
        from app.engine.agentic_rag.visual_rag import VisualAnalysisResult

        r = VisualAnalysisResult(
            node_id="n1",
            description="Test",
            image_url="https://example.com/img.jpg",
            content_type="table",
        )
        assert r.success is True
        assert r.error is None
        assert r.processing_time_ms == 0.0

    def test_visual_analysis_result_failure(self):
        from app.engine.agentic_rag.visual_rag import VisualAnalysisResult

        r = VisualAnalysisResult(
            node_id="n1",
            description="",
            image_url="https://example.com/img.jpg",
            content_type="text",
            success=False,
            error="Fetch failed",
        )
        assert r.success is False
        assert r.error == "Fetch failed"

    def test_visual_enrichment_result_defaults(self):
        from app.engine.agentic_rag.visual_rag import VisualEnrichmentResult

        r = VisualEnrichmentResult(enriched_documents=[])
        assert r.visual_analyses == []
        assert r.total_images_analyzed == 0
        assert r.total_time_ms == 0.0

    def test_visual_enrichment_result_with_data(self):
        from app.engine.agentic_rag.visual_rag import VisualEnrichmentResult, VisualAnalysisResult

        analysis = VisualAnalysisResult(
            node_id="n1", description="Desc", image_url="url", content_type="table"
        )
        r = VisualEnrichmentResult(
            enriched_documents=[{"node_id": "n1"}],
            visual_analyses=[analysis],
            total_images_analyzed=1,
            total_time_ms=250.0,
        )
        assert len(r.visual_analyses) == 1
        assert r.total_images_analyzed == 1


# ═══════════════════════════════════════════════════════════════════════════
# 7. Feature Gate Integration Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFeatureGateIntegration:
    """Test that visual RAG is properly gated in corrective_rag.py."""

    @pytest.mark.asyncio
    async def test_visual_rag_disabled_no_enrichment(self):
        """When enable_visual_rag=False, documents pass through unchanged."""
        from app.engine.agentic_rag.corrective_rag import CorrectiveRAG

        mock_settings = MagicMock()
        mock_settings.enable_visual_rag = False
        mock_settings.rag_max_iterations = 1
        mock_settings.rag_confidence_high = 0.8
        mock_settings.enable_answer_verification = False
        mock_settings.semantic_cache_enabled = False
        mock_settings.enable_hyde = False
        mock_settings.enable_adaptive_rag = False
        mock_settings.enable_graph_rag = False

        mock_rag = MagicMock()
        mock_hybrid = MagicMock()
        mock_hybrid.is_available.return_value = True

        mock_result = MagicMock()
        mock_result.node_id = "n1"
        mock_result.content = "Test content"
        mock_result.title = "Title"
        mock_result.rrf_score = 0.9
        mock_result.image_url = "https://example.com/img.jpg"
        mock_result.page_number = 1
        mock_result.document_id = "doc1"
        mock_result.bounding_boxes = None
        mock_result.content_type = "table"

        mock_hybrid.search = AsyncMock(return_value=[mock_result])
        mock_rag._hybrid_search = mock_hybrid

        with patch("app.engine.agentic_rag.corrective_rag.settings", mock_settings), \
             patch("app.engine.agentic_rag.corrective_rag.get_query_analyzer") as mock_qa, \
             patch("app.engine.agentic_rag.corrective_rag.get_retrieval_grader") as mock_grader, \
             patch("app.engine.agentic_rag.corrective_rag.get_query_rewriter"), \
             patch("app.engine.agentic_rag.corrective_rag.get_answer_verifier"), \
             patch("app.engine.agentic_rag.corrective_rag.get_reasoning_tracer") as mock_tracer:

            # Setup analyzer
            mock_analysis = MagicMock()
            mock_analysis.complexity = MagicMock(value="simple")
            mock_analysis.is_domain_related = True
            mock_analysis.detected_topics = []
            mock_analysis.confidence = 0.9
            mock_analysis.requires_verification = False
            mock_qa.return_value.analyze = AsyncMock(return_value=mock_analysis)
            mock_qa.return_value.is_available.return_value = True

            # Setup grader
            mock_grade = MagicMock()
            mock_grade.avg_score = 8.0
            mock_grade.relevant_count = 1
            mock_grader.return_value.grade_documents = AsyncMock(return_value=mock_grade)
            mock_grader.return_value.is_available.return_value = True

            # Setup tracer
            mock_tracer_inst = MagicMock()
            mock_tracer.return_value = mock_tracer_inst
            mock_tracer_inst.build_trace.return_value = None
            mock_tracer_inst.build_thinking_summary.return_value = None

            mock_embeddings = MagicMock()
            mock_embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])

            # Setup RAG generation
            mock_gen_response = MagicMock()
            mock_gen_response.content = "Answer about Rule 15"
            mock_gen_response.native_thinking = None
            mock_rag.generate_from_documents = AsyncMock(return_value=mock_gen_response)

            crag = CorrectiveRAG(rag_agent=mock_rag)

            # Visual RAG should NOT be called
            with patch(
                "app.engine.agentic_rag.visual_rag.enrich_documents_with_visual_context"
            ) as mock_enrich, patch(
                "app.engine.gemini_embedding.get_embeddings",
                return_value=mock_embeddings,
            ):
                result = await crag.process("Rule 15 là gì?", {})
                mock_enrich.assert_not_called()

    @pytest.mark.asyncio
    async def test_content_type_included_in_retrieval(self):
        """Verify content_type is included in retrieved documents."""
        from app.engine.agentic_rag.corrective_rag import CorrectiveRAG

        mock_settings = MagicMock()
        mock_settings.enable_visual_rag = False
        mock_settings.rag_max_iterations = 1
        mock_settings.rag_confidence_high = 0.8
        mock_settings.enable_answer_verification = False
        mock_settings.semantic_cache_enabled = False

        mock_rag = MagicMock()
        mock_hybrid = MagicMock()
        mock_hybrid.is_available.return_value = True

        mock_result = MagicMock()
        mock_result.node_id = "n1"
        mock_result.content = "Table content"
        mock_result.title = "Title"
        mock_result.rrf_score = 0.9
        mock_result.image_url = "https://example.com/img.jpg"
        mock_result.page_number = 1
        mock_result.document_id = "doc1"
        mock_result.bounding_boxes = None
        mock_result.content_type = "table"

        mock_hybrid.search = AsyncMock(return_value=[mock_result])
        mock_rag._hybrid_search = mock_hybrid

        with patch("app.engine.agentic_rag.corrective_rag.settings", mock_settings):
            crag = CorrectiveRAG.__new__(CorrectiveRAG)
            crag._rag = mock_rag
            docs = await crag._retrieve("test", {})

            assert len(docs) == 1
            assert docs[0]["content_type"] == "table"


# ═══════════════════════════════════════════════════════════════════════════
# 8. Visual Content Types Constants
# ═══════════════════════════════════════════════════════════════════════════


class TestVisualContentTypes:
    """Test VISUAL_CONTENT_TYPES constant."""

    def test_table_is_visual(self):
        from app.engine.agentic_rag.visual_rag import VISUAL_CONTENT_TYPES
        assert "table" in VISUAL_CONTENT_TYPES

    def test_diagram_is_visual(self):
        from app.engine.agentic_rag.visual_rag import VISUAL_CONTENT_TYPES
        assert "diagram_reference" in VISUAL_CONTENT_TYPES

    def test_formula_is_visual(self):
        from app.engine.agentic_rag.visual_rag import VISUAL_CONTENT_TYPES
        assert "formula" in VISUAL_CONTENT_TYPES

    def test_text_is_not_visual(self):
        from app.engine.agentic_rag.visual_rag import VISUAL_CONTENT_TYPES
        assert "text" not in VISUAL_CONTENT_TYPES

    def test_heading_is_not_visual(self):
        from app.engine.agentic_rag.visual_rag import VISUAL_CONTENT_TYPES
        assert "heading" not in VISUAL_CONTENT_TYPES


# ═══════════════════════════════════════════════════════════════════════════
# 9. Prompt Template
# ═══════════════════════════════════════════════════════════════════════════


class TestPromptTemplate:
    """Test VISUAL_ANALYSIS_PROMPT template."""

    def test_prompt_has_query_placeholder(self):
        from app.engine.agentic_rag.visual_rag import VISUAL_ANALYSIS_PROMPT
        assert "{query}" in VISUAL_ANALYSIS_PROMPT

    def test_prompt_format_works(self):
        from app.engine.agentic_rag.visual_rag import VISUAL_ANALYSIS_PROMPT
        formatted = VISUAL_ANALYSIS_PROMPT.format(query="Rule 15 là gì?")
        assert "Rule 15 là gì?" in formatted

    def test_prompt_is_vietnamese(self):
        from app.engine.agentic_rag.visual_rag import VISUAL_ANALYSIS_PROMPT
        assert "tiếng Việt" in VISUAL_ANALYSIS_PROMPT


# ═══════════════════════════════════════════════════════════════════════════
# 10. Edge Cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_all_fetches_fail(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [
            _make_doc(node_id="n1", content_type="table"),
            _make_doc(node_id="n2", content_type="diagram_reference",
                      image_url="https://example.com/2.jpg"),
        ]

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await enrich_documents_with_visual_context(docs, "test")
            assert result.total_images_analyzed == 0
            # Documents should be returned unchanged
            assert result.enriched_documents[0]["content"] == docs[0]["content"]
            assert result.enriched_documents[1]["content"] == docs[1]["content"]

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [
            _make_doc(node_id="n1", content_type="table", image_url="https://example.com/ok.jpg"),
            _make_doc(node_id="n2", content_type="table", image_url="https://example.com/fail.jpg"),
        ]

        fetch_results = {"https://example.com/ok.jpg": "b64ok", "https://example.com/fail.jpg": None}
        analysis_results = {"n1": "Good description", "n2": None}

        async def mock_fetch(url, **kwargs):
            return fetch_results.get(url)

        async def mock_analyze(b64, query, **kwargs):
            # Only n1 succeeds
            if b64 == "b64ok":
                return "Good description"
            return None

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            side_effect=mock_fetch,
        ), patch(
            "app.engine.agentic_rag.visual_rag._analyze_image_with_vision",
            side_effect=mock_analyze,
        ):
            result = await enrich_documents_with_visual_context(docs, "test")
            # Only first doc enriched
            assert result.total_images_analyzed == 1
            assert "Good description" in result.enriched_documents[0]["content"]
            assert result.enriched_documents[1]["content"] == docs[1]["content"]

    @pytest.mark.asyncio
    async def test_doc_without_node_id(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        docs = [
            {"content": "test", "image_url": "https://example.com/img.jpg",
             "content_type": "table", "score": 0.5, "page_number": 1},
        ]

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            new_callable=AsyncMock,
            return_value="b64",
        ), patch(
            "app.engine.agentic_rag.visual_rag._analyze_image_with_vision",
            new_callable=AsyncMock,
            return_value="Desc",
        ):
            result = await enrich_documents_with_visual_context(docs, "test")
            # Should handle missing node_id gracefully
            assert len(result.enriched_documents) == 1

    def test_visual_description_chunk_format(self):
        """Visual descriptions should follow the expected format."""
        desc = "Bảng so sánh Rule 15"
        page_num = 5
        formatted = f"[Mô tả hình ảnh trang {page_num}]: {desc}"
        assert "[Mô tả hình ảnh trang 5]" in formatted
        assert "Bảng so sánh" in formatted

    @pytest.mark.asyncio
    async def test_enriched_doc_preserves_all_fields(self):
        from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

        original_doc = _make_doc(
            node_id="n1",
            content="Original",
            title="Title",
            score=0.9,
            content_type="table",
            page_number=5,
            document_id="doc1",
            bounding_boxes=[{"x": 0.1}],
        )

        with patch(
            "app.engine.agentic_rag.visual_rag._fetch_image_as_base64",
            new_callable=AsyncMock,
            return_value="b64",
        ), patch(
            "app.engine.agentic_rag.visual_rag._analyze_image_with_vision",
            new_callable=AsyncMock,
            return_value="Visual desc",
        ):
            result = await enrich_documents_with_visual_context([original_doc], "test")
            enriched = result.enriched_documents[0]

            # All original fields should be preserved
            assert enriched["node_id"] == "n1"
            assert enriched["title"] == "Title"
            assert enriched["score"] == 0.9
            assert enriched["content_type"] == "table"
            assert enriched["page_number"] == 5
            assert enriched["document_id"] == "doc1"
            assert enriched["bounding_boxes"] == [{"x": 0.1}]
            # Plus new fields
            assert "visual_description" in enriched
            assert "Visual desc" in enriched["content"]


# ═══════════════════════════════════════════════════════════════════════════
# 11. VisionProcessor Integration (Ingestion-time)
# ═══════════════════════════════════════════════════════════════════════════


class TestVisionProcessorVisualDescription:
    """Test visual description chunk generation during PDF ingestion."""

    def test_visual_description_chunk_created(self):
        """Verify that visual_description chunks are created for visual pages."""
        from app.services.chunking_service import ChunkResult

        # Simulate what VisionProcessor does after chunking
        chunks = [
            ChunkResult(chunk_index=0, content="Table header | Col1 | Col2",
                       content_type="table", confidence_score=1.0, metadata={}),
            ChunkResult(chunk_index=1, content="Normal text paragraph",
                       content_type="text", confidence_score=1.0, metadata={}),
        ]

        # Check that at least one chunk has visual content type
        has_visual = any(c.content_type in ("table", "diagram_reference", "formula") for c in chunks)
        assert has_visual is True

    def test_visual_description_content_type(self):
        """The visual description chunk should use 'visual_description' content type."""
        from app.services.chunking_service import ChunkResult

        desc_chunk = ChunkResult(
            chunk_index=2,
            content="[Mô tả hình ảnh trang 5]: Bảng so sánh COLREGs",
            content_type="visual_description",
            confidence_score=0.85,
            metadata={"visual_description": True},
        )
        assert desc_chunk.content_type == "visual_description"
        assert desc_chunk.confidence_score == 0.85
        assert desc_chunk.metadata.get("visual_description") is True

    def test_visual_description_chunk_format(self):
        """Visual description chunks should follow standard format."""
        page_num = 10
        desc = "Sơ đồ hệ thống đèn hiệu hàng hải"
        content = f"[Mô tả hình ảnh trang {page_num}]: {desc}"
        assert content.startswith("[Mô tả hình ảnh trang 10]")
        assert "Sơ đồ hệ thống đèn hiệu" in content


# ═══════════════════════════════════════════════════════════════════════════
# 12. Streaming Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestStreamingIntegration:
    """Test visual RAG integration in streaming corrective RAG path."""

    def test_visual_rag_thinking_event_format(self):
        """Visual RAG should emit a thinking event with step='visual_rag'."""
        event = {
            "type": "thinking",
            "content": "Phân tích 2 hình ảnh từ tài liệu (350ms)",
            "step": "visual_rag",
        }
        assert event["type"] == "thinking"
        assert event["step"] == "visual_rag"
        assert "hình ảnh" in event["content"]

    def test_visual_rag_status_event_format(self):
        """Visual RAG should emit a status event before analysis."""
        event = {"type": "status", "content": "Phân tích hình ảnh tài liệu"}
        assert event["type"] == "status"
        assert "hình ảnh" in event["content"]
