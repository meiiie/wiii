# Hướng dẫn Scale Wiii AI — 1000 Concurrent Users
**Date:** 2026-03-14
**Status:** Config sẵn sàng, chưa triển khai (đang giai đoạn phát triển)

---

## 1. Tổng quan

| | Hiện tại | Sau scale |
|---|---|---|
| VM | e2-medium (2 vCPU, 4GB) | e2-standard-4 (4 vCPU, 16GB) |
| App instances | 1 | 3 |
| Workers/instance | 4 | 8 |
| Total workers | 4 | 24 |
| DB connections | 50 | 100/instance |
| Concurrent users | ~30-50 | ~1000 |
| Chi phí | ~$38/tháng | ~$125/tháng |

---

## 2. Các file đã chuẩn bị (commit `88a1804`)

| File | Thay đổi |
|------|----------|
| `docker-compose.prod.yml` | `APP_REPLICAS` env var, bỏ container_name, bỏ host port |
| `nginx/nginx.conf` | `least_conn` load balancing, keepalive 64 |
| `.env.production.template` | `GUNICORN_WORKERS=8`, `APP_REPLICAS=3`, `DB_HOST` configurable |

---

## 3. Quy trình triển khai (khi sẵn sàng)

### Bước 1: Nâng VM (~5 phút downtime)

```bash
# Stop
gcloud compute instances stop wiii-production --zone=asia-southeast1-b

# Upgrade
gcloud compute instances set-machine-type wiii-production \
  --machine-type=e2-standard-4 --zone=asia-southeast1-b

# Start
gcloud compute instances start wiii-production --zone=asia-southeast1-b
```

### Bước 2: Update .env.production trên server

```bash
gcloud compute ssh wiii-production --zone=asia-southeast1-b

# Sửa .env.production:
cd /opt/wiii/maritime-ai-service
sudo nano .env.production

# Thêm/sửa các dòng:
GUNICORN_WORKERS=8
APP_REPLICAS=3
APP_CPU_LIMIT=2.0
APP_MEM_LIMIT=4G
ASYNC_POOL_MAX_SIZE=100
DB_HOST=postgres
```

### Bước 3: Pull code mới và rebuild

```bash
cd /opt/wiii
git pull origin main

# Rebuild Docker image
sudo docker build --no-cache -f maritime-ai-service/Dockerfile.prod -t wiii-app-local:latest .

# Deploy với 3 replicas
cd maritime-ai-service
sudo docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

### Bước 4: Copy dist-web vào Nginx

```bash
cd /opt/wiii
sudo docker compose -f maritime-ai-service/docker-compose.prod.yml \
  --env-file maritime-ai-service/.env.production up -d --force-recreate nginx
sudo docker cp wiii-desktop/dist-web/. wiii-nginx:/usr/share/nginx/html/
```

### Bước 5: Verify

```bash
# Check all instances running
sudo docker compose -f docker-compose.prod.yml ps

# Expected: 3 app instances, all healthy
# maritime-ai-service-app-1   Up (healthy)
# maritime-ai-service-app-2   Up (healthy)
# maritime-ai-service-app-3   Up (healthy)

# Test health
curl -s http://localhost:8080/api/v1/health/live
# {"status":"alive"}

# Test from outside
curl -s https://wiii.holilihu.online/api/v1/health/live
```

---

## 4. Scale thêm nếu cần

### Tăng lên 2000 users (không downtime):

```bash
# Sửa .env.production
APP_REPLICAS=5

# Apply
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

### Tăng lên 5000+ users:

Cần nâng VM lên **e2-standard-8** (8 vCPU, 32GB, ~$200/tháng):

```bash
gcloud compute instances stop wiii-production --zone=asia-southeast1-b
gcloud compute instances set-machine-type wiii-production \
  --machine-type=e2-standard-8 --zone=asia-southeast1-b
gcloud compute instances start wiii-production --zone=asia-southeast1-b

# Sửa .env.production
APP_REPLICAS=8
GUNICORN_WORKERS=8
# → 64 total workers → ~5000 concurrent users
```

### Thêm PgBouncer (khi DB connection là bottleneck):

```yaml
# Thêm vào docker-compose.prod.yml:
  pgbouncer:
    image: edoburu/pgbouncer:1.22
    container_name: wiii-pgbouncer
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-wiii}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-wiii_ai}
      MAX_CLIENT_CONN: 1500
      DEFAULT_POOL_SIZE: 80
      POOL_MODE: transaction
    networks:
      - wiii-network
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: "256M"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h localhost -p 5432"]
      interval: 10s
      timeout: 3s
      retries: 5
```

Sau đó sửa `.env.production`:
```bash
DB_HOST=pgbouncer    # Thay vì postgres
```

---

## 5. Monitoring khi scale

### Check resource usage:

```bash
# CPU + RAM per container
docker stats --no-stream

# DB connections
docker exec wiii-postgres psql -U wiii -d wiii_ai -c "SELECT count(*) FROM pg_stat_activity;"

# Nginx active connections
docker exec wiii-nginx cat /proc/1/fd/2 2>&1 | tail -5
```

### Dấu hiệu cần scale thêm:

| Metric | Warning | Action |
|--------|---------|--------|
| CPU > 80% sustained | Workers đang full | Tăng replicas |
| RAM > 90% | Sắp hết bộ nhớ | Nâng VM size |
| DB connections > 80% pool | Pool cạn | Thêm PgBouncer |
| Response time > 10s | Users chờ lâu | Tăng workers |
| 502/503 errors | App không kịp xử lý | Tăng replicas + workers |

---

## 6. Bảng chi phí theo quy mô

| Users | VM | Replicas | Workers | Chi phí/tháng |
|-------|-----|----------|---------|---------------|
| 50 (hiện tại) | e2-medium | 1 | 4 | ~$38 |
| 500 | e2-standard-2 | 2 | 16 | ~$85 |
| **1000** | **e2-standard-4** | **3** | **24** | **~$125** |
| 2000 | e2-standard-4 | 5 | 40 | ~$130 |
| 5000 | e2-standard-8 | 8 | 64 | ~$215 |
| 10000+ | Kubernetes | Auto | Auto | ~$400+ |

*Chi phí chưa bao gồm Gemini API (~$50-150/tháng tùy usage)*

---

## 7. Checklist trước khi scale

- [ ] Backup database: `pg_dump` trước khi thay đổi
- [ ] Thông báo downtime (~5 phút) cho users
- [ ] Có SSH access vào GCP VM
- [ ] Có quyền `gcloud compute` trên project `valued-range-443614-j4`
- [ ] `.env.production` đã cập nhật trên server
- [ ] Test health endpoint sau khi scale
- [ ] Monitor 30 phút đầu sau scale
