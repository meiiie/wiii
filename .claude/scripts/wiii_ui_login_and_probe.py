from pathlib import Path
import json

from playwright.sync_api import sync_playwright


ARTIFACT_DIR = Path("E:/Sach/Sua/AI_v1/.claude/reports/playwright")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def dump(page, name: str) -> None:
    (ARTIFACT_DIR / f"{name}.json").write_text(
        json.dumps(
            {
                "url": page.url,
                "title": page.title(),
                "buttons": page.locator("button").all_inner_texts(),
                "inputs": page.locator("input, textarea").evaluate_all(
                    """els => els.map(el => ({
                        tag: el.tagName,
                        type: el.getAttribute('type') || '',
                        placeholder: el.placeholder || '',
                        value: el.value || '',
                        aria: el.getAttribute('aria-label') || '',
                        name: el.getAttribute('name') || ''
                    }))"""
                ),
                "body_excerpt": page.locator("body").inner_text()[:8000],
                "local_storage": page.evaluate("() => ({...window.localStorage})"),
                "session_storage": page.evaluate("() => ({...window.sessionStorage})"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    page.screenshot(path=str(ARTIFACT_DIR / f"{name}.png"), full_page=True)


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1200})
        page = context.new_page()
        page.goto("http://127.0.0.1:1420/", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        dump(page, "10_login_initial")

        buttons = page.locator("button")
        if buttons.count() >= 3:
            buttons.nth(2).click()
            page.wait_for_timeout(2000)
            dump(page, "11_after_devmode_click")

        browser.close()


if __name__ == "__main__":
    main()
