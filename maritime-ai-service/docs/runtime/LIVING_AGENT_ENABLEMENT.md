# Living Agent — Enablement Guide

Phase 33d of the runtime migration epic ([#207](https://github.com/meiiie/wiii/issues/207)).
Step-by-step procedure for enabling Wiii's autonomous "alive" layer
(Soul AGI). The CODE has been complete since Sprint 170-210d; the
remaining work is OPERATIONAL — install Ollama, pull the model, flip
the flags. This doc captures that exact path.

## What Living Agent gives you

| Feature | Sprint | What user sees |
|---------|--------|----------------|
| 30-min heartbeat | 170 | Wiii's mood drifts naturally between sessions |
| 4D emotion state (mood/energy/social/engagement) | 170 | Avatar emotes reflect time-of-day + recent interactions |
| Skill DISCOVER → LEARN → PRACTICE → EVALUATE → MASTER | 191 | Wiii learns topics from conversations + retains them via SM-2 spaced repetition |
| Journal entries | 170 | Wiii writes a per-tick journal that surfaces in proactive replies |
| Routine tracking | 210 | Wiii notices when you usually appear + says hello differently |
| Proactive messaging | 210 | After silence, Wiii sends a check-in (max 3/day) |
| Living continuity | 210 | Chat conversations feed into emotion / memory / episodes |
| Relationship psychology (CREATOR / KNOWN / OTHER) | 210c | Wiii treats you differently based on long-term relationship tier |
| LLM sentiment analysis (Sprint 210d) | 210d | Sentiment shapes the next reply's emotional valence |

What it does NOT give you:
- Smarter chat answers — that comes from V4 Pro + multi-agent + RAG. Living Agent runs in the background, not on the chat hot path.
- Faster TTFT — Living Agent doesn't touch streaming.

## What Living Agent is NOT

- Not a separate user-facing chat. The chat surface is unchanged.
- Not required for production — Wiii ships with Living Agent OFF by default.
- Not a replacement for memory layers — those (recent window + summary + core memory + episodic) work whether Living Agent is on or off.

## Pre-flight checklist

- [ ] **Ollama installed.** macOS / Windows: download from <https://ollama.com>. Linux: `curl -fsSL https://ollama.com/install.sh | sh`.
- [ ] **Model pulled.** Run `ollama pull qwen3:8b` once. ~5 GB disk.
- [ ] **Ollama daemon running** (auto-starts on macOS / Windows; `systemctl --user start ollama` on Linux).
- [ ] **Verify Ollama reachable** from Wiii: `curl http://localhost:11434/api/tags` should return JSON listing `qwen3:8b`.
- [ ] **Phase 9c+ on main** (already shipped — check `git log origin/main --grep='phase-9'`).

## Procedure

### 1. Enable the core flag

Edit `maritime-ai-service/.env.production`:

```bash
# Living Agent core
ENABLE_LIVING_AGENT=true
LIVING_AGENT_HEARTBEAT_INTERVAL=1800        # seconds (30 min default)
LIVING_AGENT_ACTIVE_HOURS_START=5           # UTC hour Wiii "wakes"
LIVING_AGENT_ACTIVE_HOURS_END=23            # UTC hour Wiii "sleeps"

# Local model (Ollama)
LIVING_AGENT_LOCAL_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434
```

### 2. Pick the sub-features (each can be toggled independently)

```bash
# Background autonomy
LIVING_AGENT_ENABLE_SOCIAL_BROWSE=true       # Wiii browses social feeds when idle
LIVING_AGENT_ENABLE_SKILL_BUILDING=true      # SM-2 spaced repetition of learned topics
LIVING_AGENT_ENABLE_JOURNAL=true             # per-tick journal entries
LIVING_AGENT_ENABLE_WEATHER=true             # weather-aware mood drift
LIVING_AGENT_ENABLE_BRIEFING=true            # morning briefing prep
LIVING_AGENT_ENABLE_ROUTINE_TRACKING=true    # learns when you usually appear

# Goal autonomy
LIVING_AGENT_ENABLE_DYNAMIC_GOALS=true       # Wiii sets her own short-term goals
LIVING_AGENT_AUTONOMY_LEVEL=1                # 0=just react, 3=full autonomy
LIVING_AGENT_ENABLE_AUTONOMY_GRADUATION=true # auto-promote level over time

# Proactive messaging (use with care — Wiii will message users)
LIVING_AGENT_ENABLE_PROACTIVE_MESSAGING=true
LIVING_AGENT_MAX_PROACTIVE_PER_DAY=3
LIVING_AGENT_REQUIRE_HUMAN_APPROVAL=false    # set true for first canary

# Optional: weather data
OPENWEATHERMAP_API_KEY=your_key_here

# Continuity — let Living Agent state shape the chat path
ENABLE_LIVING_CONTINUITY=true                # chat → emotion + memory + episodes
```

### 3. Restart Wiii backend

```bash
# Stop current uvicorn (Phase 31 doc covers this)
# Re-start with the new env:
python -c "
from dotenv import load_dotenv
load_dotenv('.env.production', override=True)
import uvicorn
uvicorn.run('app.main:app', host='0.0.0.0', port=8000)
"
```

### 4. Verify

Boot logs should show:

```
[living_agent] Soul loaded: wiii_soul.yaml
[living_agent] Heartbeat scheduled every 1800s (30 min)
[living_agent] Skill engine ready (qwen3:8b via Ollama)
[living_agent] Sentiment analyzer wired (Sprint 210d)
```

Check the API:

```bash
curl -H "X-API-Key: $WIII_API_KEY" \
     -H "X-User-ID: smoke-test" \
     http://localhost:8000/api/v1/living-agent/state
# Returns JSON with mood / energy / social / engagement
```

Open the desktop UI's Living Agent panel — 5 tabs (overview / skills / goals / journal / reflections) should populate within 30 minutes.

### 5. Soak

- First heartbeat fires after `LIVING_AGENT_HEARTBEAT_INTERVAL` seconds.
- First journal entry: same.
- First skill spaced-repetition pass: depends on existing user history; new accounts wait until Wiii has discovered topics from conversations.
- First proactive message (if enabled): `LIVING_AGENT_ACTIVE_HOURS_START` after the user has been silent for ≥ 4 hours.

## Resource cost

| Resource | Cost |
|----------|------|
| Disk | ~5 GB for qwen3:8b model weights |
| RAM | ~6 GB held by Ollama when active (q4 quant) |
| CPU/GPU | Heartbeat does 1-3 LLM calls per tick. ~1-3 minutes of compute every 30 min on consumer hardware |
| Postgres | +~2 KB per tick (journal + emotion + skills records) |
| Network | Optional: weather API (1 call per heartbeat if enabled), social_browse (varies) |

For a 24-hour day at 30-min heartbeat: 48 ticks × ~2 KB = ~96 KB Postgres growth/day. Tiny.

## Rollback

```bash
ENABLE_LIVING_AGENT=false
```

Restart. The autonomous loop stops on next heartbeat. Postgres records stay (no data loss; you can re-enable any time and pick up where you left off).

## Acceptance bar before keeping it on for real users

- [ ] One full week of heartbeat ticks with 0 errors in `app/engine/living_agent/` log namespace.
- [ ] Mood drift looks plausible to a human reviewer (not stuck at one extreme).
- [ ] No proactive message has been sent without `REQUIRE_HUMAN_APPROVAL=true` clearing in advance.
- [ ] No measurable impact on chat-path TTFT (Living Agent runs in a separate worker, not the chat hot path).
- [ ] If Ollama dies / restarts, Wiii degrades gracefully back to "no Living Agent updates" without 5xx-ing chat.

## Why this is OPERATIONAL, not engineering

The Living Agent code path has been stable since Sprint 210d. What's missing is:

- Picking when to flip the flag (depends on real users existing).
- Picking which sub-features to enable first (depends on product taste).
- Validating the resource budget (depends on the host).
- Watching the first week of ticks (operational).

None of those are code work. Hence Phase 33d is a doc, not a code change.

## Review log

| Date | Reviewer | Change |
|------|----------|--------|
| 2026-05-04 | runtime | v1 — initial enablement guide, Phase 33d of #207 |
