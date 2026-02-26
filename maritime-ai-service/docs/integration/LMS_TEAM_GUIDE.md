# Hướng Dẫn Tích Hợp Wiii AI — Dành Cho Đội LMS

> **Version:** 2.0.0
> **Last Updated:** 2026-02-23
> **For:** Đội LMS (Backend Spring Boot + Frontend Angular)
> **Reference:** [`WIII_LMS_INTEGRATION.md`](./WIII_LMS_INTEGRATION.md) (full technical spec)

---

## 1. Wiii là gì?

Wiii là trợ lý AI giáo dục do **The Wiii Lab** phát triển. Wiii giúp sinh viên tra cứu kiến thức, ôn thi, hỏi đáp bài tập. Cho giảng viên: dashboard phân tích, phát hiện sinh viên nguy cơ, báo cáo AI. Wiii chạy trên FastAPI + LangGraph, giao tiếp qua REST + SSE, bảo mật bằng HMAC-SHA256 + JWT.

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
  "id": "SV12345",
  "name": "Nguyễn Văn A",
  "email": "sv12345@vimaru.edu.vn",
  "class_name": "ĐKTB K62A",
  "program": "Điều khiển tàu biển",
  "enrolled_courses": ["NHH101", "NHH201"]
}
```

#### Student Grades Response

```json
[
  {
    "course_id": "NHH101",
    "course_name": "Điều khiển tàu biển 1",
    "grade": 7.5,
    "max_grade": 10.0,
    "date": "2026-02-20"
  }
]
```

#### Upcoming Assignments Response

```json
[
  {
    "assignment_id": "asgn-001",
    "assignment_name": "Bài tập SOLAS Chapter III",
    "course_id": "NHH101",
    "course_name": "Điều khiển tàu biển 1",
    "due_date": "2026-03-01T23:59:00Z"
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

## 5. Token Exchange Từ Góc LMS

Khi frontend Angular cần gọi Wiii AI, LMS backend exchange token cho user.

### Step-by-step

1. Angular gọi `POST /api/v3/ai/token` (với session cookie)
2. LMS backend build JSON: `{connector_id, lms_user_id, email, name, role, timestamp}`
3. LMS sign body bằng HMAC-SHA256 (`wiii.webhook.secret`)
4. LMS gọi Wiii: `POST /auth/lms/token` với header `X-LMS-Signature`
5. Wiii verify → tạo JWT → trả về `{access_token, refresh_token, expires_in, user}`
6. LMS cache token (14 phút, auto-refresh)
7. LMS trả `access_token` cho Angular

### Java Implementation

```java
// WiiiTokenExchangeAdapter.java
public WiiiTokenResponse exchangeToken(String userId, String email,
                                        String name, String role) {
    long timestamp = Instant.now().getEpochSecond();

    Map<String, Object> body = Map.of(
        "connector_id", connectorId,
        "lms_user_id", userId,
        "email", email,
        "name", name,
        "role", mapRole(role),
        "organization_id", "maritime-lms",
        "timestamp", timestamp
    );

    String jsonBody = objectMapper.writeValueAsString(body);
    String signature = sign(jsonBody);

    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_JSON);
    headers.set("X-LMS-Signature", signature);

    ResponseEntity<WiiiTokenResponse> response = restTemplate.postForEntity(
        wiiiBaseUrl + "/auth/lms/token",
        new HttpEntity<>(jsonBody, headers),
        WiiiTokenResponse.class
    );

    return response.getBody();
}

private String mapRole(String lmsRole) {
    return switch (lmsRole.toLowerCase()) {
        case "ROLE_TEACHER", "ROLE_INSTRUCTOR" -> "teacher";
        case "ROLE_ADMIN" -> "admin";
        default -> "student";
    };
}
```

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

---

## Tài liệu liên quan

- **Full API Contract**: [`WIII_LMS_INTEGRATION.md`](./WIII_LMS_INTEGRATION.md)
- **Deployment Guide**: [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md)
- **Wiii System Architecture**: [`../architecture/SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md)

---

*Guide cho đội LMS — Sprint 175 "Cắm Phích Cắm"*
