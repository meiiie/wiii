"""
Object Storage Client for Multimodal RAG — MinIO / S3-compatible backend.

CHỈ THỊ KỸ THUẬT SỐ 26: Hybrid Infrastructure
Handles image upload/download to object storage bucket for Evidence Images.

Uses the official MinIO Python SDK to communicate with MinIO in
local/dev and any S3-compatible backend in production.

**Feature: multimodal-rag-vision**
**Validates: Requirements 2.2, 2.3, 4.3**
"""
import asyncio
import io
import logging
from datetime import timedelta
from typing import Optional
from dataclasses import dataclass

from minio import Minio
from PIL import Image

from app.core.config import settings

try:
    from app.core.resilience import get_circuit_breaker
    _cb = get_circuit_breaker("object_storage", failure_threshold=5, recovery_timeout=120)
except Exception:
    _cb = None

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of image upload operation"""
    success: bool
    public_url: Optional[str] = None
    path: Optional[str] = None
    error: Optional[str] = None


class ObjectStorageClient:
    """
    Client for S3-compatible object storage operations (MinIO / S3).

    Handles image upload/download for the Multimodal RAG pipeline.
    Images are stored in the configured storage bucket.

    Path structure: {document_id}/page_{number}.jpg
    """

    BUCKET_NAME = settings.minio_bucket
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
    UPLOAD_TIMEOUT = 30.0  # seconds per attempt
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: Optional[bool] = None,
        # Legacy params for backward-compat with tests
        url: Optional[str] = None,
        key: Optional[str] = None,
    ):
        """
        Initialize object storage client.

        Args:
            endpoint: MinIO endpoint (host:port, no scheme)
            access_key: MinIO access key
            secret_key: MinIO secret key
            bucket: Storage bucket name
            secure: Use HTTPS (default from settings)
            url: Deprecated alias for endpoint (backward compat)
            key: Deprecated alias for access_key (backward compat)
        """
        # Resolve endpoint: new params → legacy params → settings
        raw_endpoint = endpoint or url or settings.minio_endpoint or ""
        # Strip scheme if present (MinIO SDK takes host:port only)
        self.endpoint = raw_endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        self.access_key = access_key or key or settings.minio_access_key or ""
        self.secret_key = secret_key or settings.minio_secret_key or ""
        self.bucket = bucket or settings.minio_bucket or self.BUCKET_NAME
        self.secure = secure if secure is not None else settings.minio_secure

        # External endpoint for browser-facing presigned URLs
        # In Docker: internal=minio:9000, external=localhost:9000
        raw_external = settings.minio_external_endpoint or ""
        self.external_endpoint = (
            raw_external.replace("https://", "").replace("http://", "").rstrip("/")
            if raw_external else ""
        )

        # Legacy compat — some tests/callers check .url and .key
        self.url = raw_endpoint
        self.key = self.access_key

        self._client: Optional[Minio] = None

    @property
    def client(self) -> Minio:
        """Lazy initialization of MinIO client"""
        if self._client is None:
            if not self.endpoint or not self.access_key:
                raise ValueError(
                    "Storage URL and Key are required. "
                    "Set MINIO_ENDPOINT and MINIO_ACCESS_KEY environment variables."
                )
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        return self._client

    def _build_path(self, document_id: str, page_number: int) -> str:
        """
        Build storage path for an image.

        Sprint 171: Org-scoped paths when multi-tenant enabled.
        Path structure:
        - Multi-tenant: {org_id}/{document_id}/page_{number}.jpg
        - Single-tenant: {document_id}/page_{number}.jpg

        **Property 9: Storage Folder Structure**
        """
        org_prefix = self._get_org_prefix()
        if org_prefix:
            return f"{org_prefix}/{document_id}/page_{page_number}.jpg"
        return f"{document_id}/page_{page_number}.jpg"

    @staticmethod
    def _get_org_prefix() -> str:
        """Get org_id prefix for storage paths (empty string when disabled)."""
        try:
            from app.core.org_filter import get_effective_org_id
            org_id = get_effective_org_id()
            if org_id and org_id != "default":
                return org_id
        except Exception:
            pass
        return ""

    async def upload_image(
        self,
        image_data: bytes,
        document_id: str,
        page_number: int,
        content_type: str = "image/jpeg"
    ) -> UploadResult:
        """
        Upload image to object storage with circuit breaker + retry logic.

        Args:
            image_data: Image bytes to upload
            document_id: Document identifier
            page_number: Page number in the document
            content_type: MIME type of the image

        Returns:
            UploadResult with success status and public URL
        """
        # Validate upload size
        if len(image_data) > self.MAX_UPLOAD_SIZE:
            return UploadResult(
                success=False,
                error=f"Upload too large: {len(image_data)} bytes (max {self.MAX_UPLOAD_SIZE})",
            )

        # Validate content type
        if content_type not in self.ALLOWED_CONTENT_TYPES:
            return UploadResult(
                success=False,
                error=f"Unsupported content type: {content_type}",
            )

        # Circuit breaker: fail fast when storage is known to be down
        if _cb is not None and not _cb.is_available():
            logger.warning(
                "[STORAGE] Circuit breaker open, skipping upload for %s",
                document_id,
            )
            return UploadResult(
                success=False,
                error=f"Storage circuit breaker open (retry in {_cb.retry_after:.0f}s)"
            )

        path = self._build_path(document_id, page_number)
        last_error: Optional[str] = None

        for attempt in range(self.MAX_RETRIES):
            try:
                data_stream = io.BytesIO(image_data)
                data_len = len(image_data)

                # Upload with timeout to prevent hanging on slow connections
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.client.put_object(
                            self.bucket,
                            path,
                            data_stream,
                            data_len,
                            content_type=content_type,
                        ),
                    ),
                    timeout=self.UPLOAD_TIMEOUT,
                )

                # Use stable public URL (no expiry) for DB storage.
                # Presigned URLs expire after 1h — unsuitable for permanent storage.
                # MinIO bucket has public-read policy (mc anonymous set download).
                public_url = self.get_public_url(path)

                logger.info("Uploaded image to %s, URL: %s", path, public_url)

                if _cb is not None:
                    await _cb.record_success()

                return UploadResult(
                    success=True,
                    public_url=public_url,
                    path=path
                )

            except asyncio.TimeoutError:
                last_error = f"Upload timeout after {self.UPLOAD_TIMEOUT}s"
                logger.warning(
                    "Upload attempt %d/%d timed out for %s",
                    attempt + 1, self.MAX_RETRIES, path,
                )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Upload attempt %d/%d failed: %s",
                    attempt + 1, self.MAX_RETRIES, e,
                )

            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
            else:
                logger.error("Failed to upload image after %d attempts", self.MAX_RETRIES)
                if _cb is not None:
                    await _cb.record_failure()
                return UploadResult(
                    success=False,
                    error=last_error
                )

        return UploadResult(success=False, error="Max retries exceeded")

    async def upload_pil_image(
        self,
        image: Image.Image,
        document_id: str,
        page_number: int,
        quality: int = 85
    ) -> UploadResult:
        """
        Upload PIL Image to object storage.

        Args:
            image: PIL Image object
            document_id: Document identifier
            page_number: Page number in the document
            quality: JPEG quality (1-100)

        Returns:
            UploadResult with success status and public URL
        """
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality)
        image_data = buffer.getvalue()

        return await self.upload_image(
            image_data=image_data,
            document_id=document_id,
            page_number=page_number
        )

    def get_public_url(self, path: str) -> str:
        """
        Build public URL for a stored file.

        Args:
            path: Storage path of the file

        Returns:
            Public URL string (constructed from endpoint + bucket + path)
        """
        scheme = "https" if self.secure else "http"
        host = self.external_endpoint or self.endpoint
        return f"{scheme}://{host}/{self.bucket}/{path}"

    def _rewrite_url_for_browser(self, url: str) -> str:
        """Rewrite internal Docker hostname to external endpoint for browser access."""
        if self.external_endpoint and self.endpoint != self.external_endpoint:
            return url.replace(self.endpoint, self.external_endpoint, 1)
        return url

    def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """
        Get a time-limited presigned URL for a stored file.

        Args:
            path: Storage path of the file
            expires_in: URL validity in seconds (default 1 hour)

        Returns:
            Presigned URL string, falls back to public URL on error.
        """
        try:
            url = self.client.presigned_get_object(
                self.bucket,
                path,
                expires=timedelta(seconds=expires_in),
            )
            return self._rewrite_url_for_browser(url)
        except Exception as e:
            logger.warning("Presigned URL failed, falling back to public: %s", e)
            return self.get_public_url(path)

    async def delete_image(self, path: str) -> bool:
        """
        Delete image from storage.

        Args:
            path: Storage path of the file

        Returns:
            True if deletion was successful
        """
        if _cb is not None and not _cb.is_available():
            logger.warning("[STORAGE] Circuit breaker open, skipping delete")
            return False

        try:
            self.client.remove_object(self.bucket, path)
            logger.info("Deleted image: %s", path)
            if _cb is not None:
                await _cb.record_success()
            return True
        except Exception as e:
            logger.error("Failed to delete image %s: %s", path, e)
            if _cb is not None:
                await _cb.record_failure()
            return False

    async def delete_document_images(self, document_id: str) -> int:
        """
        Delete all images for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of images deleted
        """
        if _cb is not None and not _cb.is_available():
            logger.warning("[STORAGE] Circuit breaker open, skipping bulk delete")
            return 0

        try:
            objects = list(self.client.list_objects(self.bucket, prefix=f"{document_id}/"))

            if not objects:
                return 0

            from minio.deleteobjects import DeleteObject
            delete_list = [DeleteObject(obj.object_name) for obj in objects]
            errors = list(self.client.remove_objects(self.bucket, delete_list))

            count = len(delete_list) - len(errors)
            logger.info("Deleted %d images for document %s", count, document_id)
            if _cb is not None:
                await _cb.record_success()
            return count

        except Exception as e:
            logger.error("Failed to delete document images %s: %s", document_id, e)
            if _cb is not None:
                await _cb.record_failure()
            return 0

    async def check_health(self) -> bool:
        """
        Check if object storage is accessible.

        Returns:
            True if storage is healthy
        """
        try:
            self.client.bucket_exists(self.bucket)
            if _cb is not None:
                await _cb.record_success()
            return True
        except Exception as e:
            logger.error("Object storage health check failed: %s", e)
            if _cb is not None:
                await _cb.record_failure()
            return False


# Singleton instance
_storage_client: Optional[ObjectStorageClient] = None


def get_storage_client() -> ObjectStorageClient:
    """Get or create singleton ObjectStorageClient instance"""
    global _storage_client
    if _storage_client is None:
        _storage_client = ObjectStorageClient()
    return _storage_client
