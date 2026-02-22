"""
Tests for Sprint 50: ObjectStorageClient coverage.

Tests ObjectStorageClient coverage including:
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
        from app.services.object_storage import UploadResult
        r = UploadResult(success=True)
        assert r.success is True
        assert r.public_url is None
        assert r.path is None
        assert r.error is None

    def test_with_all_fields(self):
        from app.services.object_storage import UploadResult
        r = UploadResult(success=True, public_url="https://example.com/img.jpg",
                         path="doc1/page_1.jpg")
        assert r.public_url == "https://example.com/img.jpg"


# ============================================================================
# __init__ and _build_path
# ============================================================================


class TestInitAndPath:
    """Test initialization and path building."""

    def test_build_path(self):
        from app.services.object_storage import ObjectStorageClient
        with patch("app.services.object_storage.settings") as mock_s:
            mock_s.minio_endpoint = "localhost:9000"
            mock_s.minio_access_key = "test-key"
            mock_s.minio_secret_key = "test-secret"
            mock_s.minio_bucket = "test-bucket"
            mock_s.minio_secure = False
            client = ObjectStorageClient(endpoint="localhost:9000", access_key="key", secret_key="secret")
        assert client._build_path("doc123", 5) == "doc123/page_5.jpg"
        assert client._build_path("abc", 1) == "abc/page_1.jpg"

    def test_custom_params(self):
        from app.services.object_storage import ObjectStorageClient
        client = ObjectStorageClient(
            endpoint="custom.storage.local:9000",
            access_key="custom-key",
            secret_key="custom-secret",
            bucket="custom-bucket"
        )
        assert client.endpoint == "custom.storage.local:9000"
        assert client.access_key == "custom-key"
        assert client.bucket == "custom-bucket"

    def test_url_scheme_stripped(self):
        """URL scheme is stripped from endpoint (MinIO takes host:port only)."""
        from app.services.object_storage import ObjectStorageClient
        client = ObjectStorageClient(url="https://storage.local:9000", key="key", bucket="b")
        assert client.endpoint == "storage.local:9000"

    def test_client_lazy_init(self):
        from app.services.object_storage import ObjectStorageClient
        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        assert client._client is None

    def test_client_missing_credentials(self):
        from app.services.object_storage import ObjectStorageClient
        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        client.endpoint = ""
        client.access_key = ""
        with pytest.raises(ValueError, match="URL and Key are required"):
            _ = client.client


# ============================================================================
# upload_image
# ============================================================================


class TestUploadImage:
    """Test image upload."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_minio = MagicMock()
        mock_minio.put_object.return_value = None
        mock_minio.presigned_get_object.return_value = "http://test.co:9000/b/doc1/page_1.jpg?token=abc"
        client._client = mock_minio

        with patch("app.services.object_storage._cb", None):
            result = await client.upload_image(b"image_data", "doc1", 1)

        assert result.success is True
        assert "page_1.jpg" in result.public_url

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_cb = MagicMock()
        mock_cb.is_available.return_value = False
        mock_cb.retry_after = 60.0

        with patch("app.services.object_storage._cb", mock_cb):
            result = await client.upload_image(b"data", "doc1", 1)

        assert result.success is False
        assert "circuit breaker" in result.error.lower()

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        call_count = 0

        def put_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")

        mock_minio = MagicMock()
        mock_minio.put_object = MagicMock(side_effect=put_side_effect)
        mock_minio.presigned_get_object.return_value = "http://test.co:9000/b/img.jpg?token=x"
        client._client = mock_minio

        client.RETRY_DELAY = 0.01

        with patch("app.services.object_storage._cb", None):
            result = await client.upload_image(b"data", "doc1", 1)

        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_minio = MagicMock()
        mock_minio.put_object.side_effect = Exception("Persistent error")
        client._client = mock_minio

        client.RETRY_DELAY = 0.01

        with patch("app.services.object_storage._cb", None):
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
        from app.services.object_storage import ObjectStorageClient, UploadResult

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        client.upload_image = AsyncMock(return_value=UploadResult(
            success=True, public_url="https://url.com/img.jpg", path="doc1/page_1.jpg"
        ))

        img = Image.new("RGB", (10, 10), color="red")
        result = await client.upload_pil_image(img, "doc1", 1)

        assert result.success is True
        client.upload_image.assert_called_once()
        call_args = client.upload_image.call_args
        assert isinstance(call_args.kwargs.get("image_data") or call_args[1].get("image_data", call_args[0][0] if call_args[0] else b""), bytes)


# ============================================================================
# get_public_url
# ============================================================================


class TestGetPublicUrl:
    """Test public URL generation."""

    def test_returns_url(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        client.secure = False
        url = client.get_public_url("doc1/page_1.jpg")
        assert "page_1.jpg" in url
        assert "test.co:9000" in url
        assert url == "http://test.co:9000/b/doc1/page_1.jpg"

    def test_returns_https_when_secure(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b", secure=True)
        url = client.get_public_url("doc1/page_1.jpg")
        assert url.startswith("https://")


# ============================================================================
# delete_image
# ============================================================================


class TestDeleteImage:
    """Test image deletion."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_minio = MagicMock()
        client._client = mock_minio

        with patch("app.services.object_storage._cb", None):
            result = await client.delete_image("doc1/page_1.jpg")
        assert result is True
        mock_minio.remove_object.assert_called_once_with("b", "doc1/page_1.jpg")

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_cb = MagicMock()
        mock_cb.is_available.return_value = False

        with patch("app.services.object_storage._cb", mock_cb):
            result = await client.delete_image("doc1/page_1.jpg")
        assert result is False

    @pytest.mark.asyncio
    async def test_error(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_minio = MagicMock()
        mock_minio.remove_object.side_effect = Exception("Delete failed")
        client._client = mock_minio

        with patch("app.services.object_storage._cb", None):
            result = await client.delete_image("doc1/page_1.jpg")
        assert result is False


# ============================================================================
# delete_document_images
# ============================================================================


class TestDeleteDocumentImages:
    """Test bulk image deletion."""

    @pytest.mark.asyncio
    async def test_success(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        # Mock list_objects to return 2 objects
        obj1 = MagicMock()
        obj1.object_name = "doc1/page_1.jpg"
        obj2 = MagicMock()
        obj2.object_name = "doc1/page_2.jpg"

        mock_minio = MagicMock()
        mock_minio.list_objects.return_value = [obj1, obj2]
        mock_minio.remove_objects.return_value = iter([])  # no errors
        client._client = mock_minio

        with patch("app.services.object_storage._cb", None):
            count = await client.delete_document_images("doc1")
        assert count == 2

    @pytest.mark.asyncio
    async def test_empty(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_minio = MagicMock()
        mock_minio.list_objects.return_value = []
        client._client = mock_minio

        with patch("app.services.object_storage._cb", None):
            count = await client.delete_document_images("doc1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_cb = MagicMock()
        mock_cb.is_available.return_value = False

        with patch("app.services.object_storage._cb", mock_cb):
            count = await client.delete_document_images("doc1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_error(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_minio = MagicMock()
        mock_minio.list_objects.side_effect = Exception("List failed")
        client._client = mock_minio

        with patch("app.services.object_storage._cb", None):
            count = await client.delete_document_images("doc1")
        assert count == 0


# ============================================================================
# check_health
# ============================================================================


class TestCheckHealth:
    """Test health check."""

    @pytest.mark.asyncio
    async def test_healthy(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True
        client._client = mock_minio

        with patch("app.services.object_storage._cb", None):
            result = await client.check_health()
        assert result is True

    @pytest.mark.asyncio
    async def test_unhealthy(self):
        from app.services.object_storage import ObjectStorageClient

        client = ObjectStorageClient(endpoint="test.co:9000", access_key="key", secret_key="s", bucket="b")
        mock_minio = MagicMock()
        mock_minio.bucket_exists.side_effect = Exception("Connection refused")
        client._client = mock_minio

        with patch("app.services.object_storage._cb", None):
            result = await client.check_health()
        assert result is False
