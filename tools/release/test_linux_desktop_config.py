"""Guard the narrow Linux packaging overlay without building an installer."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TAURI = ROOT / "wiii-desktop" / "src-tauri"


class LinuxDesktopConfigTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads((TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
        self.linux = json.loads((TAURI / "tauri.linux.conf.json").read_text(encoding="utf-8"))

    def test_linux_selects_only_supported_declared_release_formats(self):
        self.assertEqual(self.linux["bundle"]["targets"], ["deb", "appimage"])

    def test_overlay_does_not_change_runtime_or_security(self):
        self.assertEqual(set(self.linux), {"$schema", "bundle"})
        self.assertEqual(set(self.linux["bundle"]), {"targets"})

    def test_windows_default_remains_nsis(self):
        self.assertEqual(self.base["bundle"]["targets"], ["nsis"])

    def test_linux_preserves_existing_media_framework_setting(self):
        # JSON Merge Patch merges object members, so an overlay containing only
        # targets retains the existing Linux AppImage and Windows NSIS options.
        merged_bundle = {**self.base["bundle"], **self.linux["bundle"]}
        self.assertTrue(merged_bundle["linux"]["appimage"]["bundleMediaFramework"])
        self.assertEqual(merged_bundle["windows"], self.base["bundle"]["windows"])


if __name__ == "__main__":
    unittest.main()
