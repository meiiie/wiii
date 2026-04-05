"""Artifact harvesting helpers for OpenSandboxExecutor."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import PurePosixPath
from typing import Any, Optional

from app.core.generated_files import build_generated_file_url


def collect_artifacts_impl(
    *,
    execution: Any,
    sandbox: Any,
    request,
    sdk,
    extract_execution_artifacts_fn,
    harvest_sandbox_files_fn,
    max_harvested_artifacts: int,
) -> list:
    artifacts: list = []
    seen_keys: set[tuple[str, str]] = set()

    def _add_artifact(item) -> None:
        if item is None:
            return
        key = (
            (item.path or item.url or item.name).lower(),
            (item.content_type or "").lower(),
        )
        if key in seen_keys:
            return
        seen_keys.add(key)
        artifacts.append(item)

    for candidate in extract_execution_artifacts_fn(execution):
        _add_artifact(candidate)
        if len(artifacts) >= max_harvested_artifacts:
            return artifacts

    return _finish_harvested_artifacts(
        artifacts=artifacts,
        sandbox=sandbox,
        request=request,
        sdk=sdk,
        add_artifact_fn=_add_artifact,
        harvest_sandbox_files_fn=harvest_sandbox_files_fn,
        max_harvested_artifacts=max_harvested_artifacts,
    )


async def _finish_harvested_artifacts(
    *,
    artifacts: list,
    sandbox: Any,
    request,
    sdk,
    add_artifact_fn,
    harvest_sandbox_files_fn,
    max_harvested_artifacts: int,
) -> list:
    for candidate in await harvest_sandbox_files_fn(
        sandbox=sandbox,
        request=request,
        sdk=sdk,
    ):
        add_artifact_fn(candidate)
        if len(artifacts) >= max_harvested_artifacts:
            break
    return artifacts


def coerce_execution_artifact_impl(
    item: Any,
    *,
    read_field_fn,
    guess_content_type_fn,
    filename_from_ref_fn,
    sandbox_artifact_cls,
    attach_inline_content_fn,
) -> Optional[Any]:
    path = read_field_fn(item, "path", "file_path")
    name = read_field_fn(item, "name", "filename")
    url = read_field_fn(item, "url", "download_url")
    content_type = (
        read_field_fn(item, "content_type", "mime_type")
        or guess_content_type_fn(path or name or url)
    )
    inline_content = read_field_fn(item, "content", "data", "body", "bytes")

    if not any([path, name, url, inline_content]):
        return None
    if inline_content is None and not any([path, name, url]):
        return None

    normalized_name = name or filename_from_ref_fn(path or url) or "artifact"
    artifact = sandbox_artifact_cls(
        name=normalized_name,
        content_type=content_type or "application/octet-stream",
        url=str(url) if url else None,
        path=str(path) if path else None,
        metadata={"harvest_source": "execution_payload"},
    )

    attach_inline_content_fn(artifact, inline_content, normalized_name)
    size_bytes = read_field_fn(item, "size", "size_bytes")
    if size_bytes is not None:
        artifact.metadata["size_bytes"] = size_bytes
    return artifact


async def harvest_sandbox_files_impl(
    *,
    sandbox: Any,
    request,
    sdk,
    normalize_path_fn,
    build_search_roots_fn,
    read_field_fn,
    build_sandbox_file_artifact_fn,
    artifact_glob_patterns,
    max_harvested_artifacts: int,
    logger: logging.Logger,
) -> list:
    files_api = getattr(sandbox, "files", None)
    if files_api is None or not hasattr(files_api, "search"):
        return []

    staged_paths = {normalize_path_fn(path) for path in request.files}
    roots = build_search_roots_fn(request.working_directory)
    discovered: list = []
    seen_paths: set[str] = set()

    for root in roots:
        for pattern in artifact_glob_patterns:
            if len(discovered) >= max_harvested_artifacts:
                return discovered
            try:
                results = await files_api.search(
                    sdk.search_entry(path=root, pattern=pattern, recursive=True)
                    if getattr(sdk, "search_entry", None)
                    else {"path": root, "pattern": pattern}
                )
            except TypeError:
                try:
                    results = await files_api.search(
                        sdk.search_entry(path=root, pattern=pattern)
                    )
                except Exception as exc:
                    logger.debug(
                        "[OPENSANDBOX] artifact search failed for %s %s: %s",
                        root,
                        pattern,
                        exc,
                    )
                    continue
            except Exception as exc:
                logger.debug(
                    "[OPENSANDBOX] artifact search failed for %s %s: %s",
                    root,
                    pattern,
                    exc,
                )
                continue

            for entry in results or []:
                path = normalize_path_fn(read_field_fn(entry, "path", "file_path"))
                if not path or path in staged_paths or path in seen_paths:
                    continue
                seen_paths.add(path)
                artifact = await build_sandbox_file_artifact_fn(
                    files_api=files_api,
                    path=path,
                )
                if artifact is not None:
                    discovered.append(artifact)
                    if len(discovered) >= max_harvested_artifacts:
                        return discovered

    return discovered


async def build_sandbox_file_artifact_impl(
    *,
    files_api: Any,
    path: str,
    guess_content_type_fn,
    sandbox_artifact_cls,
    read_sandbox_file_content_fn,
    publish_harvested_file_fn,
    should_inline_file_fn,
    attach_inline_content_fn,
    filename_from_ref_fn,
) -> Optional[Any]:
    content_type = guess_content_type_fn(path)
    artifact = sandbox_artifact_cls(
        name=filename_from_ref_fn(path) or "artifact",
        content_type=content_type,
        path=path,
        metadata={
            "harvest_source": "sandbox_filesystem",
            "sandbox_path": path,
        },
    )

    raw_content = await read_sandbox_file_content_fn(
        files_api=files_api,
        path=path,
    )
    published = publish_harvested_file_fn(artifact.name, raw_content)
    if published is not None:
        artifact.path = str(published)
        artifact.url = build_generated_file_url(published.name)
        artifact.metadata["published_from_sandbox"] = True

    if should_inline_file_fn(content_type, path):
        attach_inline_content_fn(artifact, raw_content, artifact.name)
    return artifact


async def read_sandbox_file_content_impl(
    *,
    files_api: Any,
    path: str,
    logger: logging.Logger,
) -> Any:
    if hasattr(files_api, "read_bytes"):
        try:
            return await files_api.read_bytes(path)
        except Exception as exc:
            logger.debug("[OPENSANDBOX] artifact read_bytes failed for %s: %s", path, exc)

    if hasattr(files_api, "read_file"):
        try:
            return await files_api.read_file(path)
        except Exception as exc:
            logger.debug("[OPENSANDBOX] artifact read_file failed for %s: %s", path, exc)
    return None


def attach_inline_content_impl(
    artifact,
    raw_content: Any,
    fallback_name: str,
    *,
    guess_content_type_fn,
    is_image_content_fn,
    encode_inline_image_fn,
    coerce_text_content_fn,
    text_inline_limit: int,
) -> None:
    if raw_content is None:
        return

    content_type = artifact.content_type or guess_content_type_fn(fallback_name)
    if is_image_content_fn(content_type):
        encoded = encode_inline_image_fn(raw_content)
        if encoded:
            artifact.metadata["inline_content"] = encoded
            artifact.metadata["inline_encoding"] = "base64"
        return

    text = coerce_text_content_fn(raw_content)
    if text is None:
        return
    if len(text) > text_inline_limit:
        artifact.metadata["inline_content"] = text[:text_inline_limit]
        artifact.metadata["content_truncated"] = True
    else:
        artifact.metadata["inline_content"] = text
    artifact.metadata["inline_encoding"] = "text"


def should_inline_file_impl(content_type: str, path: str, *, is_image_content_fn) -> bool:
    if is_image_content_fn(content_type):
        return True
    return (
        content_type.startswith("text/")
        or content_type in {
            "application/json",
            "text/csv",
            "application/csv",
            "image/svg+xml",
        }
        or PurePosixPath(path).suffix.lower()
        in {".html", ".htm", ".md", ".txt", ".json", ".csv", ".svg"}
    )


def guess_content_type(ref: Optional[str]) -> str:
    guessed, _ = mimetypes.guess_type(ref or "")
    return guessed or "application/octet-stream"


def filename_from_ref(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    try:
        return PurePosixPath(str(ref)).name or None
    except Exception:
        return str(ref).rsplit("/", 1)[-1] or None


def encode_inline_image(raw_content: Any, *, image_inline_limit: int) -> Optional[str]:
    if raw_content is None:
        return None
    if isinstance(raw_content, str):
        return raw_content if len(raw_content) <= image_inline_limit else None
    if isinstance(raw_content, (bytes, bytearray)):
        if len(raw_content) > image_inline_limit:
            return None
        return base64.b64encode(bytes(raw_content)).decode("ascii")
    return None
