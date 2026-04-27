# Hướng Dẫn Tích Hợp Wiii AI — Dành Cho Đội LMS

> **Version:** 4.0.0
> **Last Updated:** 2026-03-03
> **Sprint:** 221 "Mắt Thần" — Page-Aware AI Context (E2E Verified)
> **For:** Đội LMS (Backend Spring Boot + Frontend Angular)
> **Reference:** [`WIII_LMS_INTEGRATION.md`](./WIII_LMS_INTEGRATION.md) (full technical spec)
> **Production LMS Domain:** `https://holilihu.online`

---

## 1. Wiii là gì?

Wiii là trợ lý AI giáo dục do **The Wiii Lab** phát triển. Wiii giúp sinh viên tra cứu kiến thức, ôn thi, hỏi đáp bài tập. Cho giảng viên: dashboard phân tích, phát hiện sinh viên nguy cơ, báo cáo AI. Wiii chạy trên FastAPI + WiiiRunner, giao tiếp qua REST + SSE, bảo mật bằng HMAC-SHA256 + JWT.

---

## 2. Checklist Biến Môi Trường

### LMS Backend (`application.yml` hoặc `application-dev.yml`)

```yaml
# === WIII AI INTEGRATION ===
wiii:
  base-url: ${WIII_BASE_URL:http://localhost:8000/api/v1}
  webhook:
    secret: ${WIII_WEBHOOK_SECRET:change-me-in-production}
    enabled: true
  service-token: ${WIII_SERVICE_TOKEN:change-me-in-production}
  connector-id: maritime-lms
```

Checklist:
- [ ] `wiii.base-url` — URL của Wiii backend (dev: `http://localhost:8000/api/v1`, prod: `https://ai.maritime.edu/api/v1`)
- [ ] `wiii.webhook.secret` — Shared HMAC secret (phải khớp với Wiii `LMS_WEBHOOK_SECRET`)
- [ ] `wiii.service-token` — Bearer token cho Wiii gọi ngược lại (phải khớp trong Wiii config)
- [ ] `wiii.connector-id` — Mặc định `maritime-lms`
- [ ] `@EnableAsync` trên `Application.java` (cho async webhook sending)

### LMS Frontend (`environment.ts`)

```typescript
export const environment = {
  production: false,
  aiServiceUrl: '/api/v3/ai',  // Proxy through LMS backend
};
```

- [ ] `aiServiceUrl` trỏ qua LMS proxy (KHÔNG trỏ trực tiếp Wiii)

### Secret Generation (Production)

```bash
# Generate strong secrets
openssl rand -hex 32   # → dùng cho WIII_WEBHOOK_SECRET
openssl rand -hex 32   # → dùng cho WIII_SERVICE_TOKEN
```

---

## 3. Endpoints LMS Phải Expose (cho Wiii gọi đến)

Wiii sẽ gọi đến 7 GET + 2 POST + 2 GET endpoints trên LMS. Tất cả dưới path prefix:
```
/api/v3/integration/
```

Auth: `Authorization: Bearer {service_token}` (Wiii gửi, LMS verify bằng `WiiiServiceAuthFilter`).

### 3.1 Student Data — 7 GET endpoints

| # | Method | Path | Response Type |
|---|--------|------|---------------|
| 1 | GET | `/students/{id}/profile` | JSON object |
| 2 | GET | `/students/{id}/grades` | JSON array |
| 3 | GET | `/students/{id}/assignments/upcoming` | JSON array |
| 4 | GET | `/students/{id}/enrollments` | JSON array |
| 5 | GET | `/students/{id}/quiz-history` | JSON array |
| 6 | GET | `/courses/{id}/students` | JSON array |
| 7 | GET | `/courses/{id}/stats` | JSON object |

#### Student Profile Response

```json
{
  "id": "0bad5ba8-fdbd-4abf-9cfc-e7b852335512",
  "name": "nguyenvanan",
  "full_name": "Nguyễn Văn An",
  "email": "nguyenvanan@sv.maritime.edu",
  "role": "STUDENT",
  "class_name": null,
  "program": null,
  "enrolled_courses": ["Chữa Cháy Nâng Cao và Cứu Hộ", "Hệ Thống Dẫn Đường Điện Tử ECDIS và Radar/ARPA", "Khí Tượng Hải Dương và Điều Động Tàu"]
}
```

#### Student Grades Response

```json
[
  {
    "course_id": "a8bf31c7-2d39-...",
    "course_name": "Khí Tượng Hải Dương và Điều Động Tàu",
    "class_name": "Lop KT-2026A",
    "grade": 7.5,
    "max_grade": 100.0,
    "date": "2026-02-20T..."
  }
]
```

> **Sprint 220c**: `course_name` phải từ `courses.title` (tên môn), `class_name` từ `learning_classes.name` (tên lớp). SQL cần JOIN qua `courses c ON lc.course_id = c.id`.

#### Upcoming Assignments Response

```json
[
  {
    "assignment_id": "027a976f-...",
    "assignment_name": "Bai tap tong hop ECDIS-Radar",
    "course_id": "f127c080-...",
    "course_name": "Hệ Thống Dẫn Đường Điện Tử ECDIS và Radar/ARPA",
    "class_name": "Lop ECDIS-2026A",
    "due_date": "2026-03-27 19:00:54.275517+00"
  }
]
```

#### Course Stats Response

```json
{
  "students_count": 45,
  "avg_grade": 6.8,
  "completion_rate": 72,
  "active_last_7d": 38,
  "at_risk_count": 5
}
```

### 3.2 AI Push Receivers — 2 POST + 2 GET endpoints

#### POST `/api/v3/integration/insights` — Nhận AI insight

Wiii sẽ POST insights đến LMS. LMS lưu vào bảng `ai_insights`.

```json
{
  "student_id": "SV12345",
  "insight_type": "recommendation",
  "content": "Sinh viên cần ôn tập thêm về COLREG Rule 13-17...",
  "source": "wiii_ai",
  "timestamp": "2026-02-23T10:30:00Z",
  "metadata": {}
}
```

Insight types: `recommendation`, `alert`, `summary`

#### POST `/api/v3/integration/alerts` — Nhận class alert

```json
{
  "course_id": "NHH101",
  "alert_type": "at_risk_student",
  "content": "3 sinh viên có nguy cơ cao...",
  "student_ids": ["SV12345", "SV12346"],
  "source": "wiii_ai",
  "timestamp": "2026-02-23T10:30:00Z"
}
```

Alert types: `at_risk_student`, `low_engagement`, `content_gap`

#### GET `/api/v3/integration/insights/{student_id}` — Đọc lại insights

#### GET `/api/v3/integration/alerts/{course_id}` — Đọc lại alerts

---

## 4. Webhook Events Phải Emit (LMS → Wiii)

Khi các sự kiện xảy ra trong LMS, gửi webhook đến Wiii để AI hiểu ngữ cảnh sinh viên.

**Endpoint**: `POST {wiii_base_url}/lms/webhook/{connector_id}`
**Auth**: `X-LMS-Signature: sha256={hmac_hex}`

### 4.1 Envelope Format

```json
{
  "event_type": "grade_saved",
  "timestamp": "2026-02-23T10:30:00Z",
  "payload": { ... },
  "source": "spring_boot_lms"
}
```

### 4.2 Khi nào gửi?

| Event Type | Khi nào | Payload chính |
|------------|---------|---------------|
| `grade_saved` | Giảng viên chấm điểm | student_id, course_id, grade, max_grade |
| `course_enrolled` | Sinh viên đăng ký môn | student_id, course_id, course_name, semester |
| `quiz_completed` | Sinh viên nộp bài kiểm tra | student_id, quiz_id, score, max_score |
| `assignment_submitted` | Sinh viên nộp bài tập | student_id, assignment_id, submitted_at |
| `attendance_marked` | Điểm danh | student_id, course_id, date, status (present/absent/late) |

### 4.3 Payload Mẫu Đầy Đủ

```json
{
  "event_type": "grade_saved",
  "timestamp": "2026-02-23T10:30:00Z",
  "payload": {
    "student_id": "SV12345",
    "course_id": "NHH101",
    "course_name": "Điều khiển tàu biển 1",
    "grade": 7.5,
    "max_grade": 10.0,
    "assignment_name": "Bài kiểm tra giữa kỳ"
  },
  "source": "spring_boot_lms"
}
```

### 4.4 HMAC Signing (Java)

```java
// WiiiWebhookEmitter.java
@Async
public void emit(String eventType, Map<String, Object> payload) {
    String body = objectMapper.writeValueAsString(Map.of(
        "event_type", eventType,
        "timestamp", Instant.now().toString(),
        "payload", payload,
        "source", "spring_boot_lms"
    ));

    String signature = sign(body);

    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_JSON);
    headers.set("X-LMS-Signature", signature);

    restTemplate.postForEntity(
        wiiiBaseUrl + "/lms/webhook/" + connectorId,
        new HttpEntity<>(body, headers),
        Map.class
    );
}

private String sign(String payload) {
    Mac mac = Mac.getInstance("HmacSHA256");
    mac.init(new SecretKeySpec(
        webhookSecret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"
    ));
    byte[] hash = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
    return "sha256=" + HexFormat.of().formatHex(hash);
}
```

### 4.5 Wiii Response

```json
{
  "status": "accepted",
  "event_type": "grade_saved",
  "facts_created": 2,
  "message": "Enrichment complete"
}
```

---

## 5. Token Exchange & Đồng Bộ User

### 5.1 Cách Wiii Tạo/Tìm User (Identity Federation)

Wiii và LMS là **2 hệ thống riêng biệt**, mỗi bên có bảng `users` riêng. Đội LMS **không cần** tạo user bên Wiii trước. Khi token exchange được gọi, Wiii tự động tạo hoặc tìm user:

```
Lần đầu sinh viên SV12345 dùng AI chat:
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Tìm (lms, SV12345, maritime-lms) trong DB          │
│         → Chưa có → tiếp Step 2                            │
│                                                             │
│ Step 2: Tìm user theo email sv12345@vimaru.edu.vn           │
│         → Chưa có → tiếp Step 3                            │
│                                                             │
│ Step 3: Tạo user MỚI (UUID: 550e8400-...)                  │
│         + Lưu liên kết: (lms, SV12345, maritime-lms)        │
│         → Trả về UUID + JWT                                │
└─────────────────────────────────────────────────────────────┘

Lần 2+ (cùng sinh viên):
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Tìm (lms, SV12345, maritime-lms) trong DB          │
│         → TÌM THẤY → Trả về user cũ ngay (nhanh)          │
└─────────────────────────────────────────────────────────────┘
```

**Quy tắc quan trọng:**
- `lms_user_id` + `connector_id` = unique key → luôn trả về cùng Wiii user cho cùng sinh viên
- Email trùng giữa 2 sinh viên → **không bị gộp** (LMS email chưa verified, Wiii bảo vệ bằng `email_verified=False`)
- Wiii UUID được trả về trong response `user.id` — LMS có thể cache nếu cần

### 5.2 Token Exchange Step-by-step

Khi frontend Angular cần gọi Wiii AI, LMS backend exchange token cho user.

1. Angular gọi `POST /api/v3/ai/token` (với session cookie)
2. LMS backend build JSON: `{connector_id, lms_user_id, email, name, role, timestamp}`
3. LMS sign body bằng HMAC-SHA256 (`wiii.webhook.secret`)
4. LMS gọi Wiii: `POST /auth/lms/token` với header `X-LMS-Signature`
5. Wiii verify HMAC → tìm/tạo user (xem 5.1) → tạo JWT → trả về `{access_token, refresh_token, expires_in, user}`
6. LMS cache token (14 phút, auto-refresh)
7. LMS trả `access_token` cho Angular

### Java Implementation

```java
// WiiiTokenExchangeAdapter.java
public WiiiTokenResponse exchangeToken(String userId, String email,
                                        String name, String role) {
    long timestamp = Instant.now().getEpochSecond();

    // Sprint 220c SSOT: KHÔNG gửi organization_id — Wiii tự resolve từ connector_id
    Map<String, Object> body = Map.of(
        "connector_id", connectorId,
        "lms_user_id", userId,
        "email", email,
        "name", name,
        "role", mapRole(role),
        "timestamp", timestamp
    );

    String jsonBody = objectMapper.writeValueAsString(body);
    String signature = sign(jsonBody);

    // QUAN TRỌNG: Phải dùng HTTP/1.1 (Uvicorn không hỗ trợ h2c cleartext)
    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create(wiiiBaseUrl + "/auth/lms/token"))
        .version(HttpClient.Version.HTTP_1_1)
        .header("Content-Type", "application/json")
        .header("X-LMS-Signature", signature)
        .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
        .build();

    HttpResponse<String> response = httpClient.send(request,
        HttpResponse.BodyHandlers.ofString());

    return objectMapper.readValue(response.body(), WiiiTokenResponse.class);
}

private String mapRole(String lmsRole) {
    return switch (lmsRole.toUpperCase()) {
        case "ROLE_TEACHER", "ROLE_INSTRUCTOR" -> "teacher";
        case "ROLE_ADMIN" -> "admin";
        default -> "student";
    };
}
```

> **Sprint 220c Thay Đổi Quan Trọng:**
> - LMS **KHÔNG gửi `organization_id`** trong request nữa — Wiii là SSOT, tự resolve từ `connector_id`
> - Phải dùng `HttpClient.Version.HTTP_1_1` — Uvicorn không hỗ trợ HTTP/2 cleartext (h2c)
> - Wiii response sẽ chứa `organization_id` đã resolve — Angular đọc từ response

### Angular Token Service

```typescript
// ai-token.service.ts
@Injectable({ providedIn: 'root' })
export class AiTokenService {
  private token = signal<string | null>(null);
  private expiresAt = signal<number>(0);

  constructor(private http: HttpClient) {}

  async getToken(): Promise<string> {
    if (this.token() && Date.now() < this.expiresAt()) {
      return this.token()!;
    }
    const res = await firstValueFrom(
      this.http.post<TokenResponse>('/api/v3/ai/token', {})
    );
    this.token.set(res.access_token);
    this.expiresAt.set(Date.now() + (res.expires_in - 60) * 1000); // refresh 1min early
    return res.access_token;
  }
}
```

---

## 6. Test Integration

### 6.1 Health Check

```bash
# Wiii LMS auth health
curl -s http://localhost:8000/api/v1/auth/lms/health | jq .
```

Expected:
```json
{"status": "ok", "enabled": true, "connectors": ["maritime-lms"], "has_flat_secret": true}
```

### 6.2 Token Exchange

```bash
# Generate HMAC signature
SECRET="your-shared-secret"
BODY='{"connector_id":"maritime-lms","lms_user_id":"SV12345","email":"test@vimaru.edu.vn","name":"Test Student","role":"student","timestamp":'$(date +%s)'}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

curl -X POST http://localhost:8000/api/v1/auth/lms/token \
  -H "Content-Type: application/json" \
  -H "X-LMS-Signature: sha256=$SIGNATURE" \
  -d "$BODY" | jq .
```

### 6.3 Webhook

```bash
SECRET="your-shared-secret"
BODY='{"event_type":"grade_saved","timestamp":"2026-02-23T10:00:00Z","payload":{"student_id":"SV12345","course_id":"NHH101","course_name":"DKTB1","grade":7.5,"max_grade":10},"source":"spring_boot_lms"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

curl -X POST http://localhost:8000/api/v1/lms/webhook/maritime-lms \
  -H "Content-Type: application/json" \
  -H "X-LMS-Signature: sha256=$SIGNATURE" \
  -d "$BODY" | jq .
```

### 6.4 Student Data (sử dụng JWT từ token exchange)

```bash
TOKEN="eyJ..."  # from token exchange response

# Student grades
curl -H "X-API-Key: your-api-key" \
     -H "X-User-ID: uuid-from-exchange" \
     -H "X-Role: student" \
     http://localhost:8000/api/v1/lms/students/SV12345/grades | jq .

# Course overview (teacher only)
curl -H "X-API-Key: your-api-key" \
     -H "X-User-ID: teacher-001" \
     -H "X-Role: teacher" \
     http://localhost:8000/api/v1/lms/dashboard/courses/NHH101/overview | jq .
```

### 6.5 Chat Stream

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream/v3 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-User-ID: uuid-from-exchange" \
  -H "X-Session-ID: test-session" \
  -H "X-Role: student" \
  -H "X-Organization-ID: maritime-lms" \
  -d '{"message":"Giải thích Rule 15 COLREG","domain_id":"maritime","organization_id":"maritime-lms"}'
```

---

## 7. Troubleshooting

| Triệu chứng | Nguyên nhân | Giải pháp |
|-------------|-------------|-----------|
| 401 `Invalid HMAC signature` | Secret không khớp giữa 2 bên | Verify `LMS_WEBHOOK_SECRET` (Wiii) = `wiii.webhook.secret` (LMS) |
| 401 `Missing signature` | Không gửi header `X-LMS-Signature` | Thêm HMAC header khi gọi webhook/token |
| 400 `timestamp is required in production` | Thiếu timestamp trong production | Thêm `"timestamp": <unix_epoch>` vào body |
| 400 `Request timestamp too far` | Clock skew giữa 2 server >5 phút | Sync NTP trên cả 2 server |
| 404 `LMS integration disabled` | Feature flag chưa bật | Set `ENABLE_LMS_INTEGRATION=true` trong Wiii `.env` |
| 404 `LMS connector not found` | `connector_id` không tồn tại | Kiểm tra `LMS_CONNECTORS` JSON hoặc connector registry |
| 403 `Bạn chỉ có thể xem dữ liệu của chính mình` | Student truy cập dữ liệu người khác | Role phải là teacher/admin để xem dữ liệu người khác |
| 429 Rate limited | Quá nhiều request | Tăng cache, giảm tần suất gọi |
| 502/503 Wiii không phản hồi | Wiii backend chưa chạy | Kiểm tra `docker compose up` hoặc `uvicorn` |
| SSE stream bị ngắt | Timeout proxy | Tăng timeout LMS proxy (khuyến nghị 60s cho SSE) |
| Circuit breaker mở | 5 lỗi liên tiếp từ LMS API | Kiểm tra LMS backend health, chờ 120s recovery |
| Token exchange trả 500 | DB hoặc user service lỗi | Kiểm tra Wiii logs, PostgreSQL connection |
| Data Pull trả 500 | SQL schema mismatch trong `WiiiDataControllerV3.java` | Xác minh column names: `enrollments.class_id` (KHÔNG phải `learning_class_id`), `qa.submitted_at`/`qa.started_at` (KHÔNG phải `end_time`/`start_time`). Quiz→Course join: `quiz_attempts→quizzes→lessons→chapters→courses` |
| HMAC valid nhưng Wiii reject 401 | `dict(request.headers)` Starlette lowercase keys | Wiii đã fix case-insensitive lookup (Sprint 220). Nếu custom header, luôn so sánh `.lower()` |
| Docker containers không kết nối được | 2 service trên Docker network khác nhau | `docker network connect <target_network> <container_name>` để bridge |

---

## Tài liệu liên quan

- **Full API Contract**: [`WIII_LMS_INTEGRATION.md`](./WIII_LMS_INTEGRATION.md)
- **Deployment Guide**: [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md)
- **Wiii System Architecture**: [`../architecture/SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md)

---

---

## 8. Iframe Embed (Sprint 220b/220c)

Từ Sprint 220b, LMS **nhúng trực tiếp Wiii** qua iframe thay vì proxy qua Spring Boot.

### 8.1 Angular Iframe URL

```typescript
// Angular chat component — tạo iframe URL
const wiiiEmbedUrl = `${wiiiBaseUrl}/embed#token=${accessToken}&refresh_token=${refreshToken}&org=${orgId}&domain=maritime&session_id=${sessionId}`;
```

> **Lưu ý**: Token truyền qua URL **hash** (`#`) — KHÔNG phải query string (`?`). Hash không gửi lên server, an toàn hơn.

### 8.2 CSP Frame-Ancestors

Wiii server trả header CSP cho phép iframe từ LMS domain:
```
Content-Security-Policy: frame-ancestors 'self' https://holilihu.online
```

Nếu production domain thay đổi, cần update `EMBED_ALLOWED_ORIGINS` trong Wiii `.env`.

### 8.3 E2E Verification Status (Sprint 220c)

| Endpoint | Status | Verified |
|----------|--------|----------|
| `/students/{id}/profile` | 200 OK | full_name, email, enrolled_courses |
| `/students/{id}/enrollments` | 200 OK | course_name + class_name đúng |
| `/students/{id}/grades` | 200 OK | course_name từ courses.title |
| `/students/{id}/assignments/upcoming` | 200 OK | 8 bài tập, due_date + class_name |
| `/students/{id}/quiz-history` | 200 OK | score, max_score, status |

---

## 9. Page-Aware AI Context (Sprint 221: "Mắt Thần")

### Wiii AI giờ hiểu sinh viên đang xem trang nào

Khi LMS gửi page context, Wiii tự động điều chỉnh:
- **Trang bài giảng**: AI tham chiếu nội dung bài học, dạy theo phương pháp Socratic
- **Trang quiz**: AI gợi ý nhưng **KHÔNG BAO GIỜ** cho đáp án trực tiếp
- **Dashboard**: AI gợi ý bước tiếp theo dựa trên tiến độ

### 9.1 `WiiiContextService` — ĐÃ TRIỂN KHAI

Service đã được implement và auto-wire vào `ChatPanelComponent`. **Không cần thêm code thủ công.**

**File:** `features/ai-chat/infrastructure/api/wiii-context.service.ts`

**Hoạt động tự động:**
1. Service subscribe Router `NavigationEnd` → extract `page_type`, `course_id`, `lesson_id` từ URL
2. `ChatPanelComponent` dùng `effect()` kết nối iframe → WiiiContextService
3. Mỗi khi route thay đổi, PostMessage `wiii:page-context` tự động gửi đến iframe

**Route patterns đã hỗ trợ:**
| URL Pattern | `page_type` |
|-------------|-------------|
| `/student/learn/course/:id/lesson/:id` | `lesson` |
| `/student/learn/course/:id` | `course_overview` |
| `/student/quiz/take/:id` | `quiz` |
| `/student/course/:id` | `course_detail` |
| `/student/assignments/:id/work` | `assignment` |
| `/student/dashboard` | `dashboard` |
| `/student/grades` | `grades` |
| `/student/my-courses` | `course_list` |

### 9.2 Schema PostMessage: `wiii:page-context`

```typescript
// LMS → Wiii iframe
{
  type: "wiii:page-context",
  payload: {
    // Level 1: Page Location (bắt buộc)
    page_type: "lesson" | "quiz" | "assignment" | "dashboard" | "grades" | "resource",
    page_title?: string,           // "Áp suất khí quyển — Chương 3"
    course_id?: string,
    course_name?: string,          // "Khí Tượng Hải Dương"
    lesson_id?: string,
    chapter_name?: string,

    // Level 2: Content (nếu có)
    content_snippet?: string,      // max 2000 ký tự nội dung đang hiển thị
    content_type?: "theory" | "exercise" | "video" | "pdf" | "discussion",
    quiz_question?: string,        // câu hỏi đang làm
    quiz_options?: string[],       // ["A) ...", "B) ...", ...]

    // Level 3: Student State (Sprint 222)
    student_state?: {
      time_on_page_ms?: number,    // milliseconds
      scroll_percent?: number,     // 0-100
      quiz_attempts?: number,
      last_answer?: string,
      is_correct?: boolean,
    },

    // Level 3: Available Actions (Sprint 222)
    available_actions?: Array<{
      action: string,              // "navigate" | "request_hint" | "show_solution"
      label: string,               // Vietnamese UI label
      target?: string,             // URL or resource ID
    }>,
  }
}
```

### 9.3 Mức độ tích hợp

| Phase | Gửi gì | Effort | Wiii behavior |
|-------|---------|--------|---------------|
| **Phase 1** (Sprint 221) | `page_type` + `page_title` + `course_name` | ~1 ngày | AI biết trang đang xem, tham chiếu nội dung |
| **Phase 2** (Sprint 222) | + `content_snippet` + `quiz_question` + `student_state` | ~2 ngày | AI dạy Socratic, phát hiện sinh viên "bí" |
| **Phase 3** (Sprint 223+) | + `available_actions` + server-side content | ~3 ngày | AI gợi ý hành động (next lesson, hint, submit) |

**Phase 1 là đủ để Wiii hoạt động page-aware.** Phase 2-3 làm sau.

### 9.4 Auto-wiring — KHÔNG CẦN CODE THỦ CÔNG

Service `providedIn: 'root'`, tự inject vào `ChatPanelComponent` qua Angular DI.
`ChatPanelComponent` dùng `effect()` watch `viewChild` iframe → gọi `connectIframe()` khi iframe load xong.

**Không cần sửa `AppComponent` hay bất kỳ module nào.**

### 9.5 Phase 2: Enrichment API (cho page components)

Để gửi thêm dữ liệu (tên khóa học, nội dung bài giảng...) từ page component:

```typescript
// Trong CourseLearningComponent
import { WiiiContextService } from '../../ai-chat/infrastructure/api/wiii-context.service';

@Component({ ... })
export class CourseLearningComponent {
  private contextService = inject(WiiiContextService);

  onLessonLoaded(lesson: Lesson): void {
    this.contextService.enrichContext({
      course_name: lesson.course?.title,    // "Khí Tượng Hải Dương"
      lesson_name: lesson.title,            // "Áp suất khí quyển"
      chapter_name: lesson.chapter?.title,  // "Chương 3"
      content_snippet: this.getVisibleContent()?.slice(0, 2000),
      content_type: 'theory',
    });
  }
}
```

### 9.6 E2E Verification (Sprint 221)

Đã verified với curl:
- Lesson page context: AI tham chiếu "Áp suất khí quyển" và "1013.25 hPa" trực tiếp
- Quiz page context: AI dùng Socratic method, KHÔNG cho đáp án trực tiếp

---

*Guide cho đội LMS — Sprint 221 "Mắt Thần" (Page-Aware AI Context)*
