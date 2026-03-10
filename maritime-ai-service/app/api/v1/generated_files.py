"""Serve generated user-facing artifacts from the workspace."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.generated_files import (
    generated_file_disposition,
    get_generated_dir,
    guess_generated_media_type,
    is_allowed_generated_file,
)

router = APIRouter(prefix="/generated-files", tags=["generated-files"])


def _build_generated_file_response(filename: str) -> FileResponse:
    """Build the response for a generated file download/preview."""
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=404, detail="File not found")

    if not is_allowed_generated_file(safe_name):
        raise HTTPException(status_code=404, detail="File not found")

    media_type = guess_generated_media_type(safe_name)
    filepath = get_generated_dir() / safe_name
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=filepath,
        media_type=media_type,
        filename=safe_name,
        content_disposition_type=generated_file_disposition(safe_name),
    )


@router.get("/{filename}")
async def download_generated_file(filename: str) -> FileResponse:
    """Download a generated file by its basename only."""
    return _build_generated_file_response(filename)


@router.head("/{filename}", include_in_schema=False)
async def head_generated_file(filename: str) -> FileResponse:
    """Support HEAD probes for generated files without duplicating schema noise."""
    return _build_generated_file_response(filename)
