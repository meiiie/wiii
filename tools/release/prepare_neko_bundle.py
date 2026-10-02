"""Prepare the reviewed Neko artifact; never execute downloads or update the lock."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import BinaryIO
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "wiii-desktop/src-tauri/neko-bundle.lock.json"
DESTINATION = ROOT / "wiii-desktop/.build/neko-bundle"
REPOSITORY = "https://github.com/meiiie/neko-core"
TARGETS = {
    "windows-x64": "neko-windows-x64.exe",
    "linux-x64": "neko-linux-x64",
    "linux-arm64": "neko-linux-arm64",
    "macos-x64": "neko-macos-x64",
    "macos-arm64": "neko-macos-arm64",
}
MAX_BYTES = 128 * 1024 * 1024


class HttpsRedirectsOnly(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise ValueError("Neko download redirect must remain HTTPS")
        return super().redirect_request(request, fp, code, message, headers, newurl)


def manifest_for(lock: dict, target: str) -> dict:
    if target not in TARGETS:
        raise ValueError("unsupported Neko target")
    if lock.get("repository") != REPOSITORY:
        raise ValueError("unexpected Neko source repository")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?", lock.get("version", "")):
        raise ValueError("invalid pinned Neko version")
    if not re.fullmatch(r"[0-9a-f]{40}", lock.get("commit", "")):
        raise ValueError("invalid pinned Neko source commit")
    artifact = lock.get("artifacts", {}).get(target, {})
    size = artifact.get("size")
    if artifact.get("asset") != TARGETS[target]:
        raise ValueError("unexpected Neko artifact name")
    if type(size) is not int or not 0 < size < MAX_BYTES:
        raise ValueError("invalid Neko artifact size")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact.get("sha256", "")):
        raise ValueError("invalid Neko artifact SHA-256")
    return {"schema_version": 1, "version": lock["version"], "commit": lock["commit"],
            "repository": REPOSITORY, "target": target, **artifact}


def copy_verified(source: BinaryIO, output: BinaryIO, manifest: dict) -> None:
    """Bound bytes and time even when a remote server omits Content-Length."""
    digest = hashlib.sha256()
    received = 0
    deadline = time.monotonic() + 180
    while chunk := source.read(1024 * 1024):
        received += len(chunk)
        if received > manifest["size"] or time.monotonic() > deadline:
            raise ValueError("Neko artifact exceeded its pinned size or download deadline")
        digest.update(chunk)
        output.write(chunk)
    if received != manifest["size"] or digest.hexdigest() != manifest["sha256"]:
        raise ValueError("Neko artifact failed pinned size/SHA-256 verification")


def executable_name(target: str) -> str:
    return "neko.exe" if target.startswith("windows-") else "neko"


def check_bundle(destination: Path, manifest: dict) -> None:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("Neko bundle directory is missing or is a symlink")
    record = destination / "bundle.json"
    binary = destination / executable_name(manifest["target"])
    for path in (record, binary, destination / "LICENSE", destination / "SOURCE.txt"):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Neko bundle contains a missing or symlinked file")
    if record.stat().st_size > 8192 or json.loads(record.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Neko bundle record differs from the pinned target")
    if binary.stat().st_size != manifest["size"]:
        raise ValueError("Neko bundle executable has the wrong size")
    with binary.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256"]:
            raise ValueError("Neko bundle executable has the wrong SHA-256")
    if not manifest["target"].startswith("windows-") and not binary.stat().st_mode & 0o111:
        raise ValueError("Neko bundle executable has no execute permission")


def prepare(lock: dict, target: str, destination: Path, artifact: Path | None = None) -> dict:
    manifest = manifest_for(lock, target)
    if destination.exists() or destination.is_symlink():
        # Do not silently replace another target, partial preparation or corrupt
        # data. Build output is disposable, but only its owner may choose that.
        check_bundle(destination, manifest)
        return manifest
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".neko-stage-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "bundle"
        stage.mkdir()
        binary = stage / executable_name(target)
        url = f'{REPOSITORY}/releases/download/v{manifest["version"]}/{manifest["asset"]}'
        source = artifact.open("rb") if artifact else build_opener(HttpsRedirectsOnly()).open(url, timeout=30)
        with source, binary.open("xb") as output:
            if not artifact and not source.geturl().startswith("https://"):
                raise ValueError("Neko download redirected away from HTTPS")
            copy_verified(source, output, manifest)
        binary.chmod(0o755)
        (stage / "bundle.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        # Keep distribution notices and the exact corresponding-source reference
        # in the package. This is not a claim that checksum equals provenance.
        shutil.copyfile(ROOT / "LICENSE", stage / "LICENSE")
        (stage / "SOURCE.txt").write_text(
            f'Neko Core {manifest["version"]}\nLicense: AGPL-3.0-only\n'
            f'{REPOSITORY}/tree/{manifest["commit"]}\n', encoding="utf-8")
        check_bundle(stage, manifest)
        # Same-filesystem rename publishes only a complete verified directory.
        # A concurrent winner is accepted only if it matches this exact lock.
        try:
            stage.rename(destination)
        except OSError:
            if not destination.exists():
                raise
            check_bundle(destination, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=TARGETS)
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--destination", type=Path, default=DESTINATION)
    parser.add_argument("--artifact", type=Path, help="Offline artifact; still verified against the lock")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    manifest = manifest_for(lock, args.target)
    if args.check_only:
        check_bundle(args.destination, manifest)
    else:
        prepare(lock, args.target, args.destination, args.artifact)
    print(f'Neko bundle verified: {args.target}, {manifest["version"]}, {manifest["sha256"]}')


if __name__ == "__main__":
    main()
