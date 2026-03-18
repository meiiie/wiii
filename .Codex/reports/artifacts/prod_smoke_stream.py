import asyncio
import json
import time
import uuid

import httpx

BASE_URL = "https://wiii.holilihu.online"
API_KEY = "secret_key_cho_team_lms"

TESTS = [
    (
        "visual",
        "Explain Kimi linear attention in charts. Use 2 to 3 small inline figures, each proving one claim: the problem, the mechanism, and the result.",
    ),
    (
        "code_studio",
        "Build a mini pendulum physics app in chat with drag interaction. Use Code Studio and keep it inline with the conversation.",
    ),
]


async def run_case(kind: str, message: str) -> None:
    payload = {
        "message": message,
        "user_id": str(uuid.uuid4()),
        "session_id": f"prod-smoke-{kind}-{int(time.time())}",
        "role": "student",
    }
    counts: dict[str, int] = {}
    snippets: list[tuple[str, str]] = []
    status = "ok"
    error = None
    first_events: list[str] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=30, read=180, write=30, pool=30),
        follow_redirects=True,
    ) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/v1/chat/stream/v3",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "X-API-Key": API_KEY,
                "X-User-ID": payload["user_id"],
                "X-Role": payload["role"],
            },
        ) as response:
            print(f"CASE={kind} HTTP={response.status_code}")
            if response.status_code != 200:
                print((await response.aread()).decode("utf-8", "ignore")[:1000])
                return

            current_event = None
            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    counts[current_event] = counts.get(current_event, 0) + 1
                    if len(first_events) < 20:
                        first_events.append(current_event)
                    continue

                if not line.startswith("data:"):
                    continue

                data = line.split(":", 1)[1].strip()
                if current_event == "error":
                    status = "error"
                    error = data[:500]
                    break

                if current_event in {
                    "thinking",
                    "action_text",
                    "status",
                    "answer",
                    "code_open",
                    "code_delta",
                    "code_complete",
                    "visual_open",
                    "visual_patch",
                    "visual_commit",
                } and len(snippets) < 16:
                    snippets.append((current_event, data[:220]))

                if current_event == "done":
                    break

    print("FIRST_EVENTS=", first_events)
    print("COUNTS=", json.dumps(counts, ensure_ascii=False))
    print("STATUS=", status)
    if error:
        print("ERROR=", error)
    print("SNIPPETS_START")
    for event_name, data in snippets:
        print(f"[{event_name}] {data}")
    print("SNIPPETS_END")
    print("---")


async def main() -> None:
    for case in TESTS:
        await run_case(*case)


if __name__ == "__main__":
    asyncio.run(main())
