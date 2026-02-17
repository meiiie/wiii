# Kế Hoạch Chuyển Đổi: Từ Render Cloud sang Local Development

## 🔍 Phân Tích Tình Trạng Hiện Tại (Sử dụng CoT Methodology)

### 1. Problem Statement

Hệ thống Maritime AI hiện đang chạy trên **Render Cloud** gây khó khăn cho việc phát triển:
- **Cold start**: Mỗi lần deploy mất thờigian khởi động
- **Debug khó khăn**: Không thể attach debugger trực tiếp
- **Test chậm**: Phải deploy lên cloud để test
- **Không có hot-reload**: Thay đổi code phải redeploy
- **Phụ thuộc mạng**: Cần internet để phát triển

### 2. Root Cause Analysis (5 Whys)

```
Step 1: Why phát triển khó khăn?
  → Vì hệ thống chạy trên Render Cloud, không local

Step 2: Why không chạy local?
  → Vì thiếu cấu hình docker-compose đầy đủ cho local dev

Step 3: Why docker-compose thiếu?
  → Vì ban đầu tập trung deploy nhanh lên cloud

Step 4: Why ưu tiên cloud trước?
  → Vì team cần demo sản phẩm nhanh cho stakeholders

Step 5: Why không cân bằng cả hai?
  → Vì chưa có kế hoạch kiến trúc dev/prod parity

Root Cause: Thiếu local development environment tương đương production
```

### 3. Current Architecture Analysis

| Component | Production (Render) | Local (Current) | Gap |
|-----------|---------------------|-----------------|-----|
| **App Server** | Render Web Service | ❌ Không có | Cần Docker + hot-reload |
| **PostgreSQL** | Neon Serverless | ❌ Không có | Cần local Postgres |
| **Neo4j** | Neo4j Aura / Cloud | ✅ Docker | OK |
| **Vector DB** | ChromaDB (cloud) | ✅ Docker | OK |
| **Cache** | ❌ Không có | ❌ Không có | Cần Redis |
| **File Storage** | Supabase Storage | ❌ Không có | Cần MinIO/local |

### 4. SOTA Comparison

| Aspect | Current | Industry Best Practice | Gap |
|--------|---------|------------------------|-----|
| **Dev Environment** | Cloud-only | Local + Docker Compose | ❌ Large |
| **Hot Reload** | ❌ Không có | ✅ Có (uvicorn --reload) | ❌ Large |
| **Debug** | Print logs | VS Code debugger attach | ❌ Large |
| **Test Speed** | Slow (deploy) | Fast (local) | ❌ Large |
| **Dev/Prod Parity** | Low | High (Docker) | ❌ Medium |

---

## 🏗️ Kiến Trúc Mục Tiêu: Local Development Environment

### Mục Tiêu
- **Hot-reload**: Code thay đổi → tự động reload
- **Full debugging**: Attach VS Code debugger
- **Fast feedback**: Test ngay không cần deploy
- **Dev/Prod parity**: Cùng Docker image với production
- **Offline capable**: Phát triển không cần internet

### Kiến Trúc Local Stack

```mermaid
flowchart TB
    subgraph "Local Development Stack"
        direction TB
        
        App["🚀 FastAPI App<br/>(Hot Reload + Debug)"]
        
        subgraph "Docker Compose Services"
            Postgres[("🐘 PostgreSQL 15<br/>User Data + Chat History")]
            Neo4j[("🕸️ Neo4j 5<br/>Knowledge Graph")]
            Chroma[("🔍 ChromaDB<br/>Vector Store")]
            Redis[("⚡ Redis<br/>Cache + Session")]
            MinIO[("📦 MinIO<br/>File Storage")]
        end
        
        App --> Postgres
        App --> Neo4j
        App --> Chroma
        App --> Redis
        App --> MinIO
    end
    
    Dev["👨‍💻 Developer<br/>VS Code"] --> App
```

---

## 📋 Implementation Plan

### Phase 1: Cập Nhật Docker Compose (P0 - Critical)

**File**: `maritime-ai-service/docker-compose.yml`

Thêm các services:
1. **Redis** - Cache và session storage
2. **MinIO** - Local S3-compatible storage (thay Supabase)
3. **App Service** - FastAPI với hot-reload và volume mount

### Phase 2: Environment Configuration (P0)

**File**: `maritime-ai-service/.env.local`

Tạo file cấu hình local riêng biệt:
- Database URLs trỏ đến localhost
- API keys dùng development keys
- Debug mode enabled
- Log level DEBUG

### Phase 3: Development Scripts (P1)

**Files**:
- `scripts/start-local.sh` (Linux/Mac)
- `scripts/start-local.ps1` (Windows)
- `scripts/seed-data.py` (Test data)

### Phase 4: VS Code Integration (P1)

**Files**:
- `.vscode/launch.json` - Debug configuration
- `.vscode/tasks.json` - Build tasks
- `.vscode/settings.json` - Python path

### Phase 5: Documentation (P2)

**File**: `maritime-ai-service/docs/LOCAL_DEV.md`

---

## 🎯 Chi Tiết Từng Bước

### Step 1: Cập Nhật docker-compose.yml

```yaml
services:
  # FastAPI App với hot-reload
  app:
    build: .
    container_name: maritime-app
    ports:
      - "8000:8000"
    volumes:
      - .:/app  # Mount code để hot-reload
    environment:
      - ENVIRONMENT=development
      - DEBUG=true
      - DATABASE_URL=postgresql://maritime:maritime_secret@postgres:5432/maritime_ai
      - NEO4J_URI=bolt://neo4j:7687
      - REDIS_URL=redis://redis:6379
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    
  # Redis - Cache
  redis:
    image: redis:7-alpine
    container_name: maritime-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      
  # MinIO - Local S3
  minio:
    image: minio/minio:latest
    container_name: maritime-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: maritime
      MINIO_ROOT_PASSWORD: maritime_secret
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### Step 2: Tạo .env.local

```bash
# Local Development Environment
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Database - Local Docker
DATABASE_URL=postgresql://maritime:maritime_secret@localhost:5433/maritime_ai

# Neo4j - Local
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_secret

# Redis - Local
REDIS_URL=redis://localhost:6379

# MinIO - Local (thay Supabase)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=maritime
MINIO_SECRET_KEY=maritime_secret
MINIO_BUCKET=maritime-docs

# LLM - Development keys
GOOGLE_API_KEY=your-dev-key-here
OPENAI_API_KEY=your-dev-key-here

# Disable cloud-specific features
USE_MULTI_AGENT=true
SEMANTIC_CACHE_ENABLED=true
```

### Step 3: Scripts Khởi Động

**scripts/start-local.sh**:
```bash
#!/bin/bash
set -e

echo "🚀 Starting Maritime AI Local Development Environment..."

# Export local environment
export ENV_FILE=.env.local

# Start infrastructure
echo "📦 Starting infrastructure services..."
docker-compose up -d postgres neo4j chroma redis minio

# Wait for services
echo "⏳ Waiting for services to be ready..."
sleep 10

# Run migrations
echo "🔄 Running database migrations..."
cd maritime-ai-service
alembic upgrade head

# Seed test data
echo "🌱 Seeding test data..."
python scripts/seed-data.py

# Start app with hot-reload
echo "🎯 Starting FastAPI with hot-reload..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo "✅ Local development environment is ready!"
echo "📱 API: http://localhost:8000"
echo "📚 Docs: http://localhost:8000/docs"
```

### Step 4: VS Code Configuration

**.vscode/launch.json**:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
      "jinja": true,
      "justMyCode": false,
      "cwd": "${workspaceFolder}/maritime-ai-service",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/maritime-ai-service"
      }
    }
  ]
}
```

---

## 🔄 Migration Strategy

### Bước 1: Chuẩn Bị (Không ảnh hưởng Production)
- Tạo branch `feature/local-dev`
- Cập nhật docker-compose.yml
- Tạo .env.local template

### Bước 2: Test Local
- Chạy `scripts/start-local.sh`
- Verify tất cả services hoạt động
- Test API endpoints
- Test debug attach

### Bước 3: Documentation
- Viết LOCAL_DEV.md
- Update README.md
- Training team

### Bước 4: Song Song
- Developer có thể chọn: Local hoặc Render
- Production vẫn chạy Render

### Bước 5: Optional: Local Production
- Nếu cần, có thể dùng Docker Swarm/K3s local
- Hoặc giữ Render cho production

---

## 📊 Expected Benefits

| Metric | Before (Render) | After (Local) | Improvement |
|--------|-----------------|---------------|-------------|
| **Code → Test** | 2-5 phút (deploy) | 2-5 giây (hot-reload) | **60-150x** |
| **Debug** | Print logs | VS Code debugger | **N/A** |
| **Offline dev** | ❌ Không | ✅ Có | **Yes** |
| **Cost** | $7-25/tháng | $0 | **Free** |
| **Team onboarding** | 1-2 giờ | 15 phút | **4-8x** |

---

## ⚠️ Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dev/Prod drift | Medium | Cùng Dockerfile, CI test trên cả hai |
| Local resource | Low | Docker resource limits |
| Data sync | Low | Scripts export/import data |
| Windows issues | Low | WSL2 + Docker Desktop |

---

## 📝 Next Steps

1. **Review kế hoạch** với team
2. **Ưu tiên Phase 1** (docker-compose.yml)
3. **Tạo branch** và bắt đầu implement
4. **Test thử** với 1 developer
5. **Roll out** cho cả team

---

*Created: 2026-01-29*
*Methodology: CoT (Chain-of-Thought) Research Skill*
