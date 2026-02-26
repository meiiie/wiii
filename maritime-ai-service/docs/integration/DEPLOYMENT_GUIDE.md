# Deployment Guide — Wiii AI x LMS Integration

> **Version:** 2.0.0
> **Last Updated:** 2026-02-23
> **Sprint:** 175 "Cắm Phích Cắm"
> **For:** DevOps cả 2 team (Wiii + LMS)

---

## Mục lục

1. [Pre-deployment Checklist](#1-pre-deployment-checklist)
2. [Environment Variables — Production](#2-environment-variables--production)
3. [Domain & CORS Configuration](#3-domain--cors-configuration)
4. [Database Migrations](#4-database-migrations)
5. [Health Check Verification](#5-health-check-verification)
6. [Monitoring Endpoints](#6-monitoring-endpoints)
7. [Rollback Procedure](#7-rollback-procedure)
8. [Production Hardening Notes](#8-production-hardening-notes)

---

## 1. Pre-deployment Checklist

### Wiii Side

- [ ] **Secrets generated**: `openssl rand -hex 32` for each secret
- [ ] **Feature flags enabled** in `.env`:
  - [ ] `ENABLE_LMS_INTEGRATION=true`
  - [ ] `ENABLE_LMS_TOKEN_EXCHANGE=true`
  - [ ] `ENABLE_MULTI_TENANT=true`
- [ ] **HMAC secret configured**: `LMS_WEBHOOK_SECRET` matches LMS `wiii.webhook.secret`
- [ ] **LMS base URL set**: `LMS_BASE_URL` points to LMS production API
- [ ] **LMS connector JSON configured**: `LMS_CONNECTORS` with correct production values
- [ ] **CORS updated**: LMS frontend domain added to `CORS_ORIGINS`
- [ ] **Database migration 021** applied: `alembic upgrade head`
- [ ] **Rate limits reviewed**: Adequate for expected traffic
- [ ] **JWT secret strong**: `JWT_SECRET_KEY` is a random 64+ character string
- [ ] **API key shared**: Wiii `API_KEY` shared with LMS team (for fallback auth)
- [ ] **Docker image built**: `docker compose build app`
- [ ] **Health check passes**: `/api/v1/auth/lms/health` returns `{"status": "ok"}`
- [ ] **Tests pass**: `pytest tests/unit/test_sprint175* tests/unit/test_sprint155* -v`

### LMS Backend Side

- [ ] **Wiii config set** in `application.yml`:
  - [ ] `wiii.base-url` points to Wiii production URL
  - [ ] `wiii.webhook.secret` matches Wiii `LMS_WEBHOOK_SECRET`
  - [ ] `wiii.service-token` matches what Wiii expects
  - [ ] `wiii.webhook.enabled=true`
- [ ] **Security filter active**: `WiiiServiceAuthFilter` validates Bearer token
- [ ] **Flyway migration V45** applied: `ai_insights` + `ai_alerts` tables created
- [ ] **`@EnableAsync`** on main Application class (for async webhook sending)
- [ ] **CORS**: If Angular served from different domain, configure Spring Security CORS
- [ ] **Build passes**: `mvn compile` (or `mvn package`) succeeds
- [ ] **Domain events wired**: `WiiiEventBridge` listens to grade/enrollment/quiz events

### LMS Frontend Side

- [ ] **Environment config**: `aiServiceUrl` points to LMS backend proxy (`/api/v3/ai`)
- [ ] **AiTokenService** integrated in chat components
- [ ] **Build passes**: `npx ng build --configuration=production`
- [ ] **SSE proxy timeout**: Backend/Nginx timeout ≥ 60s for SSE endpoints

### Network & Infrastructure

- [ ] **Firewall**: Wiii ↔ LMS can communicate (both directions)
- [ ] **DNS**: Both services have resolvable hostnames
- [ ] **TLS**: HTTPS between services in production
- [ ] **NTP**: Clock sync on both servers (for HMAC timestamp validation ±300s)
- [ ] **Load balancer**: SSE/streaming endpoints NOT buffered (disable proxy_buffering)

---

## 2. Environment Variables — Production

### Wiii `.env` — LMS Integration Section

```bash
# =============================================================================
# LMS INTEGRATION (Sprint 175: "Cắm Phích Cắm")
# =============================================================================
# Master feature flags
ENABLE_LMS_INTEGRATION=true
ENABLE_LMS_TOKEN_EXCHANGE=true
ENABLE_MULTI_TENANT=true

# HMAC-SHA256 shared secret for webhook verification and token exchange
# MUST match LMS application.yml → wiii.webhook.secret
# Generate: openssl rand -hex 32
LMS_WEBHOOK_SECRET=<production-hmac-secret-64-hex-chars>

# LMS REST API base URL (for Wiii → LMS data pull)
LMS_BASE_URL=https://lms.maritime.edu.vn/api/v3

# API timeout for LMS calls (seconds, range 3-60)
LMS_API_TIMEOUT=10

# Token exchange replay protection (seconds, range 30-600)
# Reject requests with timestamp drift > this value
LMS_TOKEN_EXCHANGE_MAX_AGE=300

# Multi-LMS connector configuration (JSON array)
# Each connector: id, display_name, backend_type, base_url, service_token, webhook_secret
LMS_CONNECTORS=[{"id":"maritime-lms","display_name":"LMS Hang Hai","backend_type":"spring_boot","base_url":"https://lms.maritime.edu.vn/api/v3","service_token":"<lms-service-token>","webhook_secret":"<production-hmac-secret>","api_timeout":10,"extra":{"api_prefix":"api/v3/integration"}}]

# CORS — add LMS frontend domain
CORS_ORIGINS=["https://lms.maritime.edu.vn","https://admin.maritime.edu.vn"]

# JWT (ensure strong secret for production)
JWT_SECRET_KEY=<strong-random-64+-character-secret>
JWT_EXPIRE_MINUTES=15
```

### LMS Backend `application.yml` — Production

```yaml
wiii:
  base-url: https://ai.maritime.edu.vn/api/v1
  webhook:
    secret: ${WIII_WEBHOOK_SECRET}     # Same as Wiii LMS_WEBHOOK_SECRET
    enabled: true
  service-token: ${WIII_SERVICE_TOKEN}  # Bearer token for Wiii → LMS calls
  connector-id: maritime-lms

# Spring Boot server port
server:
  port: ${SERVER_PORT:8080}

# Flyway auto-migration
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
```

### LMS Frontend `environment.prod.ts`

```typescript
export const environment = {
  production: true,
  aiServiceUrl: '/api/v3/ai',  // Relative path, proxied through LMS backend
};
```

---

## 3. Domain & CORS Configuration

### Wiii Side

Add LMS frontend domain(s) to `CORS_ORIGINS`:

```bash
CORS_ORIGINS=["https://lms.maritime.edu.vn","http://localhost:4200"]
```

### Nginx / Reverse Proxy

If using Nginx in front of Wiii or LMS:

```nginx
# SSE streaming — CRITICAL: disable buffering
location /api/v1/chat/stream/ {
    proxy_pass http://wiii-backend:8000;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_read_timeout 300s;  # 5 min for long streams
}

# Regular API
location /api/v1/ {
    proxy_pass http://wiii-backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### LMS Nginx (for Angular SSE proxy)

```nginx
location /api/v3/ai/chat/stream {
    proxy_pass http://lms-backend:8080;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 120s;
}
```

---

## 4. Database Migrations

### Wiii Side — Alembic

```bash
cd maritime-ai-service

# Check current revision
alembic current

# Apply all pending migrations (includes 021: maritime-lms org seed)
alembic upgrade head

# Verify migration 021 applied
alembic current
# Should show revision for 021_seed_maritime_lms_organization
```

**Migration 021** creates/updates:
- `organizations` table: inserts `maritime-lms` org record
- Idempotent: safe to re-run (uses `ON CONFLICT DO UPDATE`)

### LMS Side — Flyway

Flyway runs automatically on Spring Boot startup.

```bash
# Verify V45 migration applied
# Check flyway_schema_history table:
SELECT * FROM flyway_schema_history WHERE script LIKE '%V45%';
```

**V45 migration** creates:
- `ai_insights` table (student AI insights from Wiii)
- `ai_alerts` table (class AI alerts from Wiii)
- Indexes on `student_id`, `course_id`, `insight_type`, `alert_type`

---

## 5. Health Check Verification

Run these curl commands after deployment to verify everything works.

### 5.1 Wiii Health

```bash
# General health
curl -s https://ai.maritime.edu.vn/api/v1/health | jq .

# LMS auth health
curl -s https://ai.maritime.edu.vn/api/v1/auth/lms/health | jq .
# Expected: {"status":"ok","enabled":true,"connectors":["maritime-lms"],"has_flat_secret":true}
```

### 5.2 Token Exchange

```bash
SECRET="your-production-hmac-secret"
BODY='{"connector_id":"maritime-lms","lms_user_id":"test-deploy","role":"student","timestamp":'$(date +%s)'}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

curl -s -X POST https://ai.maritime.edu.vn/api/v1/auth/lms/token \
  -H "Content-Type: application/json" \
  -H "X-LMS-Signature: sha256=$SIG" \
  -d "$BODY" | jq .status
# Expected: 200 with access_token
```

### 5.3 Webhook Test

```bash
SECRET="your-production-hmac-secret"
BODY='{"event_type":"attendance_marked","timestamp":"2026-02-23T00:00:00Z","payload":{"student_id":"test","course_id":"test","date":"2026-02-23","status":"present"},"source":"deploy_test"}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

curl -s -X POST https://ai.maritime.edu.vn/api/v1/lms/webhook/maritime-lms \
  -H "Content-Type: application/json" \
  -H "X-LMS-Signature: sha256=$SIG" \
  -d "$BODY" | jq .
# Expected: {"status":"accepted","event_type":"attendance_marked",...}
```

### 5.4 LMS Backend Health

```bash
# LMS Spring Boot actuator
curl -s https://lms.maritime.edu.vn/actuator/health | jq .

# LMS data endpoint (with service token)
curl -s -H "Authorization: Bearer your-service-token" \
  https://lms.maritime.edu.vn/api/v3/integration/students/SV12345/profile | jq .
```

### 5.5 End-to-End Chat

```bash
# SSE streaming test
curl -N -X POST https://ai.maritime.edu.vn/api/v1/chat/stream/v3 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -H "X-User-ID: test-deploy" \
  -H "X-Session-ID: deploy-test-session" \
  -H "X-Role: student" \
  -H "X-Organization-ID: maritime-lms" \
  -d '{"message":"Xin chào","domain_id":"maritime","organization_id":"maritime-lms"}'
# Expected: SSE events (thinking_start, status, answer_delta, done)
```

---

## 6. Monitoring Endpoints

| Endpoint | Service | Purpose | Expected |
|----------|---------|---------|----------|
| `GET /api/v1/health` | Wiii | Overall health | `{"status": "ok"}` |
| `GET /api/v1/health/db` | Wiii | Database | `{"status": "ok"}` |
| `GET /api/v1/auth/lms/health` | Wiii | LMS integration | `{"status": "ok", "enabled": true}` |
| `GET /actuator/health` | LMS | Spring Boot health | `{"status": "UP"}` |

### Key Metrics to Monitor

| Metric | Warning | Critical | Source |
|--------|---------|----------|--------|
| Token exchange latency | >2s | >5s | Wiii logs |
| Webhook processing time | >3s | >10s | Wiii logs |
| LMS API circuit breaker | 3 failures | 5 failures (open) | Wiii logs |
| Chat SSE TTFT | >20s | >45s | Wiii logs |
| JWT token cache hit rate | <50% | <20% | LMS logs |

---

## 7. Rollback Procedure

### Level 1: Feature Flag Off (instant, zero downtime)

Disable LMS integration without redeployment:

```bash
# Wiii: set in .env and restart
ENABLE_LMS_INTEGRATION=false
ENABLE_LMS_TOKEN_EXCHANGE=false

# Docker: restart container
docker compose restart app
```

**Effect**: All LMS endpoints return 404, webhooks rejected, tools disabled. Chat continues working normally.

### Level 2: Migration Rollback

```bash
# Wiii: revert migration 021 (removes maritime-lms org record)
alembic downgrade -1

# LMS: Flyway doesn't auto-rollback — manual SQL if needed:
# DROP TABLE IF EXISTS ai_insights;
# DROP TABLE IF EXISTS ai_alerts;
# DELETE FROM flyway_schema_history WHERE script LIKE '%V45%';
```

### Level 3: Code Rollback

```bash
# Wiii: revert to previous image
docker compose pull app  # if using registry
docker compose up -d app

# Or git-based:
git revert HEAD  # revert Sprint 175 commit
docker compose build app && docker compose up -d app
```

### Level 4: Full Revert

```bash
# 1. Feature flags off (Level 1)
# 2. Migration rollback (Level 2)
# 3. Code rollback (Level 3)
# 4. Remove LMS-side config:
#    - Remove wiii.* from application.yml
#    - Remove ai-token.service.ts integration
#    - Rebuild LMS
```

---

## 8. Production Hardening Notes

### Phase 5 Items (Planned, not yet implemented)

| Item | Priority | Description |
|------|----------|-------------|
| **HMAC Key Rotation** | High | Rolling secret update: support 2 active keys during rotation window |
| **Mutual TLS** | Medium | Certificate-based service auth (eliminates Bearer token risk) |
| **Webhook Retry Queue** | Medium | Dead-letter queue for failed webhooks (currently fire-and-forget) |
| **Student Pseudonymization** | Medium | Hash student_id before sending to AI for privacy |
| **Audit Logging** | High | Log all cross-system API calls with request IDs |
| **Rate Limit Headers** | Low | Return `X-RateLimit-*` headers for client-side backoff |
| **Circuit Breaker Dashboard** | Low | Expose circuit breaker state via health endpoint |

### Security Reminders

1. **Never commit secrets** — Use environment variables or secret managers
2. **Rotate secrets quarterly** — Update HMAC + service tokens
3. **Monitor for replay attacks** — Wiii logs timestamp rejection events
4. **NTP sync** — Both servers must be within 5 minutes of each other
5. **HTTPS only** — Never send HMAC-signed requests over HTTP in production
6. **Principle of least privilege** — Service token should only access integration endpoints

### Performance Tuning

| Setting | Development | Production |
|---------|-------------|------------|
| `LMS_API_TIMEOUT` | 10s | 10s (increase to 15s if LMS is slow) |
| `async_pool_min_size` | 10 | 10 |
| `async_pool_max_size` | 50 | 50 (PostgreSQL max_connections=100) |
| Wiii workers | 1 (uvicorn --reload) | 4+ (gunicorn -w 4 -k uvicorn.workers.UvicornWorker) |
| SSE proxy timeout | 30s | 120-300s |
| Token cache TTL | 14 min | 14 min (matches 15min JWT expiry - 1min buffer) |

---

*Deployment Guide — Sprint 175 "Cắm Phích Cắm"*
*Maintained by: Wiii AI Team & LMS Team*
