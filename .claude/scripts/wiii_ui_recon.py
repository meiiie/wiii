from pathlib import Path
import json
import time

from playwright.sync_api import sync_playwright


ARTIFACT_DIR = Path("E:/Sach/Sua/AI_v1/.claude/reports/playwright")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def save_json(name: str, payload: object) -> None:
    (ARTIFACT_DIR / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1200})
        page = context.new_page()
        console_logs = []
        page.on(
            "console",
            lambda msg: console_logs.append(
                {"type": msg.type, "text": msg.text, "location": msg.location}
            ),
        )

        page.goto("http://127.0.0.1:1420", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(ARTIFACT_DIR / "00_initial.png"), full_page=True)

        buttons = page.locator("button").all_inner_texts()
        inputs = page.locator("input, textarea").evaluate_all(
            """els => els.map(el => ({
                tag: el.tagName,
                placeholder: el.placeholder || '',
                value: el.value || '',
                aria: el.getAttribute('aria-label') || ''
            }))"""
        )
        texts = page.locator("body").inner_text()

        save_json(
            "recon_initial.json",
            {
                "url": page.url,
                "title": page.title(),
                "buttons": buttons,
                "inputs": inputs,
                "body_excerpt": texts[:6000],
                "local_storage": page.evaluate("() => ({...window.localStorage})"),
                "session_storage": page.evaluate("() => ({...window.sessionStorage})"),
            },
        )

        save_json("console_initial.json", console_logs)
        browser.close()


if __name__ == "__main__":
    main()
