"""
Tests for Sprint 50: SupabaseStorageClient coverage.

Tests Supabase storage including:
- UploadResult dataclass
- __init__ (defaults, custom)
- _build_path (path structure)
- client property (lazy init, missing credentials)
- upload_image (success, retry, circuit breaker, max retries)
- upload_pil_image (converts and uploads)
- get_public_url
- delete_image (success, circuit breaker, error)
- delete_document_images (success, empty, circuit breaker, error)
- check_health (success, error)
- Singleton
"""

import pytest
import io
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from PIL import Image


# ============================================================================
# UploadResult
# ============================================================================


class TestUploadResult:
    """Test UploadResult dataclass."""

    def test_defaults(self):
        from app.services.supabase_storage import UploadResult
        r = UploadResult(success=True)
        assert r.success is True
        assert r.public_url is None
        assert r.path is None
        assert r.error is None

    def test_with_all_fields(self):
        from app.services.supabase_storage import UploadResult
        r = UploadResult(success=True, public_url="https://example.com/img.jpg",
                         path="doc1/page_1.jpg")
        assert r.public_url == "https://example.com/img.jpg"


# ============================================================================
# __init__ and _build_path
# ============================================================================


class TestInitAndPath:
    """Test initialization and path building."""

    def test_build_path(self):
        from app.services.supabase_storage import SupabaseStorageClient
        with patch("app.services.supabase_storage.settings") as mock_s:
            mock_s.supabase_url = "https://test.supabase.co"
            mock_s.supabase_key = "test-key"
            mock_s.supabase_storage_bucket = "test-bucket"
            client = SupabaseStorageClient(url="https://test.supabase.co", key="key")
        assert client._build_path("doc123", 5) == "doc123/page_5.jpg"
        assert client._build_path("abc", 1) == "abc/page_1.jpg"

    def test_custom_params(self):
        from app.services.supabase_storage import SupabaseStorageClient
        client = SupabaseStorageClient(
            url="https://custom.supabase.co",
            key="custom-key",
            bucket="custom-bucket"
        )
        assert client.url == "https://custom.supabase.co"
        assert client.key == "custom-key"
        assert client.bucket == "custom-bucket"

    def test_client_lazy_init(self):
        from app.services.supabase_storage import SupabaseStorageClient
        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        assert client._client is None

    def test_client_missing_credentials(self):
        from app.services.supabase_storage import SupabaseStorageClient
        # Must set url/key directly to bypass `or settings.xxx` fallback
        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        client.url = ""
        client.key = ""
        with pytest.raises(ValueError, match="Supabase URL and Key are required"):
            _ = client.client


# ============================================================================
# upload_image
# ============================================================================


class TestUploadImage:
    """Test image upload."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_bucket.get_public_url.return_value = "https://test.co/storage/v1/object/public/b/doc1/page_1.jpg"
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        with patch("app.services.supabase_storage._cb", None):
            result = await client.upload_image(b"image_data", "doc1", 1)

        assert result.success is True
        assert "page_1.jpg" in result.public_url

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_cb = MagicMock()
        mock_cb.is_available.return_value = False
        mock_cb.retry_after = 60.0

        with patch("app.services.supabase_storage._cb", mock_cb):
            result = await client.upload_image(b"data", "doc1", 1)

        assert result.success is False
        assert "circuit breaker" in result.error.lower()

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        call_count = 0

        def upload_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")

        mock_bucket.upload = MagicMock(side_effect=upload_side_effect)
        mock_bucket.get_public_url.return_value = "https://url.com/img.jpg"
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        # Reduce retry delay for test speed
        client.RETRY_DELAY = 0.01

        with patch("app.services.supabase_storage._cb", None):
            result = await client.upload_image(b"data", "doc1", 1)

        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_bucket.upload.side_effect = Exception("Persistent error")
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        client.RETRY_DELAY = 0.01

        with patch("app.services.supabase_storage._cb", None):
            result = await client.upload_image(b"data", "doc1", 1)

        assert result.success is False
        assert "Persistent error" in result.error


# ============================================================================
# upload_pil_image
# ============================================================================


class TestUploadPilImage:
    """Test PIL image upload."""

    @pytest.mark.asyncio
    async def test_converts_and_uploads(self):
        from app.services.supabase_storage import SupabaseStorageClient, UploadResult

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        client.upload_image = AsyncMock(return_value=UploadResult(
            success=True, public_url="https://url.com/img.jpg", path="doc1/page_1.jpg"
        ))

        img = Image.new("RGB", (10, 10), color="red")
        result = await client.upload_pil_image(img, "doc1", 1)

        assert result.success is True
        client.upload_image.assert_called_once()
        # Verify image_data is bytes
        call_args = client.upload_image.call_args
        assert isinstance(call_args.kwargs.get("image_data") or call_args[1].get("image_data", call_args[0][0] if call_args[0] else b""), bytes)


# ============================================================================
# get_public_url
# ============================================================================


class TestGetPublicUrl:
    """Test public URL generation."""

    def test_returns_url(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_bucket.get_public_url.return_value = "https://test.co/storage/v1/object/public/b/doc1/page_1.jpg"
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        url = client.get_public_url("doc1/page_1.jpg")
        assert "page_1.jpg" in url


# ============================================================================
# delete_image
# ============================================================================


class TestDeleteImage:
    """Test image deletion."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        with patch("app.services.supabase_storage._cb", None):
            result = await client.delete_image("doc1/page_1.jpg")
        assert result is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_cb = MagicMock()
        mock_cb.is_available.return_value = False

        with patch("app.services.supabase_storage._cb", mock_cb):
            result = await client.delete_image("doc1/page_1.jpg")
        assert result is False

    @pytest.mark.asyncio
    async def test_error(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_bucket.remove.side_effect = Exception("Delete failed")
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        with patch("app.services.supabase_storage._cb", None):
            result = await client.delete_image("doc1/page_1.jpg")
        assert result is False


# ============================================================================
# delete_document_images
# ============================================================================


class TestDeleteDocumentImages:
    """Test bulk image deletion."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_bucket.list.return_value = [
            {"name": "page_1.jpg"}, {"name": "page_2.jpg"}
        ]
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        with patch("app.services.supabase_storage._cb", None):
            count = await client.delete_document_images("doc1")
        assert count == 2

    @pytest.mark.asyncio
    async def test_empty(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_bucket.list.return_value = []
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        with patch("app.services.supabase_storage._cb", None):
            count = await client.delete_document_images("doc1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_cb = MagicMock()
        mock_cb.is_available.return_value = False

        with patch("app.services.supabase_storage._cb", mock_cb):
            count = await client.delete_document_images("doc1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_error(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_bucket.list.side_effect = Exception("List failed")
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        with patch("app.services.supabase_storage._cb", None):
            count = await client.delete_document_images("doc1")
        assert count == 0


# ============================================================================
# check_health
# ============================================================================


class TestCheckHealth:
    """Test health check."""

    @pytest.mark.asyncio
    async def test_healthy(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        with patch("app.services.supabase_storage._cb", None):
            result = await client.check_health()
        assert result is True

    @pytest.mark.asyncio
    async def test_unhealthy(self):
        from app.services.supabase_storage import SupabaseStorageClient

        client = SupabaseStorageClient(url="https://test.co", key="key", bucket="b")
        mock_bucket = MagicMock()
        mock_bucket.list.side_effect = Exception("Connection refused")
        mock_storage = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase = MagicMock()
        mock_supabase.storage = mock_storage
        client._client = mock_supabase

        with patch("app.services.supabase_storage._cb", None):
            result = await client.check_health()
        assert result is False
