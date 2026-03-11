from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_PATHS = (
    REPO_ROOT / "maritime-ai-service" / "app",
    REPO_ROOT / "maritime-ai-service" / "docs" / "architecture",
    REPO_ROOT / "maritime-ai-service" / "docs" / "deploy",
    REPO_ROOT / "maritime-ai-service" / "scripts",
    REPO_ROOT / "maritime-ai-service" / "tests",
    REPO_ROOT / "wiii-desktop" / "src",
    REPO_ROOT / "wiii-desktop" / "index.html",
    REPO_ROOT / "wiii-desktop" / "embed.html",
    REPO_ROOT / "wiii-desktop" / "tailwind.config.ts",
    REPO_ROOT / "wiii-desktop" / "README.md",
    REPO_ROOT / "wiii-desktop" / "public" / "splashscreen.html",
)
ALLOWED_LEGACY_PATHS: set[Path] = {
    REPO_ROOT / "maritime-ai-service" / "app" / "engine" / "model_catalog.py",
    REPO_ROOT / "maritime-ai-service" / "tests" / "unit" / "test_model_catalog.py",
    REPO_ROOT / "wiii-desktop" / "src" / "lib" / "llm-presets.ts",
}
TEXT_SUFFIXES = {".css", ".html", ".md", ".py", ".sh", ".toml", ".ts", ".tsx"}
BANNED_STRINGS = (
    "gemini-" + "2.0-flash",
    "gemini-" + "2.0-flash-exp",
    "gemini-" + "2.5-flash",
    "gemini-" + "2.5-pro",
    "text-" + "embedding-004",
)


def _iter_text_files(path: Path):
    if path.is_file():
        if path.suffix in TEXT_SUFFIXES:
            yield path
        return

    for file_path in path.rglob("*"):
        if file_path.is_file() and file_path.suffix in TEXT_SUFFIXES:
            yield file_path


def test_no_legacy_model_strings_in_active_paths():
    violations: list[str] = []

    for root in ACTIVE_PATHS:
        for file_path in _iter_text_files(root):
            if file_path in ALLOWED_LEGACY_PATHS:
                continue
            contents = file_path.read_text(encoding="utf-8", errors="ignore")
            for banned in BANNED_STRINGS:
                if banned in contents:
                    violations.append(
                        f"{file_path.relative_to(REPO_ROOT)} contains banned model string: {banned}"
                    )

    assert not violations, "\n".join(violations)
