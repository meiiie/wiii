"""Guard the one-click Windows installer template without building it."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "wiii-desktop"
TAURI = DESKTOP / "src-tauri"


class WindowsInstallerTemplateTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
        self.nsis = self.config["bundle"]["windows"]["nsis"]
        self.template = (TAURI / self.nsis["template"]).read_text(encoding="utf-8")

    def _function(self, name):
        match = re.search(rf"(?ms)^Function {re.escape(name)}\n(.*?)^FunctionEnd", self.template)
        self.assertIsNotNone(match, name)
        return match.group(1)

    def test_template_tracks_the_locked_tauri_cli(self):
        lock = json.loads((DESKTOP / "package-lock.json").read_text(encoding="utf-8"))
        locked = lock["packages"]["node_modules/@tauri-apps/cli"]["version"]
        derived = re.search(r"shipped with @tauri-apps/cli (\S+)\.", self.template)
        self.assertIsNotNone(derived)
        self.assertEqual(derived.group(1), locked, "re-derive windows/installer.nsi for the new Tauri CLI")

    def test_install_needs_no_choices(self):
        self.assertEqual(self.nsis["installMode"], "currentUser")
        self.assertFalse(self.nsis["displayLanguageSelector"])
        self.assertIn("RequestExecutionLevel user", self.template)
        on_init = self._function(".onInit")
        self.assertRegex(on_init, r"(?m)^\s*StrCpy \$PassiveMode 1\s*$")
        self.assertNotIn('"/P" $PassiveMode', on_init)

    def test_progress_page_is_the_only_installer_page(self):
        self.assertIn("ShowInstDetails nevershow", self.template)
        pages = []
        pre = None
        for line in self.template.splitlines():
            line = line.strip()
            if line.startswith("!define MUI_PAGE_CUSTOMFUNCTION_PRE "):
                pre = line.split()[-1]
            elif re.match(r"!insertmacro (MUI_PAGE_\w+|MULTIUSER_PAGE_INSTALLMODE)", line):
                pages.append((line.split()[1], pre))
                pre = None
        self.assertIn(("MUI_PAGE_INSTFILES", None), pages)
        for page, page_pre in pages:
            if page != "MUI_PAGE_INSTFILES":
                self.assertIn(page_pre, {"SkipIfPassive", "Skip"}, page)
        self.assertIn("SetAutoClose true", self._section("Install"))

    def test_interactive_install_opens_wiii(self):
        on_success = self._function(".onInstSuccess")
        interactive = on_success.split("${Else}", 1)[1]
        self.assertIn('nsis_tauri_utils::RunAsUser "$INSTDIR\${MAINBINARYNAME}.exe"', interactive)

    def test_shortcuts_are_created_without_the_finish_page(self):
        install = self._section("Install")
        self.assertIn("Call CreateOrUpdateStartMenuShortcut", install)
        self.assertRegex(install, r"\$PassiveMode = 1[\s\S]*?Call CreateOrUpdateDesktopShortcut")

    def _section(self, name):
        match = re.search(rf"(?ms)^Section {re.escape(name)}\n(.*?)^SectionEnd", self.template)
        self.assertIsNotNone(match, name)
        return match.group(1)


if __name__ == "__main__":
    unittest.main()
