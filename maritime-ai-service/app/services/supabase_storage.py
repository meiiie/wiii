"""
Backward-compatibility re-export — use app.services.object_storage instead.

This module re-exports all public names from object_storage.py so that
existing imports like `from app.services.supabase_storage import ...`
continue to work. New code should import from app.services.object_storage.
"""
# Re-export everything from the renamed module
from app.services.object_storage import (  # noqa: F401
    ObjectStorageClient,
    ObjectStorageClient as SupabaseStorageClient,  # deprecated alias
    UploadResult,
    get_storage_client,
    _cb,
)

# Allow patching at this path too
settings = None  # Sentinel — actual settings are in object_storage
try:
    from app.core.config import settings  # noqa: F811
except Exception:
    pass
