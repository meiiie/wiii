"""Offline package-contract tests: synthetic bytes, no downloads or execution."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import Request

from tools.release import prepare_neko_bundle as bundle


class NekoBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = b"synthetic executable fixture, never executed\n"
        self.source = self.root / "artifact"
        self.source.write_bytes(self.payload)
        self.lock = {"version": "1.5.1", "commit": "a" * 40,
                     "repository": bundle.REPOSITORY, "artifacts": {
                         target: {"asset": name, "size": len(self.payload),
                                  "sha256": hashlib.sha256(self.payload).hexdigest()}
                         for target, name in bundle.TARGETS.items()}}

    def test_all_published_targets_have_verified_layout_and_notices(self):
        for target in bundle.TARGETS:
            with self.subTest(target=target):
                destination = self.root / target
                manifest = bundle.prepare(self.lock, target, destination, self.source)
                bundle.check_bundle(destination, manifest)
                self.assertEqual((destination / bundle.executable_name(target)).read_bytes(), self.payload)
                self.assertTrue((destination / "LICENSE").is_file())
                self.assertIn(self.lock["commit"], (destination / "SOURCE.txt").read_text())

    def test_valid_bundle_reuse_needs_no_source_or_network(self):
        destination = self.root / "bundle"
        first = bundle.prepare(self.lock, "linux-x64", destination, self.source)
        self.assertEqual(bundle.prepare(self.lock, "linux-x64", destination, self.root / "absent"), first)

    def test_corrupt_short_and_oversized_inputs_never_publish(self):
        for payload in [b"", self.payload[:-1], b"x" * len(self.payload), self.payload + b"x"]:
            with self.subTest(payload_size=len(payload)):
                self.source.write_bytes(payload)
                with self.assertRaises(ValueError):
                    bundle.prepare(self.lock, "linux-x64", self.root / "bundle", self.source)
                self.assertFalse((self.root / "bundle").exists())
                self.assertFalse(list(self.root.glob(".neko-stage-*")))

    def test_partial_or_wrong_target_destination_is_preserved_and_rejected(self):
        destination = self.root / "bundle"
        bundle.prepare(self.lock, "linux-x64", destination, self.source)
        original = (destination / "bundle.json").read_bytes()
        with self.assertRaises(ValueError):
            bundle.prepare(self.lock, "linux-arm64", destination, self.source)
        self.assertEqual((destination / "bundle.json").read_bytes(), original)
        (destination / "neko").write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            bundle.prepare(self.lock, "linux-x64", destination, self.source)
        self.assertEqual((destination / "neko").read_bytes(), b"corrupt")

    def test_manifest_changes_are_detected(self):
        destination = self.root / "bundle"
        manifest = bundle.prepare(self.lock, "linux-x64", destination, self.source)
        modified = {**manifest, "version": "1.6.0"}
        (destination / "bundle.json").write_text(json.dumps(modified))
        with self.assertRaises(ValueError):
            bundle.check_bundle(destination, manifest)

    def test_symlinked_binary_is_not_a_valid_bundle(self):
        destination = self.root / "bundle"
        manifest = bundle.prepare(self.lock, "linux-x64", destination, self.source)
        binary = destination / "neko"
        binary.unlink()
        try:
            binary.symlink_to(self.source)
        except OSError:
            self.skipTest("host does not permit test symlinks")
        with self.assertRaises(ValueError):
            bundle.check_bundle(destination, manifest)

    def test_lock_rejects_unapproved_sources_and_path_injection(self):
        for key, value in [("repository", "https://example.com/fork"),
                           ("version", "../../latest"), ("commit", "main")]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    bundle.manifest_for({**self.lock, key: value}, "linux-x64")
        for key, value in [("asset", "../neko"), ("size", True), ("size", bundle.MAX_BYTES),
                           ("sha256", "not a digest")]:
            lock = copy.deepcopy(self.lock)
            lock["artifacts"]["linux-x64"][key] = value
            with self.assertRaises(ValueError):
                bundle.manifest_for(lock, "linux-x64")
        with self.assertRaises(ValueError):
            bundle.manifest_for(self.lock, "unsupported-os")

    def test_https_redirect_cannot_downgrade_before_request(self):
        with self.assertRaises(ValueError):
            bundle.HttpsRedirectsOnly().redirect_request(
                Request("https://github.com/example"), None, 302, "Found", {}, "http://example.com/payload")

    def test_overflow_is_rejected_before_writing_excess_bytes(self):
        manifest = bundle.manifest_for(self.lock, "linux-x64")
        output = io.BytesIO()
        with self.assertRaises(ValueError):
            bundle.copy_verified(io.BytesIO(self.payload + b"extra"), output, manifest)
        self.assertEqual(output.getvalue(), b"")

    def test_linux_installer_declares_required_containment_dependency(self):
        config = json.loads((bundle.ROOT / "wiii-desktop/src-tauri/tauri.neko-bundle.conf.json").read_text())
        self.assertIn("bundled-neko", config["build"]["features"])
        self.assertIn("bubblewrap", config["bundle"]["linux"]["deb"]["depends"])

    def test_release_recipes_opt_into_the_bundle(self):
        workflow = (bundle.ROOT / ".github/workflows/release-desktop.yml").read_text()
        builds = [line for line in workflow.splitlines() if "run: npm run tauri -- build" in line]
        self.assertEqual(len(builds), 4)
        self.assertTrue(all("--config src-tauri/tauri.neko-bundle.conf.json" in line for line in builds))
        self.assertIn("prepare_neko_bundle.py --target", workflow)


if __name__ == "__main__":
    unittest.main()
