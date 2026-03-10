from pathlib import Path
import json

from playwright.sync_api import sync_playwright


ARTIFACT_DIR = Path("E:/Sach/Sua/AI_v1/.claude/reports/playwright")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


PROMPT = "Hãy vẽ một biểu đồ bằng Python và gửi lại file PNG như artifact."


def dump(page, name: str, console_logs: list[dict], network_logs: list[dict]) -> None:
    (ARTIFACT_DIR / f"{name}.json").write_text(
        json.dumps(
            {
                "url": page.url,
                "title": page.title(),
                "buttons": page.locator("button").all_inner_texts(),
                "body_excerpt": page.locator("body").inner_text()[:12000],
                "local_storage": page.evaluate("() => ({...window.localStorage})"),
                "session_storage": page.evaluate("() => ({...window.sessionStorage})"),
                "console_logs": console_logs[-100:],
                "network_logs": network_logs[-200:],
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
        context = browser.new_context(viewport={"width": 1600, "height": 1400})
        page = context.new_page()

        console_logs: list[dict] = []
        network_logs: list[dict] = []

        page.on(
            "console",
            lambda msg: console_logs.append(
                {"type": msg.type, "text": msg.text, "location": msg.location}
            ),
        )
        page.on(
            "response",
            lambda response: network_logs.append(
                {
                    "status": response.status,
                    "url": response.url,
                    "ok": response.ok,
                }
            ),
        )

        page.goto("http://127.0.0.1:1420/", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        dump(page, "20_before_login", console_logs, network_logs)

        buttons = page.locator("button")
        buttons.nth(2).click()
        page.wait_for_timeout(500)

        inputs = page.locator("input")
        if inputs.count() >= 2:
            inputs.nth(1).fill("local-dev-key")
        buttons = page.locator("button")
        buttons.nth(2).click()
        page.wait_for_timeout(4000)
        page.wait_for_load_state("networkidle")
        dump(page, "21_after_login", console_logs, network_logs)

        body_text = page.locator("body").inner_text()
        if "Hỏi Wiii" not in body_text and "Trò chuyện mới" not in body_text:
            browser.close()
            return

        composer = page.locator("textarea, [contenteditable='true']").first
        composer.click()
        composer.fill(PROMPT)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")

        page.wait_for_timeout(4000)
        dump(page, "22_during_stream", console_logs, network_logs)

        page.wait_for_timeout(12000)
        page.wait_for_load_state("networkidle")
        dump(page, "23_after_response", console_logs, network_logs)

        browser.close()


if __name__ == "__main__":
    main()
