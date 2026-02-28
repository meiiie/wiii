#!/usr/bin/env python3
"""Sprint 210c -- Live API Test Suite.

Tests tier-aware emotion feedback, episodic memory, goals, and heartbeat
against the running Docker stack.

Usage: python scripts/test_sprint210c_live.py
"""
import asyncio
import json
import sys

import httpx

BASE = "http://localhost:8000"
HEADERS = {
    "X-API-Key": "local-dev-key",
    "Content-Type": "application/json",
}

ADMIN_HEADERS = {
    **HEADERS,
    "X-User-ID": "admin",
    "X-Role": "admin",
    "X-Session-ID": "live-210c-admin",
}
STUDENT_HEADERS = {
    **HEADERS,
    "X-User-ID": "student-test-99",
    "X-Role": "student",
    "X-Session-ID": "live-210c-student",
}


def p(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    msg = "  [%s] %s" % (mark, label)
    if detail:
        msg += " -- %s" % detail
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    return ok


def pr(msg):
    sys.stdout.buffer.write((str(msg) + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


passed = 0
failed = 0


def check(label, ok, detail=""):
    global passed, failed
    if p(label, ok, detail):
        passed += 1
    else:
        failed += 1
    return ok


async def main():
    global passed, failed
    client = httpx.AsyncClient(timeout=60.0)

    pr("\n" + "=" * 60)
    pr("  Sprint 210c -- Live API Test Suite")
    pr("=" * 60)

    # ------------------------------------------------------------------
    # 0. Health
    # ------------------------------------------------------------------
    pr("\n--- 0. Health Check ---")
    r = await client.get(f"{BASE}/health")
    if not check("App healthy", r.status_code == 200, r.text[:100]):
        pr("  ABORT: app not running")
        return 1

    # ------------------------------------------------------------------
    # 1. Baseline emotional state
    # ------------------------------------------------------------------
    pr("\n--- 1. Baseline Emotional State ---")
    r = await client.get(f"{BASE}/api/v1/living-agent/emotional-state", headers=ADMIN_HEADERS)
    emo = r.json()
    baseline_mood = emo.get("primary_mood", "unknown")
    check("Got emotional state", r.status_code == 200, "mood=%s" % baseline_mood)

    # ------------------------------------------------------------------
    # 2. Admin positive message (Creator tier -> immediate mood impact)
    # ------------------------------------------------------------------
    pr("\n--- 2. Admin Positive Message (Creator Tier) ---")
    body = {
        "message": "Thank you Wiii! You are amazing and so helpful!",
        "user_id": "admin",
        "session_id": "live-210c-admin",
        "role": "admin",
    }
    r = await client.post(f"{BASE}/api/v1/chat", headers=ADMIN_HEADERS, json=body)
    check("Chat responded (admin positive)", r.status_code == 200, "len=%d" % len(r.text))
    if r.status_code == 200:
        resp_data = r.json()
        pr("    Agent: %s" % resp_data.get("agent_type", "N/A"))
        pr("    Response: %s..." % (resp_data.get("response") or "")[:120])

    await asyncio.sleep(1)
    r = await client.get(f"{BASE}/api/v1/living-agent/emotional-state", headers=ADMIN_HEADERS)
    mood_after_positive = r.json().get("primary_mood", "unknown")
    pr("    Mood: %s -> %s" % (baseline_mood, mood_after_positive))
    # Positive feedback from Creator should keep/set mood to happy
    check("Mood is happy/positive after praise",
          mood_after_positive in ("happy", "proud", "excited", "grateful"),
          mood_after_positive)

    # ------------------------------------------------------------------
    # 3. Admin negative message
    # ------------------------------------------------------------------
    pr("\n--- 3. Admin Negative Message ---")
    body = {
        "message": "That was wrong, you made a mistake. Not correct at all.",
        "user_id": "admin",
        "session_id": "live-210c-admin",
        "role": "admin",
    }
    r = await client.post(f"{BASE}/api/v1/chat", headers=ADMIN_HEADERS, json=body)
    check("Chat responded (admin negative)", r.status_code == 200)

    await asyncio.sleep(1)
    r = await client.get(f"{BASE}/api/v1/living-agent/emotional-state", headers=ADMIN_HEADERS)
    mood_after_neg = r.json().get("primary_mood", "unknown")
    pr("    Mood: %s -> %s" % (mood_after_positive, mood_after_neg))
    # Note: single negative may or may not change mood depending on intensity
    # The important thing is that the LifeEvent was processed (we'll verify via logs)
    check("Emotional state accessible after negative", r.status_code == 200)

    # ------------------------------------------------------------------
    # 4. Student message (Non-Creator -> Buffered, no immediate mood change)
    # ------------------------------------------------------------------
    pr("\n--- 4. Student Message (Non-Creator Tier -> Buffered) ---")
    mood_before_student = mood_after_neg
    body = {
        "message": "Hello Wiii, help me with COLREG rule 13 please",
        "user_id": "student-test-99",
        "session_id": "live-210c-student",
        "role": "student",
    }
    r = await client.post(f"{BASE}/api/v1/chat", headers=STUDENT_HEADERS, json=body)
    check("Student chat responded", r.status_code == 200)

    await asyncio.sleep(1)
    r = await client.get(f"{BASE}/api/v1/living-agent/emotional-state", headers=STUDENT_HEADERS)
    mood_after_student = r.json().get("primary_mood", "unknown")
    check("Mood unchanged after student msg (buffered)",
          mood_after_student == mood_before_student,
          "still %s" % mood_after_student)

    # ------------------------------------------------------------------
    # 5. Episodic memory (check via DB directly since API has no type filter)
    # ------------------------------------------------------------------
    pr("\n--- 5. Episodic Memory Check ---")
    # Try the memories endpoint (returns all types)
    r = await client.get(f"{BASE}/api/v1/memories/admin", headers=ADMIN_HEADERS)
    if r.status_code == 200:
        all_memories = r.json()
        if isinstance(all_memories, list):
            episodes = [m for m in all_memories if m.get("memory_type") == "episode"]
            total = len(all_memories)
            check("Memories retrieved", total > 0, "total=%d, episodes=%d" % (total, len(episodes)))
            if episodes:
                pr("    Latest episode: %s" % json.dumps(episodes[0], ensure_ascii=True)[:200])
        else:
            check("Memories response format", False, "unexpected format: %s" % type(all_memories).__name__)
    elif r.status_code == 404:
        # Might be behind auth check - try as insight endpoint
        check("Memories endpoint (admin)", False, "404 returned")
    else:
        check("Memories endpoint", False, "status=%d" % r.status_code)

    # ------------------------------------------------------------------
    # 6. Living Agent full status
    # ------------------------------------------------------------------
    pr("\n--- 6. Living Agent Full Status ---")
    r = await client.get(f"{BASE}/api/v1/living-agent/status", headers=ADMIN_HEADERS)
    if r.status_code == 200:
        status = r.json()
        check("Status endpoint OK", True)
        skills_count = status.get("skills_count", 0)
        journal_count = status.get("journal_entries_count", 0)
        heartbeat_count = status.get("heartbeat", {}).get("heartbeat_count", 0)
        soul_loaded = status.get("soul_loaded", False)
        enabled = status.get("enabled", False)
        pr("    Enabled: %s" % enabled)
        pr("    Soul loaded: %s" % soul_loaded)
        pr("    Skills: %d" % skills_count)
        pr("    Journal entries: %d" % journal_count)
        pr("    Heartbeat count: %d" % heartbeat_count)
        pr("    Mood: %s" % status.get("emotional_state", {}).get("primary_mood", "N/A"))

        check("Living Agent enabled", enabled)
        check("Soul loaded", soul_loaded)
        check("Heartbeat has run", heartbeat_count > 0, "%d beats" % heartbeat_count)
        check("Skills discovered", skills_count > 0, "%d skills" % skills_count)
    else:
        pr("    Status endpoint failed: %d" % r.status_code)
        for _ in range(5):
            failed += 1

    # ------------------------------------------------------------------
    # 7. Goals (seeded from wiii_soul.yaml)
    # ------------------------------------------------------------------
    pr("\n--- 7. Goals Check ---")
    r = await client.get(f"{BASE}/api/v1/living-agent/goals", headers=ADMIN_HEADERS)
    if r.status_code == 200:
        goals = r.json()
        goal_list = goals if isinstance(goals, list) else goals.get("goals", [])
        check("Goals seeded from soul", len(goal_list) >= 3, "count=%d" % len(goal_list))
        for g in goal_list[:5]:
            title = g.get("title", g.get("name", "?"))
            pr("    - %s" % title)
    elif r.status_code == 404:
        check("Goals endpoint exists", False, "404")
    else:
        check("Goals endpoint", False, "status=%d" % r.status_code)

    # ------------------------------------------------------------------
    # 8. Heartbeat trigger (long timeout - Ollama CPU inference is slow)
    # ------------------------------------------------------------------
    pr("\n--- 8. Manual Heartbeat Trigger ---")
    pr("    (Using 180s timeout for Ollama CPU inference...)")
    try:
        long_client = httpx.AsyncClient(timeout=180.0)
        r = await long_client.post(f"{BASE}/api/v1/living-agent/heartbeat/trigger", headers=ADMIN_HEADERS)
        if r.status_code in (200, 202):
            hb = r.json()
            check("Heartbeat triggered", True, json.dumps(hb)[:200])
        else:
            check("Heartbeat trigger", False, "status=%d: %s" % (r.status_code, r.text[:200]))
        await long_client.aclose()
    except httpx.ReadTimeout:
        check("Heartbeat trigger (timeout)", False, "Ollama inference >180s")
    except Exception as e:
        check("Heartbeat trigger", False, str(e)[:200])

    # Give it time to complete
    pr("    Waiting 5s...")
    await asyncio.sleep(5)

    # Verify heartbeat count increased
    r = await client.get(f"{BASE}/api/v1/living-agent/status", headers=ADMIN_HEADERS)
    if r.status_code == 200:
        status2 = r.json()
        new_hb = status2.get("heartbeat", {}).get("heartbeat_count", 0)
        check("Heartbeat count increased", new_hb > heartbeat_count,
              "%d -> %d" % (heartbeat_count, new_hb))

    # ------------------------------------------------------------------
    # 9. Journal entries
    # ------------------------------------------------------------------
    pr("\n--- 9. Journal Check ---")
    r = await client.get(f"{BASE}/api/v1/living-agent/journal", headers=ADMIN_HEADERS)
    if r.status_code == 200:
        journal = r.json()
        j_list = journal if isinstance(journal, list) else journal.get("entries", [])
        check("Journal endpoint OK", True, "entries=%d" % len(j_list))
        if j_list:
            pr("    Latest: %s" % json.dumps(j_list[0], ensure_ascii=True)[:200])
    else:
        check("Journal endpoint", False, "status=%d" % r.status_code)

    # ------------------------------------------------------------------
    # 10. Streaming chat (admin)
    # ------------------------------------------------------------------
    pr("\n--- 10. Streaming Chat (Admin) ---")
    body = {
        "message": "What is SOLAS?",
        "user_id": "admin",
        "session_id": "live-210c-stream",
        "role": "admin",
    }
    try:
        async with client.stream(
            "POST", f"{BASE}/api/v1/chat/stream/v3",
            headers=ADMIN_HEADERS, json=body, timeout=30.0,
        ) as resp:
            chunks = []
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunks.append(line[6:])
                if len(chunks) > 5:
                    break
            check("SSE stream received", len(chunks) > 0, "%d events" % len(chunks))
    except Exception as e:
        check("SSE stream", False, str(e)[:200])

    # Final mood
    r = await client.get(f"{BASE}/api/v1/living-agent/emotional-state", headers=ADMIN_HEADERS)
    final_mood = r.json().get("primary_mood", "unknown")
    pr("    Final mood: %s" % final_mood)

    # ------------------------------------------------------------------
    # 11. Skills
    # ------------------------------------------------------------------
    pr("\n--- 11. Skills Check ---")
    r = await client.get(f"{BASE}/api/v1/living-agent/skills", headers=ADMIN_HEADERS)
    if r.status_code == 200:
        skills = r.json()
        s_list = skills if isinstance(skills, list) else skills.get("skills", [])
        check("Skills endpoint OK", len(s_list) > 0, "count=%d" % len(s_list))
        for s in s_list[:5]:
            name = s.get("name", s.get("skill_name", "?"))
            status_val = s.get("status", s.get("lifecycle_stage", "?"))
            pr("    - %s (%s)" % (name, status_val))
    else:
        check("Skills endpoint", False, "status=%d" % r.status_code)

    # ------------------------------------------------------------------
    # 12. Multiple student messages (verify buffering at scale)
    # ------------------------------------------------------------------
    pr("\n--- 12. Multiple Student Messages (Buffer Test) ---")
    mood_before_multi = final_mood
    for i in range(3):
        body_s = {
            "message": "Question %d about maritime safety" % (i + 1),
            "user_id": "student-bulk-%d" % i,
            "session_id": "live-210c-bulk-%d" % i,
            "role": "student",
        }
        hdrs = {**HEADERS, "X-User-ID": "student-bulk-%d" % i, "X-Role": "student", "X-Session-ID": "live-210c-bulk-%d" % i}
        r = await client.post(f"{BASE}/api/v1/chat", headers=hdrs, json=body_s)
        pr("    Student %d: %d" % (i, r.status_code))

    await asyncio.sleep(1)
    r = await client.get(f"{BASE}/api/v1/living-agent/emotional-state", headers=ADMIN_HEADERS)
    mood_after_multi = r.json().get("primary_mood", "unknown")
    check("Mood unchanged after 3 student msgs",
          mood_after_multi == mood_before_multi,
          "still %s (3 students buffered, not processed)" % mood_after_multi)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = passed + failed
    pr("\n" + "=" * 60)
    pr("  RESULTS: %d/%d passed, %d failed" % (passed, total, failed))
    pct = (passed * 100 // total) if total else 0
    pr("  Pass rate: %d%%" % pct)
    pr("=" * 60 + "\n")

    await client.aclose()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
