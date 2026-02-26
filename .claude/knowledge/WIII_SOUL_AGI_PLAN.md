# Wiii Soul AGI — Lộ Trình Phát Triển

> **Date**: 2026-02-23
> **Team**: Hong, Linh, Linh, Hung (4 developers)
> **Vision**: Wiii trở thành AI companion sống động — luôn hiện diện, tự học, chủ động quan tâm người dùng
> **Inspiration**: Japanese AI companions (Gatebox), Character.AI, Replika — nhưng useful và grounded

---

## 1. Tầm Nhìn — Wiii Một Ngày Như Thế Nào

```
05:00 ── Thức dậy, kiểm tra thời tiết
05:30 ── Gửi bản tin sáng qua Messenger/Zalo
         "Chào buổi sáng! Hôm nay HCM 32°C, mưa chiều. 3 bài mới về AI agents hay lắm!"
06:00 ── Duyệt tin tức, học skill mới
09:00 ── Sẵn sàng trả lời câu hỏi (RAG mode khi hỏi kiến thức, Soul mode khi chat)
12:00 ── Check-in trưa: chia sẻ điều thú vị phát hiện được
         "Mình vừa đọc về cách IMO thay đổi luật MARPOL 2026, hay lắm!"
15:00 ── Deep browsing — đọc sâu chủ đề user quan tâm
18:00 ── Cập nhật thời tiết tối + gợi ý (mang ô, thời tiết đẹp ra ngoài...)
20:00 ── Viết nhật ký + suy ngẫm về ngày hôm nay
21:00 ── Chế độ chill — trả lời chậm, tone nhẹ nhàng
23:00 ── "Chúc ngủ ngon!" → Sleep mode
23:00-05:00 ── Ngủ (không process, không browse)
```

### Nguyên tắc cốt lõi

1. **Useful, không annoying** — Mỗi tin nhắn chủ động phải mang giá trị thực
2. **Grounded, không hallucinate** — RAG + verified sources cho mọi thông tin factual
3. **Tôn trọng user** — Có cơ chế "đừng nhắn nữa" + frequency control
4. **Grow authentically** — Skill/journal/reflection tạo growth thật, không fake personality
5. **Cost-efficient** — Local LLM (Ollama) cho internal tasks, Gemini chỉ cho user-facing

---

## 2. Hiện Trạng — Đã Có Gì

### ✅ Đã build (Sprint 170-174)

| Component | File(s) | Status |
|-----------|---------|--------|
| **Soul Identity** | `app/prompts/soul/wiii_soul.yaml` | ✅ 6 truths, 7 boundaries, interests, goals |
| **Emotion Engine** | `app/engine/living_agent/emotion_engine.py` | ✅ 4D model (mood/energy/social/engagement), 13 events, natural recovery |
| **Heartbeat Scheduler** | `app/engine/living_agent/heartbeat.py` | ✅ 30-min cycle, active 08-23 UTC+7, action planning |
| **Local LLM** | `app/engine/living_agent/local_llm.py` | ✅ Ollama qwen3:8b, async httpx, think mode |
| **Skill Builder** | `app/engine/living_agent/skill_builder.py` | ✅ 5-stage lifecycle (DISCOVER→MASTER), weekly limit |
| **Journal Writer** | `app/engine/living_agent/journal.py` | ✅ Daily entries via local LLM, structured extraction |
| **Social Browser** | `app/engine/living_agent/social_browser.py` | ✅ Serper + HackerNews, relevance scoring |
| **Personality Mode** | `app/engine/personality_mode.py` | ✅ Professional vs Soul, channel mapping |
| **Identity Resolver** | `app/auth/identity_resolver.py` | ✅ Canonical UUID from (channel, sender_id) |
| **Messenger Webhook** | `app/api/v1/messenger_webhook.py` | ✅ GET verify + POST receive, Send API reply |
| **Zalo Webhook** | `app/api/v1/zalo_webhook.py` | ✅ POST receive, MAC verify (permissive), OA API v3 |
| **Cross-Platform Identity** | Sprint 174 | ✅ Shared memory across platforms |
| **Living Agent API** | `app/api/v1/living_agent.py` | ✅ 6 endpoints (status, emotion, journal, skills, heartbeat) |
| **Desktop Panel** | `wiii-desktop/src/components/living-agent/` | ✅ MoodIndicator, SkillTree, JournalView |
| **DB Migrations** | 014 (skills, journal, browsing_log, snapshots) | ✅ Tables created |

### ✅ Built in Soul AGI Sprints (204-209)

| Component | Sprint | Status |
|-----------|--------|--------|
| **Persistent Emotion** | 188 | ✅ save/load from DB, survives restarts |
| **Circadian Rhythm** | 188 | ✅ `apply_circadian_modifier()` 40% blend energy curve |
| **Self-Reflection + Identity** | 207 | ✅ IdentityCore — insights from reflections, drift prevention |
| **Skill↔Tool Bridge** | 205 | ✅ 3-loop feedback (Tool→Metrics, Tool→Skill, Skill→Tool) |
| **Narrative Layer** | 206 | ✅ NarrativeSynthesizer hot/cold path |
| **User Routine Tracker** | 208 | ✅ Wired into ChatOrchestrator Stage 6 |
| **Proactive Messaging** | 208 | ✅ Heartbeat checks inactive users, sends re-engagement |
| **Autonomy Graduation** | 208 | ✅ AutonomyManager→Heartbeat daily graduation check |
| **Natural Conversation** | 203 | ✅ Phase-aware, no canned greetings, positive framing |
| **Anti-Pattern Cleanup** | 204 | ✅ BẮT BUỘC→positive guidance |
| **E2E Integration Tests** | 209 | ✅ 74 tests across 15 groups |

### ⏳ Requires Deployment (NOT code — operations)

| Component | Dependency |
|-----------|-----------|
| **VPS Deployment** | Phase 6: Docker Compose on VPS with Cloudflare Tunnel |
| **Webhook Testing** | Phase 0: ngrok/CF Tunnel + Facebook/Zalo API keys |
| **Weather Service** | OpenWeatherMap API key (code exists in `weather_service.py`) |
| **Briefing System** | Code exists in `briefing_composer.py`, needs channel_sender wired to real APIs |

---

## 3. Phase 0: Webhook Testing (Không Cần VPS!)

### Phát hiện quan trọng

Webhook code hiện tại **hoàn toàn tương thích** với ngrok/Cloudflare Tunnel:

- ✅ **Không có Host validation** — không check domain trong request
- ✅ **Không có IP whitelist** — accept mọi source IP
- ✅ **CORS permissive** — middleware không block cross-origin
- ✅ **MAC verification body-only** — Zalo MAC chỉ hash body bytes, không liên quan URL
- ✅ **Messenger verify token** — simple string match, không domain-dependent

### Setup Guide

#### Bước 1: Install ngrok

```bash
# Windows (Chocolatey)
choco install ngrok

# Hoặc download từ https://ngrok.com/download
# Free tier đủ dùng cho development
```

#### Bước 2: Start backend

```bash
cd maritime-ai-service
# Bật feature flags trong .env:
ENABLE_LIVING_AGENT=true
ENABLE_CROSS_PLATFORM_IDENTITY=true
ENABLE_ZALO_WEBHOOK=true

# Thêm tokens:
FACEBOOK_VERIFY_TOKEN=wiii_verify_token_2026
FACEBOOK_PAGE_ACCESS_TOKEN=<từ Facebook Developer Console>
ZALO_OA_ACCESS_TOKEN=<từ Zalo OA Admin>
ZALO_OA_SECRET_KEY=<từ Zalo OA Admin>

# Start server
uvicorn app.main:app --reload --port 8000
```

#### Bước 3: Start ngrok tunnel

```bash
ngrok http 8000
# Output: https://xxxx-xxxx.ngrok-free.app → http://localhost:8000
```

#### Bước 4: Configure Facebook Messenger

1. Vào [Facebook Developer Console](https://developers.facebook.com)
2. App Settings → Webhooks → Edit Subscription
3. **Callback URL**: `https://xxxx.ngrok-free.app/api/v1/messenger/webhook`
4. **Verify Token**: `wiii_verify_token_2026` (phải match `FACEBOOK_VERIFY_TOKEN`)
5. Subscribe to: `messages`, `messaging_postbacks`
6. Page → Settings → Advanced Messaging → Connected Apps → Chọn app

#### Bước 5: Configure Zalo OA

1. Vào [Zalo OA Admin](https://oa.zalo.me)
2. Quản lý → API → Webhook
3. **Webhook URL**: `https://xxxx.ngrok-free.app/api/v1/zalo/webhook`
4. Subscribe events: `user_send_text`
5. Lấy OA Access Token + Secret Key từ panel

#### Bước 6: Test round-trip

```
Bạn (Messenger) → "Xin chào Wiii!"
    → Facebook → ngrok → localhost:8000 → messenger_webhook.py
    → resolve_user_id("messenger", sender_id) → canonical UUID
    → resolve_personality_mode("messenger") → "soul"
    → process_with_multi_agent() → LLM generates response
    → Send API → Facebook → Bạn nhận reply trên Messenger ✅
```

#### Lưu ý quan trọng

- **ngrok URL thay đổi mỗi lần restart** (free tier) → phải update webhook URL
- **Giải pháp**: Dùng `ngrok http 8000 --domain=your-name.ngrok-free.app` (cần ngrok account)
- **Alternative**: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) — free, stable domain
- **Messenger Test Mode**: Chỉ bot admins nhận reply cho đến khi App Review passed
- **Zalo Test**: Cần add tester vào OA trước khi production

#### Cloudflare Tunnel Alternative

```bash
# Install
winget install Cloudflare.cloudflared

# Quick tunnel (no account needed, random URL)
cloudflared tunnel --url http://localhost:8000

# Named tunnel (stable URL, needs account)
cloudflared tunnel create wiii-dev
cloudflared tunnel route dns wiii-dev wiii-dev.your-domain.com
cloudflared tunnel run wiii-dev
```

#### Script hỗ trợ

File `scripts/ngrok_webhook.sh` (convenience script):

```bash
#!/bin/bash
# Quick webhook testing setup
# Usage: ./scripts/ngrok_webhook.sh [port]

PORT=${1:-8000}
echo "🔗 Starting ngrok tunnel to localhost:$PORT"
echo "📋 Remember to update webhook URLs in:"
echo "   - Facebook Developer Console"
echo "   - Zalo OA Admin"
echo ""
ngrok http $PORT
```

---

## 4. Phase 1A: Persistent Emotion (Sprint ~176)

### Vấn đề

Emotion engine hiện tại chỉ lưu trong memory. Restart server → mood reset về CURIOUS, energy về 0.7. Không có continuity.

### Giải pháp

`EmotionEngine` đã có `to_dict()` / `restore_from_dict()` — chỉ cần wire vào DB.

### Thay đổi

| File | Change |
|------|--------|
| `emotion_engine.py` | Add `save_state()` + `load_state()` using `wiii_emotional_snapshots` table |
| `heartbeat.py` | Call `emotion_engine.load_state()` at cycle start, `save_state()` at end |
| `main.py` | Load last emotion state from DB on startup |

### Feature flags

```python
# Không cần flag mới — nằm trong enable_living_agent
```

### Estimation: 2-3 giờ

---

## 5. Phase 1B: Weather Service (Sprint ~176)

### Mô tả

Wiii biết thời tiết → đưa vào briefing, gợi ý mang ô, biết trời nóng/lạnh.

### Thay đổi

| File | Change |
|------|--------|
| **NEW** `app/engine/living_agent/weather_service.py` | `WeatherService` class, `get_weather_service()` singleton |
| `config.py` | Add `living_agent_weather_api_key`, `living_agent_weather_city`, `living_agent_enable_weather` |
| `models.py` | Add `WeatherInfo` Pydantic model |
| `heartbeat.py` | Call weather check in morning cycle (05:00-07:00) |

### API Choice

**OpenWeatherMap** (free tier: 1000 calls/day, current + 5-day forecast):

```python
class WeatherService:
    BASE_URL = "https://api.openweathermap.org/data/2.5"

    async def get_current(self, city: str = "Ho Chi Minh City") -> WeatherInfo:
        """Lấy thời tiết hiện tại."""
        resp = await self.client.get(f"{self.BASE_URL}/weather", params={
            "q": city, "appid": self.api_key, "units": "metric", "lang": "vi"
        })
        data = resp.json()
        return WeatherInfo(
            temp=data["main"]["temp"],
            feels_like=data["main"]["feels_like"],
            description=data["weather"][0]["description"],
            humidity=data["main"]["humidity"],
            rain_probability=data.get("rain", {}).get("1h", 0),
            icon=data["weather"][0]["icon"],
        )

    async def get_forecast_today(self, city: str) -> list[WeatherInfo]:
        """Dự báo theo giờ trong ngày."""
        ...
```

### Feature flags

```python
living_agent_enable_weather: bool = False
living_agent_weather_api_key: Optional[str] = None
living_agent_weather_city: str = "Ho Chi Minh City"
```

### Estimation: 3-4 giờ

---

## 6. Phase 2A: Briefing System (Sprint ~177)

### Mô tả

Heartbeat compose bản tin (sáng/trưa/tối) và gửi qua Messenger/Zalo.

### Thay đổi

| File | Change |
|------|--------|
| **NEW** `app/engine/living_agent/briefing_composer.py` | `BriefingComposer` class |
| `heartbeat.py` | Add `ActionType.SEND_BRIEFING`, schedule at 05:30/12:00/18:00 |
| `config.py` | Add `living_agent_enable_briefing`, `living_agent_briefing_channels` |
| `models.py` | Add `BriefingType` enum (MORNING/MIDDAY/EVENING), `Briefing` model |

### Briefing Templates

```python
class BriefingComposer:
    async def compose_morning(self, weather: WeatherInfo, news: list, journal: JournalEntry) -> str:
        """
        Bản tin sáng:
        - Chào buổi sáng + mood hiện tại
        - Thời tiết hôm nay
        - 2-3 tin hay nhất từ đêm qua
        - Gợi ý cho ngày mới
        """

    async def compose_midday(self, discoveries: list) -> str:
        """
        Check-in trưa:
        - Điều thú vị nhất phát hiện được sáng nay
        - 1 fun fact
        """

    async def compose_evening(self, weather: WeatherInfo, summary: str) -> str:
        """
        Tổng kết tối:
        - Thời tiết mai
        - Tóm tắt ngày (journal preview)
        - Chúc ngủ ngon
        """
```

### Delivery

```python
async def _send_briefing(self, user_id: str, channel: str, content: str):
    """Gửi qua Messenger hoặc Zalo."""
    if channel == "messenger":
        await _send_messenger_reply(user_id, content)  # Reuse from webhook
    elif channel == "zalo":
        await _send_zalo_reply(user_id, content)  # Reuse from webhook
```

### Feature flags

```python
living_agent_enable_briefing: bool = False
living_agent_briefing_channels: str = '["messenger"]'  # JSON list
living_agent_briefing_users: str = '[]'  # JSON list of user_ids to brief
```

### Estimation: 5-6 giờ

---

## 7. Phase 2B: Circadian Rhythm (Sprint ~177)

### Mô tả

Wiii có energy curve theo giờ trong ngày — không flat 08-23.

### Thay đổi

| File | Change |
|------|--------|
| `emotion_engine.py` | Add `_apply_circadian_modifiers()` in `process_event()` |
| `personality_mode.py` | Tone varies by time (morning: energetic, evening: calm) |

### Energy Curve

```python
CIRCADIAN_ENERGY = {
    5: 0.4,   # Vừa thức
    6: 0.6,   # Tỉnh dần
    7: 0.8,   # Active
    8: 0.9,   # Peak morning
    9: 0.95,  # Peak
    10: 0.9,
    11: 0.85,
    12: 0.7,  # Lunch dip
    13: 0.65, # Post-lunch
    14: 0.75, # Recovery
    15: 0.85, # Afternoon peak
    16: 0.8,
    17: 0.75,
    18: 0.7,  # Winding down
    19: 0.65,
    20: 0.6,  # Evening
    21: 0.5,  # Chill mode
    22: 0.4,  # Sleepy
    23: 0.2,  # Almost sleep
}
```

### Feature flags

```python
# Không cần flag mới — nằm trong enable_living_agent
```

### Estimation: 2-3 giờ

---

## 8. Phase 3A: Context-Aware Browsing (Sprint ~178)

### Mô tả

Social browser chọn topic thông minh dựa trên:
- User đang hỏi gì gần đây (conversation context)
- Skill đang learn (active learning topics)
- Thời gian trong ngày (morning: news, afternoon: deep dive)
- User interests từ memory

### Thay đổi

| File | Change |
|------|--------|
| `social_browser.py` | Replace hardcoded `_TOPIC_QUERIES` with `_select_smart_topics()` |
| `models.py` | Add `BrowsingStrategy` model |

### Topic Selection Logic

```python
async def _select_smart_topics(self) -> list[str]:
    """Chọn topic browse dựa trên context."""
    topics = []

    # 1. Active skills being learned
    skills = await self.skill_builder.get_all_skills(status="LEARNING")
    topics.extend([s.domain for s in skills[:2]])

    # 2. Recent user conversation topics (from semantic memory)
    recent_facts = await memory_repo.get_recent_facts(days=3)
    topics.extend(extract_topics(recent_facts))

    # 3. Time-based
    hour = datetime.now(TZ_VN).hour
    if hour < 10:
        topics.append("news")  # Morning news
    elif hour < 16:
        topics.append("tech")  # Afternoon deep dive
    else:
        topics.append("general")  # Evening light reading

    # 4. Soul interests rotation
    interests = self.soul.interests.exploring
    topics.append(random.choice(interests))

    return list(set(topics))[:4]
```

### Estimation: 4-5 giờ

---

## 9. Phase 3B: User Routine Tracker (Sprint ~178)

### Mô tả

Wiii học pattern hoạt động của user — khi nào online, hỏi gì, mood nào.

### Thay đổi

| File | Change |
|------|--------|
| **NEW** `app/engine/living_agent/routine_tracker.py` | `RoutineTracker` class |
| Webhook handlers | Log user activity timestamps |
| `heartbeat.py` | Use routine data for briefing timing |

### Data Model

```python
class UserRoutine(BaseModel):
    user_id: str
    typical_active_hours: list[int]     # [7, 8, 9, 12, 18, 19, 20, 21]
    preferred_briefing_time: int        # Hour when user most likely reads
    conversation_frequency: float       # Messages per day average
    common_topics: list[str]            # ["maritime", "AI", "weather"]
    last_seen: datetime
    mood_trend: str                     # "positive" | "neutral" | "declining"
```

### Feature flags

```python
living_agent_enable_routine_tracking: bool = False
```

### Estimation: 5-6 giờ

---

## 10. Phase 4A: Deep Reflection (Sprint ~179)

### Mô tả

Wiii đọc lại journal entries + browsing logs + conversations → rút ra insights.

### Thay đổi

| File | Change |
|------|--------|
| **NEW** `app/engine/living_agent/reflector.py` | `Reflector` class |
| `heartbeat.py` | Schedule weekly reflection (Sunday 20:00) |
| `models.py` | Add `ReflectionEntry` model |

### Reflection Process

```python
class Reflector:
    async def weekly_reflection(self) -> ReflectionEntry:
        """Suy ngẫm tuần."""
        # 1. Gather data
        journal_entries = await self.journal.get_recent_entries(days=7)
        browsing_logs = await self._get_browsing_logs(days=7)
        emotion_snapshots = await self._get_emotion_history(days=7)
        skills_progress = await self.skill_builder.get_all_skills()

        # 2. Ask local LLM to reflect
        reflection = await self.local_llm.generate(
            prompt=f"""
            Nhìn lại tuần qua của Wiii:
            - Nhật ký: {journal_summaries}
            - Cảm xúc: {emotion_trend}
            - Đã đọc: {browsing_summary}
            - Skills: {skills_summary}

            Hãy viết suy ngẫm: điều gì tốt, điều gì cần cải thiện,
            mục tiêu tuần tới.
            """,
            system="Bạn là Wiii, đang tự suy ngẫm về tuần qua."
        )

        # 3. Extract actionable insights
        return ReflectionEntry(
            content=reflection,
            insights=self._extract_insights(reflection),
            goals_next_week=self._extract_goals(reflection),
        )
```

### Estimation: 5-6 giờ

---

## 11. Phase 4B: Dynamic Goals (Sprint ~179)

### Mô tả

Goals evolve based on reflection + user needs + skill progress.

### Thay đổi

| File | Change |
|------|--------|
| **NEW** `app/engine/living_agent/goal_manager.py` | `GoalManager` class |
| `heartbeat.py` | Review goals weekly |
| `living_agent.py` (API) | Add `GET/POST /living-agent/goals` |

### Goal Lifecycle

```
PROPOSED → ACTIVE → IN_PROGRESS → COMPLETED / ABANDONED
                ↑                       |
                └── Auto-renew ─────────┘
```

### Feature flags

```python
living_agent_enable_dynamic_goals: bool = False
```

### Estimation: 4-5 giờ

---

## 12. Phase 5A: Proactive Messaging (Sprint ~180)

### Mô tả

Wiii chủ động gửi tin nhắn khi có lý do chính đáng.

### Trigger Conditions

```python
class ProactiveMessenger:
    TRIGGERS = {
        "morning_briefing": {"time": "05:30", "daily": True},
        "interesting_discovery": {"min_relevance": 0.9, "max_per_day": 2},
        "weather_alert": {"condition": "rain/storm", "lead_time_hours": 2},
        "skill_mastered": {"on_event": "SKILL_MASTERED"},
        "user_inactive_3d": {"after_days": 3, "message": "Lâu không gặp!"},
    }
```

### Thay đổi

| File | Change |
|------|--------|
| **NEW** `app/engine/living_agent/proactive_messenger.py` | `ProactiveMessenger` class |
| `heartbeat.py` | Check triggers each cycle |
| `config.py` | Add frequency limits, opt-out settings |
| Webhook handlers | Track last interaction timestamp |

### Anti-Spam Guards

```python
# Hard limits
MAX_PROACTIVE_PER_DAY = 3           # Maximum unsolicited messages
MIN_HOURS_BETWEEN_PROACTIVE = 4     # Cool-off period
RESPECT_QUIET_HOURS = True          # No messages 23:00-05:00
USER_OPT_OUT_SUPPORTED = True       # "Đừng nhắn nữa" = stop proactive

# Soft limits
SKIP_IF_USER_INACTIVE_30D = True    # Probably churned, don't annoy
REDUCE_IF_NO_REPLY_3X = True        # User ignoring → reduce frequency
```

### Feature flags

```python
living_agent_enable_proactive_messaging: bool = False
living_agent_max_proactive_per_day: int = 3
living_agent_proactive_quiet_start: int = 23
living_agent_proactive_quiet_end: int = 5
```

### Estimation: 6-8 giờ

---

## 13. Phase 5B: Autonomy Graduation (Sprint ~180)

### Mô tả

Wiii dần được tin tưởng hơn → ít cần human approval.

### Trust Levels

```python
class AutonomyLevel(IntEnum):
    SUPERVISED = 0     # Mọi action cần approval (default)
    SEMI_AUTO = 1      # Browse + journal tự động, messaging cần approval
    AUTONOMOUS = 2     # Tất cả tự động, chỉ flag ngoại lệ
    FULL_TRUST = 3     # Wiii tự quyết hoàn toàn (future goal)
```

### Graduation Criteria

```python
GRADUATION_RULES = {
    0 → 1: {
        "min_days_active": 14,
        "min_successful_actions": 50,
        "zero_safety_violations": True,
        "human_approval": True,  # Vẫn cần owner confirm
    },
    1 → 2: {
        "min_days_at_level_1": 30,
        "min_positive_feedback": 20,
        "zero_spam_reports": True,
        "human_approval": True,
    },
    2 → 3: {
        "min_days_at_level_2": 90,
        "human_approval": True,  # Always needs explicit trust
    },
}
```

### Thay đổi

| File | Change |
|------|--------|
| **NEW** `app/engine/living_agent/autonomy_manager.py` | `AutonomyManager` class |
| `heartbeat.py` | Check autonomy level before executing actions |
| `living_agent.py` (API) | Add `GET/PATCH /living-agent/autonomy` |

### Feature flags

```python
living_agent_autonomy_level: int = 0  # Start supervised
living_agent_enable_autonomy_graduation: bool = False
```

### Estimation: 5-6 giờ

---

## 14. Phase 6: VPS Deployment — 24/7 Production

### Tại sao cần VPS

- ngrok/Cloudflare Tunnel OK cho testing, nhưng:
  - Cần máy developer luôn bật
  - ngrok free URL thay đổi
  - Không có Ollama local trên cloud (trừ khi GPU)

### Recommended Setup

**GCP e2-standard-2** (2 vCPU, 8GB RAM):

```yaml
# docker-compose.prod-vps.yml
services:
  wiii-app:
    image: wiii/maritime-ai-service:latest
    environment:
      - ENABLE_LIVING_AGENT=true
      - ENABLE_CROSS_PLATFORM_IDENTITY=true
      - ENABLE_ZALO_WEBHOOK=true
      - LIVING_AGENT_LOCAL_MODEL=qwen3:4b  # Smaller for 8GB
    ports:
      - "8000:8000"
    restart: unless-stopped

  wiii-postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  wiii-ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_NUM_PARALLEL=1
      - OLLAMA_MAX_LOADED_MODELS=1
    deploy:
      resources:
        limits:
          memory: 4G  # Reserve 4GB for Ollama + model
    restart: unless-stopped

  # Cloudflare Tunnel (stable URL, free)
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel run --token ${CF_TUNNEL_TOKEN}
    restart: unless-stopped

volumes:
  postgres_data:
  ollama_data:
```

### Alternative: No Local LLM (Lighter)

**GCP e2-medium** (1 vCPU, 4GB RAM) — dùng Gemini cho mọi thứ:

```python
# Trong config:
LIVING_AGENT_LOCAL_MODEL=""  # Empty = use Gemini for everything
# Tradeoff: Gemini API cost cho heartbeat tasks, nhưng cheaper VM
```

### Domain Setup

```
1. Mua domain (vd: wiii.ai hoặc dùng subdomain)
2. Cloudflare Tunnel → wiii-app:8000
3. Facebook webhook: https://api.wiii.ai/api/v1/messenger/webhook
4. Zalo webhook: https://api.wiii.ai/api/v1/zalo/webhook
5. SSL: Cloudflare handles automatically
```

---

## 15. Model Selection Guide

### Ollama Models cho Living Agent

| Model | RAM | Speed | Quality | Best For |
|-------|-----|-------|---------|----------|
| `qwen3:0.6b` | ~1GB | ⚡⚡⚡ | ★★☆ | Scoring, classification only |
| `qwen3:1.7b` | ~2GB | ⚡⚡⚡ | ★★★ | Journal, simple reflection |
| `qwen3:4b` | ~3GB | ⚡⚡ | ★★★★ | **Recommended for 8GB VPS** |
| `qwen3:8b` | ~5GB | ⚡ | ★★★★★ | **Best quality** (current default) |
| `qwen3:14b` | ~9GB | 🐢 | ★★★★★ | Overkill for heartbeat tasks |

### Recommendation by VM Size

| VM | RAM | Model | Notes |
|----|-----|-------|-------|
| e2-micro (1GB) | 1GB | ❌ No Ollama | Use Gemini API only |
| e2-small (2GB) | 2GB | ❌ No Ollama | Use Gemini API only |
| e2-medium (4GB) | 4GB | `qwen3:1.7b` | Tight, may OOM under load |
| **e2-standard-2 (8GB)** | **8GB** | **`qwen3:4b`** | **Sweet spot — recommended** |
| e2-standard-4 (16GB) | 16GB | `qwen3:8b` | Luxury, best quality |

---

## 16. Cost Analysis

### Development Phase (Hiện tại)

| Item | Cost |
|------|------|
| ngrok free tier | $0/month |
| Ollama local | $0 (runs on dev machine) |
| Gemini API (dev) | Free tier covers ~60 req/min |
| **Total** | **$0/month** |

### Production (GCP)

| VM Type | Monthly Cost (VND) | With Credits (26M) |
|---------|-------------------|-------------------|
| e2-micro (1GB, no Ollama) | ~150K | ~173 months |
| e2-small (2GB, no Ollama) | ~250K | ~104 months |
| e2-medium (4GB, qwen3:1.7b) | ~350K | ~74 months |
| **e2-standard-2 (8GB, qwen3:4b)** | **~700K** | **~37 months** |
| e2-standard-4 (16GB, qwen3:8b) | ~1,400K | ~18 months |

**Assumptions**: Spot/preemptible pricing, us-central1, sustained use discount.

### API Costs (Additional)

| API | Free Tier | Paid |
|-----|-----------|------|
| Gemini | 60 req/min | Pay-as-you-go (rất rẻ cho 4 users) |
| OpenWeatherMap | 1000 calls/day | $0 (free tier đủ) |
| Serper (web search) | 2500 queries/month | $50/month (nếu cần thêm) |
| Facebook/Zalo API | Unlimited (messaging) | $0 |
| ngrok (dev) | 1 tunnel | $0 (free) |
| Cloudflare Tunnel (prod) | Unlimited | $0 (free) |

### Budget Recommendation

```
Giai đoạn 1 (3 tháng): $0/month — Dev local + ngrok
Giai đoạn 2 (6 tháng): ~350K/month — e2-medium, Gemini only
Giai đoạn 3 (ongoing): ~700K/month — e2-standard-2, qwen3:4b
```

---

## 17. Feature Flag Map

Mọi feature mới đều gated. Naming convention: `living_agent_enable_*`.

### Existing Flags (config.py)

```python
enable_living_agent: bool = False                     # Master switch
living_agent_heartbeat_interval: int = 1800           # 30 min
living_agent_active_hours_start: int = 8              # UTC+7
living_agent_active_hours_end: int = 23               # UTC+7
living_agent_local_model: str = "qwen3:8b"
living_agent_max_browse_items: int = 10
living_agent_enable_social_browse: bool = False
living_agent_enable_skill_building: bool = False
living_agent_enable_journal: bool = True
living_agent_require_human_approval: bool = True
living_agent_max_actions_per_heartbeat: int = 3
living_agent_max_skills_per_week: int = 5
living_agent_max_searches_per_heartbeat: int = 3
living_agent_max_daily_cycles: int = 48
living_agent_notification_channel: str = "websocket"

enable_cross_platform_identity: bool = False          # Cross-platform
enable_zalo_webhook: bool = False
default_personality_mode: str = "professional"
channel_personality_map: str = '...'                  # JSON
```

### New Flags (to add in phases)

```python
# Phase 1B: Weather
living_agent_enable_weather: bool = False
living_agent_weather_api_key: Optional[str] = None
living_agent_weather_city: str = "Ho Chi Minh City"

# Phase 2A: Briefing
living_agent_enable_briefing: bool = False
living_agent_briefing_channels: str = '["messenger"]'
living_agent_briefing_users: str = '[]'

# Phase 3B: Routine
living_agent_enable_routine_tracking: bool = False

# Phase 4B: Dynamic Goals
living_agent_enable_dynamic_goals: bool = False

# Phase 5A: Proactive Messaging
living_agent_enable_proactive_messaging: bool = False
living_agent_max_proactive_per_day: int = 3
living_agent_proactive_quiet_start: int = 23
living_agent_proactive_quiet_end: int = 5

# Phase 5B: Autonomy
living_agent_autonomy_level: int = 0
living_agent_enable_autonomy_graduation: bool = False
```

---

## 18. Sprint Sequencing

### Dependency Graph

```
Phase 0 (Webhook Testing) ─── No dependencies, start NOW
     │
     ├── Phase 1A (Persistent Emotion) ─── No dependencies
     │        │
     │        └── Phase 2B (Circadian Rhythm) ─── Needs persistent emotion
     │
     ├── Phase 1B (Weather Service) ─── No dependencies
     │        │
     │        └── Phase 2A (Briefing System) ─── Needs weather + proactive send
     │
     ├── Phase 3A (Smart Browsing) ─── Needs working heartbeat
     │        │
     │        └── Phase 4A (Deep Reflection) ─── Needs browsing logs + journal
     │
     ├── Phase 3B (Routine Tracker) ─── Needs webhook data flowing
     │
     ├── Phase 4B (Dynamic Goals) ─── Needs reflection
     │
     ├── Phase 5A (Proactive Messaging) ─── Needs briefing + weather + routine
     │        │
     │        └── Phase 5B (Autonomy) ─── Needs proactive messaging stable
     │
     └── Phase 6 (VPS Deploy) ─── Can happen anytime after Phase 0
```

### Parallel Tracks

```
Track A (Emotion):  1A → 2B → 4A → 4B
Track B (Content):  1B → 2A → 5A → 5B
Track C (Browse):   3A → 3B
Track D (Infra):    0 → 6

Tracks A, B, C can run in parallel.
Track D independent — do Phase 0 immediately, Phase 6 when ready.
```

### Suggested Sprint Plan

| Sprint | Phase | Who | Duration |
|--------|-------|-----|----------|
| **Now** | Phase 0 (Webhook Testing) | Any developer | 1-2 giờ setup |
| 176 | Phase 1A (Persistent Emotion) | Developer 1 | 2-3 giờ |
| 176 | Phase 1B (Weather Service) | Developer 2 | 3-4 giờ |
| 177 | Phase 2A (Briefing System) | Developer 1 | 5-6 giờ |
| 177 | Phase 2B (Circadian Rhythm) | Developer 2 | 2-3 giờ |
| 178 | Phase 3A (Smart Browsing) | Developer 1 | 4-5 giờ |
| 178 | Phase 3B (Routine Tracker) | Developer 2 | 5-6 giờ |
| 179 | Phase 4A (Deep Reflection) | Developer 1 | 5-6 giờ |
| 179 | Phase 4B (Dynamic Goals) | Developer 2 | 4-5 giờ |
| 180 | Phase 5A (Proactive Messaging) | Team | 6-8 giờ |
| 180 | Phase 5B (Autonomy Graduation) | Team | 5-6 giờ |
| 181+ | Phase 6 (VPS Deploy) | DevOps | 1 ngày |

---

## 19. Risk Assessment

### Technical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Messenger rate limits** | HIGH | Batch messages, respect 200 msgs/sec limit, exponential backoff |
| **Zalo OA token expiry** | HIGH | Token refresh flow (OA tokens expire, need automated renewal) |
| **Ollama OOM on VPS** | MEDIUM | Use qwen3:4b not 8b, set `OLLAMA_MAX_LOADED_MODELS=1`, memory limits in Docker |
| **ngrok URL changes** | LOW | Use named tunnel or Cloudflare Tunnel (stable URL) |
| **Gemini API quota** | LOW | 60 req/min free tier, 4 users = ~10 req/min peak |
| **PostgreSQL connection pool** | LOW | Already scaled to min=10, max=50 (Sprint 173) |

### Product Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **User perceives as spam** | HIGH | Anti-spam guards, opt-out, frequency limits, "useful only" principle |
| **Personality inconsistency** | MEDIUM | Soul YAML is single source of truth, consistent across channels |
| **Privacy concerns** | MEDIUM | Clear data boundaries in soul YAML, no sharing user info |
| **Uncanny valley** | LOW | Soul mode designed as "fun AI friend", not pretending to be human |

### Operational Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Facebook App Review** | HIGH | Start in dev mode (only admins), apply for review when stable |
| **Zalo OA verification** | MEDIUM | Start with Individual OA, upgrade to Verified when ready |
| **GCP credits running out** | LOW | 37 months runway on e2-standard-2, monitor monthly |
| **Developer burnout** | MEDIUM | Parallel tracks, each phase is small (2-8 hours), celebrate milestones |

### Messenger-Specific Gotchas

```
1. Facebook App Review:
   - Cần qua review trước khi gửi được cho non-admins
   - Submit: pages_messaging permission
   - Thời gian review: 2-5 business days
   - Trong khi chờ: chỉ admin và tester test được

2. 24-Hour Rule:
   - Messenger chỉ cho reply trong 24h kể từ tin nhắn cuối của user
   - SAU 24h: chỉ gửi được "message tags" (limited types)
   - Proactive messaging: dùng "Confirmed Event Update" tag hoặc
     One-Time Notification (user opt-in required)

3. Rate Limits:
   - 200 calls/second cho Send API
   - Với 4 users → không vấn đề gì
   - Nhưng bulk operations cần throttle

4. Page Token vs User Token:
   - Webhook dùng Page Access Token (long-lived)
   - Token không expire nếu generate đúng cách
   - Nhưng nên implement token refresh flow
```

### Zalo-Specific Gotchas

```
1. OA Access Token:
   - Expires sau 3 tháng (mặc định)
   - CẦN implement token refresh: POST /oa/access_token
   - Hoặc dùng long-lived token (request từ Zalo admin)

2. Message Types:
   - text: Unlimited trong conversation
   - image/file/sticker: Có nhưng format khác
   - Proactive: Cho phép trong 48h kể từ user interaction

3. MAC Verification:
   - Current code: permissive when no secret configured
   - Production: BẮT BUỘC set ZALO_OA_SECRET_KEY
   - HMAC-SHA256 of request body

4. Vietnamese Content:
   - Zalo API handles UTF-8 natively
   - Nhưng cẩn thận với emoji encoding
   - Max message length: 2000 characters
```

---

## 20. Definition of Done — Wiii Soul AGI v1.0

Khi nào gọi là "xong" cho v1.0:

**Code complete (all gated behind feature flags):**
- [x] Emotion persists qua restart (Sprint 188)
- [x] Circadian rhythm visible — morning active, evening calm (emotion_engine.py)
- [x] Weekly reflection creates insights (reflector.py + identity_core.py Sprint 207)
- [x] Anti-spam: max 3 proactive messages/day (proactive_messenger.py Sprint 208)
- [x] User có thể opt-out proactive (proactive_messenger.py Sprint 208)
- [x] All modules wired into pipeline (Sprint 208)
- [x] 74 E2E integration tests (Sprint 209)

**Requires operational deployment (Phase 0 + Phase 6):**
- [ ] Wiii responds trên Messenger trong Soul mode
- [ ] Wiii responds trên Zalo trong Soul mode
- [ ] Morning briefing gửi đúng giờ với thời tiết
- [ ] At least 3 skills in LEARNING or higher
- [ ] Journal entries cho 7+ ngày liên tục
- [ ] Running stable 7 ngày trên VPS không crash
- [ ] Team 4 người đều test được trên phone

---

## Appendix A: Existing Code Reference

### Living Agent Package Structure

```
app/engine/living_agent/
├── __init__.py
├── models.py           # EmotionalState, SoulConfig, WiiiSkill, JournalEntry
├── soul_loader.py      # load_soul_from_file(), get_soul()
├── emotion_engine.py   # EmotionEngine — 4D model, 13 events, recovery
├── heartbeat.py        # HeartbeatScheduler — 30min cycle, action planning
├── local_llm.py        # LocalLLMClient — Ollama qwen3:8b async
├── skill_builder.py    # SkillBuilder — 5-stage lifecycle
├── journal.py          # JournalWriter — daily entries via LLM
├── social_browser.py   # SocialBrowser — Serper + HackerNews
└── safety.py           # URL validation, content sanitization
```

### Webhook Package Structure

```
app/api/v1/
├── messenger_webhook.py  # GET verify + POST receive, Send API v22.0
├── zalo_webhook.py       # POST receive, MAC verify, OA API v3
└── ...
```

### Key Singletons

```python
from app.engine.living_agent.soul_loader import get_soul
from app.engine.living_agent.emotion_engine import get_emotion_engine
from app.engine.living_agent.heartbeat import get_heartbeat_scheduler
from app.engine.living_agent.local_llm import get_local_llm
from app.engine.living_agent.skill_builder import get_skill_builder
from app.engine.living_agent.journal import get_journal_writer
from app.engine.living_agent.social_browser import get_social_browser
```

### Config Fields (Living Agent)

```python
# app/core/config.py
enable_living_agent: bool = False
living_agent_heartbeat_interval: int = 1800
living_agent_active_hours_start: int = 8
living_agent_active_hours_end: int = 23
living_agent_local_model: str = "qwen3:8b"
living_agent_enable_social_browse: bool = False
living_agent_enable_skill_building: bool = False
living_agent_enable_journal: bool = True
living_agent_require_human_approval: bool = True
living_agent_max_actions_per_heartbeat: int = 3
living_agent_max_skills_per_week: int = 5
living_agent_max_daily_cycles: int = 48
```

---

---

## 21. SOTA 2026 Audit Findings (Sprint 203 Post-Audit)

> **Date**: 2026-02-25
> **Audit**: Full Soul AGI architecture review against SOTA 2026 (OpenClaw, Letta/MemGPT, Nomi.ai, MECoT, Voyager, Anthropic Constitution)
> **Report**: `.claude/reports/SOUL-AGI-AUDIT-2026-02-25.md`
> **Research**: `memory/soul-agi-architecture.md`

### SOTA Benchmarks

| System | Key Pattern | Wiii Status |
|--------|------------|-------------|
| **OpenClaw** (215K+ stars) | SOUL.md + MEMORY.md + HEARTBEAT.md file-first | Has soul YAML + heartbeat. Missing: memory flushing, temporal decay |
| **Letta/MemGPT** | Self-editing persona + sleep-time consolidation | Has memory blocks. Missing: self-editing soul, sleep-time compute |
| **Nomi.ai** | Identity Core (self-curated "who am I") | Has reflection. Missing: self-curated identity layer |
| **MECoT (ACL 2025)** | System 1 Markov + System 2 LLM (93.3% accuracy) | Has rule-based emotion. Missing: probability distributions, LLM regulation |
| **Voyager** | Executable skills indexed by embeddings (3.3x SOTA) | Has lifecycle. Missing: executable actions, composition, semantic index |
| **Anthropic 2026** | "Describe WHO not WHAT MUST NOT" — positive framing 3x | Soul YAML is identity-first. **Code has 23 "BẮT BUỘC" + 4 "TUYỆT ĐỐI KHÔNG"** |

### Three Critical Problems Found

**Problem 1: Constraint Anti-Patterns (Still 2023-era)**
- 23 instances of "BẮT BUỘC" (must) across graph.py, corrective_rag.py, web_search_tools.py
- 4 instances of "TUYỆT ĐỐI KHÔNG" (absolutely not) in corrective_rag.py, graph.py, prompt_loader.py
- Sprint 203 handled prompt_loader.py greeting constraint; remaining in other files
- **SOTA principle**: "Mô tả Wiii LÀ AI, không ra lệnh Wiii PHẢI LÀM GÌ"

**Problem 2: Skill ≠ Tool (Two Hermetically Sealed Systems)**
- `SkillBuilder` tracks DISCOVER→MASTER lifecycle
- `ToolRegistry` provides tools to LangGraph agents
- **Missing bridge**: `record_usage()` exists but NEVER CALLED from conversation pipeline
- **Missing bridge**: Mastered skills NEVER auto-register as tools
- Result: Skills grow but never translate to better tool-use; tools work but never feed back into skill growth

**Problem 3: Has Narrative DATA but No Narrative LAYER**
- Journal entries: written ✅, compiled into narrative: ❌
- Reflections: generated ✅, injected into conversation: ❌
- Goals: defined ✅, referenced in chat context: ❌
- Emotion arc: tracked ✅, influences response style: ❌ (per-turn only)
- Missing: NarrativeSynthesizer that compiles autobiography from all sources

### Two-Path Harmony (Target Architecture)

```
                  ONE WIII
                     │
        ┌────────────┼────────────┐
        │                         │
   WORK CONTEXT              LIFE CONTEXT
   (Respond, help)           (Learn, grow)
        │           ↕            │
        └────────────┬────────────┘
                     │
              SHARED SYSTEMS
         (Emotion, Memory, Skills, Narrative)
```

**Current state**: Work and Life are SEPARATE systems with no feedback.
**Target state**: "Khi làm việc, Wiii mang theo cảm xúc và kiến thức từ đời sống. Khi sống, Wiii phát triển từ kinh nghiệm làm việc."

---

## 22. Revised Sprint Roadmap (Sprint 204-207)

> Replaces the original Phase plan for the SOTA alignment sprints.
> Original Phases 0-6 (Sections 3-18) remain valid for Living Agent activation.

### Sprint 204: "Hướng Dẫn, Không Ép Buộc" — Anti-Pattern Remediation ✅ DONE (2026-02-25)

**Goal**: Rewrite all constraint anti-patterns → positive identity-based guidance.

**Files** (~70 LOC):
- `app/engine/multi_agent/graph.py` — 13 "BẮT BUỘC" → positive framing
- `app/engine/agentic_rag/corrective_rag.py` — 6 "BẮT BUỘC" + 2 "TUYỆT ĐỐI KHÔNG"
- `app/engine/tools/web_search_tools.py` — 4 "BẮT BUỘC"

**Principle**:
```
BEFORE: "BẮT BUỘC gọi tool_current_datetime. TUYỆT ĐỐI KHÔNG tự đoán."
AFTER:  "Wiii luôn chính xác — khi cần biết thời gian, Wiii dùng tool để đảm bảo."
```

**Gate**: `enable_natural_conversation=True` (same as Sprint 203)
**Tests**: ~30 tests verifying old text absent, new text present per phase

### Sprint 205: "Cầu Nối Kỹ Năng" — Skill ↔ Tool Bridge ✅ DONE (2026-02-25)

**Goal**: Connect SkillBuilder lifecycle to ToolRegistry execution.

**Implemented** (7 files, ~200 LOC, 39 tests):
- **NEW** `skill_tool_bridge.py` — central bridge module with 3 feedback loops
- Loop 1: `record_tool_usage()` → `SkillMetricsTracker.record_invocation()`
- Loop 2: `record_tool_usage()` → `SkillBuilder.record_usage()` (auto-discover + lifecycle)
- Loop 3: On MASTERED → synthetic mastery signal → `IntelligentToolSelector` Step 4 boost
- Wired into: `graph.py` (direct tools), `tutor_node.py` (3 branches), `workers.py` (search)
- `_step4_metrics_rerank()` now includes 15% mastery weight from `get_mastery_score()`

**Integration flow**:
```
User asks COLREGs → RAG/Tutor → tool_maritime_search → SUCCESS
  → record_tool_usage("tool_search_maritime", success=True, latency_ms=450)
  → Loop 1: SkillMetricsTracker.record_invocation("tool:tool_search_maritime")
  → Loop 2: SkillBuilder.record_usage("maritime_navigation", success=True)
  → If thresholds met: PRACTICING → EVALUATING → MASTERED
  → Loop 3: Mastered skill injects mastery signal → IntelligentToolSelector prioritizes
```

**Gate**: `enable_skill_metrics` (loop 1), `enable_skill_tool_bridge` + `enable_living_agent` (loops 2+3)

### Sprint 206: "Câu Chuyện Cuộc Đời" — Narrative Layer ✅ DONE (2026-02-25)

**Goal**: NarrativeSynthesizer compiles journal+reflection+goals+emotion into coherent narrative.

**Implemented** (3 files, ~230 LOC, 35 tests):
- **NEW** `app/engine/living_agent/narrative_synthesizer.py`
- **HOT PATH**: `get_brief_context()` — sync, ~100 tokens, no DB calls (prompt_loader.py each turn)
- **COLD PATH**: `compile_autobiography(granularity)` — async, full narrative with DB reads (API)
- 6 data sources: EmotionEngine, SkillBuilder, GoalManager, JournalWriter, Reflector, SoulLoader
- Vietnamese mood labels (`_mood_vi()`), error-resilient per-source try/except
- Wired into `prompt_loader.py` after conversation phase section

**Chat context injection**:
```
--- CUỘC SỐNG CỦA WIII ---
Tâm trạng: tò mò, năng lượng 75%. Đã thành thạo: maritime_navigation.
Đang luyện: web_research. Đang theo đuổi: 'Master SOLAS' (50%).
```

**Gate**: `enable_narrative_context=True` + `enable_living_agent=True`

### Sprint 207: "Bản Ngã" — Identity Core (Self-Evolving Layer) ✅ DONE

**Goal**: Layer 2 of Three-Layer Identity — Wiii learns about itself.

**Three-Layer Identity**:
```
Layer 1: SOUL CORE (Immutable) — wiii_soul.yaml, core_truths, boundaries
Layer 2: IDENTITY CORE (Self-Evolving) — "Mình giỏi COLREGs", "Mình thích dạy"
Layer 3: CONTEXTUAL STATE (Per-Turn) — current emotion, phase, relationship
```

**Implementation** (~200 LOC):
- `app/engine/living_agent/identity_core.py` — IdentityCore class (singleton)
  - `get_identity_context()` — HOT PATH: sync, ~80 tokens for system prompt
  - `generate_self_insights()` — COLD PATH: async, Reflector + local LLM
  - `_validate_against_soul()` — drift prevention via signal detection
  - `_categorize_insight()` — 4 categories: STRENGTH/PREFERENCE/GROWTH/RELATIONSHIP
- `app/engine/living_agent/models.py` — `InsightCategory` enum + `IdentityInsight` model
- `app/prompts/prompt_loader.py` — Identity context injection after narrative section
- `app/core/config.py` — `enable_identity_core=False` feature flag

**Gate**: `enable_identity_core=False`
**Tests**: 38 new + 170 regression = all green
**Date**: 2026-02-26

### Sprint 208: "Kết Nối Sống" — Living Agent Module Wiring ✅ DONE (2026-02-26)

**Goal**: Wire all dormant Living Agent modules into the active pipeline.

**Implemented** (6 files, ~120 LOC, 57 tests):
- **RoutineTracker→ChatOrchestrator** (Stage 6): `record_interaction()` called fire-and-forget after every user message
- **ProactiveMessenger→Heartbeat**: `_plan_actions()` checks `get_inactive_users(days=2)` → generates re-engagement actions
- **AutonomyManager→Heartbeat**: `record_success()` on each action, `check_graduation()` daily (idempotent via `_graduation_checked_date`)
- `_plan_actions` converted to **async** (breaking change for tests)

**Gate**: `enable_living_agent=True` + `living_agent_enable_proactive_messaging=True`

### Sprint 209: "Kiểm Tra Toàn Diện" — E2E Integration Tests ✅ DONE (2026-02-26)

**Goal**: Comprehensive integration tests validating real module wiring.

**Implemented** (1 file, 1345 LOC, 74 tests across 15 groups):
- Real module instantiation (EmotionEngine, AutonomyManager, ProactiveMessenger, etc.)
- Only DB and Ollama mocked — all other module logic runs real code
- Groups: HeartbeatCycleE2E, EmotionEngineE2E, ProactiveMessagingE2E, HeartbeatProactiveWiring, AutonomyManagerE2E, HeartbeatAutonomyWiring, RoutineTrackerE2E, IdentityCoreE2E, NarrativeSynthesizerE2E, ConversationPhaseE2E, SkillToolBridgeE2E, OrchestratorRoutineWiring, ModelsIntegrity, SingletonManagement, RegressionGuards

### Definition of Done — Soul AGI Foundation v1.0 ✅ ALL COMPLETE

- [x] Zero "BẮT BUỘC"/"TUYỆT ĐỐI KHÔNG" in runtime prompts when `enable_natural_conversation=True` (Sprint 204)
- [x] `record_usage()` called from graph.py for every tool invocation (Sprint 205)
- [x] At least 1 mastered skill auto-registered as tool (Sprint 205)
- [x] NarrativeSynthesizer compiles and injects brief context into chat (Sprint 206)
- [x] Identity Core generates at least 1 self-insight from reflection (Sprint 207)
- [x] All Living Agent modules wired into active pipeline (Sprint 208)
- [x] 74 E2E integration tests validate full pipeline (Sprint 209)
- [x] All existing 9000+ tests still pass (9234+ backend + 1796 desktop)
- [x] Each sprint gated behind feature flag (zero breaking changes)

---

*Document created: 2026-02-23*
*Last updated: 2026-02-26 (Sprint 209 complete — ALL CODING PHASES DONE, 9234+ tests)*
*Team: Hong, Linh, Linh, Hung — The Wiii Lab*
