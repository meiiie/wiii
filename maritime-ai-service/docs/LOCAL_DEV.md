# Wiii - Local Development Guide

> 🏠 **Phát triển Local** | ☁️ **Deploy trên Render**

Hướng dẫn này giúp bạn thiết lập môi trường phát triển local cho Wiii, thay thế việc phát triển trực tiếp trên Render Cloud.

---

## 🎯 Lợi Ích của Local Development

| Feature | Render Cloud | Local Dev | Lợi Ích |
|---------|-------------|-----------|---------|
| **Hot Reload** | ❌ Cần redeploy | ✅ Tự động | Code thay đổi → Test ngay lập tức |
| **Debug** | ❌ Print logs | ✅ VS Code debugger | Attach debugger, breakpoints |
| **Test Speed** | ⏱️ 2-5 phút | ⚡ 2-5 giây | Nhanh hơn **60-150x** |
| **Offline** | ❌ Cần internet | ✅ Không cần | Phát triển mọi lúc, mọi nơi |
| **Cost** | $7-25/tháng | $0 | **Miễn phí** |

---

## 📋 Yêu Cầu Hệ Thống

### Bắt Buộc
- **Docker Desktop** >= 4.0 ([Download](https://www.docker.com/products/docker-desktop))
- **Python** >= 3.11 ([Download](https://www.python.org/downloads/))
- **Git**

### Khuyến Nghị
- **VS Code** với extensions:
  - Python (Microsoft)
  - Docker (Microsoft)
  - Thunder Client (API testing)
- **RAM**: 8GB+ (16GB recommended)
- **Disk**: 10GB+ free space

---

## 🚀 Quick Start (5 phút)

### Bước 1: Clone Repository

```bash
git clone <your-repo-url>
cd AI_v1/maritime-ai-service
```

### Bước 2: Tạo Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python -m venv .venv
source .venv/bin/activate
```

### Bước 3: Cài Đặt Dependencies

```bash
pip install -r requirements.txt
```

### Bước 4: Cấu Hình Môi Trường

```bash
# Copy file cấu hình local
copy .env.local .env

# Hoặc trên Linux/Mac
cp .env.local .env
```

**Chỉnh sửa `.env` và thêm API keys:**

```bash
# Lấy API key từ Google AI Studio: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=your-google-api-key-here

# Optional: OpenRouter cho fallback
OPENAI_API_KEY=your-openrouter-key-here
```

### Bước 5: Khởi Động

```bash
# Windows PowerShell
.\scripts\start-local.ps1

# Linux/Mac
chmod +x scripts/start-local.sh
./scripts/start-local.sh
```

**Hoặc dùng VS Code:**
- Nhấn `Ctrl+Shift+P` → "Tasks: Run Task" → "Setup Local Environment"

### Bước 6: Truy Cập

| Service | URL |
|---------|-----|
| **API Server** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |
| **Health Check** | http://localhost:8000/health |
| **Neo4j Browser** | http://localhost:7474 |
| **MinIO Console** | http://localhost:9001 |
| **pgAdmin** | http://localhost:5050 |

---

## 🏗️ Kiến Trúc Local Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Local Development Stack                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   FastAPI    │    │   VS Code    │    │   Browser    │  │
│  │   (App)      │◄──►│  (Debugger)  │    │  (Testing)   │  │
│  │   :8000      │    │              │    │              │  │
│  └──────┬───────┘    └──────────────┘    └──────────────┘  │
│         │                                                    │
│  ┌──────┴────────────────────────────────────────────────┐  │
│  │              Docker Compose Network                    │  │
│  ├──────────────┬──────────────┬──────────────┬──────────┤  │
│  │  PostgreSQL  │    Neo4j     │   ChromaDB   │  Redis   │  │
│  │    :5433     │   :7474      │    :8001     │  :6379   │  │
│  │  (User Data) │ (Knowledge   │  (Vectors)   │ (Cache)  │  │
│  │              │    Graph)    │              │          │  │
│  └──────────────┴──────────────┴──────────────┴──────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                      MinIO                             │  │
│  │              (Local S3 Storage)                        │  │
│  │                    :9000/:9001                         │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Chi Tiết Cấu Hình

### Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| `app` | 8000 | FastAPI application (hot-reload) |
| `postgres` | 5433 | PostgreSQL database |
| `neo4j` | 7474, 7687 | Knowledge graph |
| `chroma` | 8001 | Vector embeddings |
| `redis` | 6379 | Cache & sessions |
| `minio` | 9000, 9001 | Object storage (S3-compatible) |
| `pgadmin` | 5050 | PostgreSQL admin UI (optional) |

### Environment Variables

File `.env.local` đã được cấu hình sẵn cho local development:

```bash
# Database URLs trỏ đến localhost
DATABASE_URL=postgresql+asyncpg://wiii:wiii_secret@localhost:5433/wiii_ai
NEO4J_URI=bolt://localhost:7687
REDIS_URL=redis://localhost:6379/0

# MinIO thay thế Supabase
MINIO_ENDPOINT=localhost:9000
SUPABASE_URL=http://localhost:9000

# Development flags
DEBUG=true
LOG_LEVEL=DEBUG
USE_MULTI_AGENT=true
```

---

## 🔧 Debugging với VS Code

### 1. Cấu Hình Launch

File `.vscode/launch.json` đã được tạo sẵn. Các configuration có sẵn:

- **Python: FastAPI (Local)** - Chạy với hot-reload
- **Python: FastAPI (No Reload)** - Chạy không reload (debug ổn định hơn)
- **Python: Current File** - Debug file hiện tại
- **Python: Seed Data** - Chạy seed script

### 2. Cách Debug

1. Đặt breakpoint trong code (F9)
2. Chọn configuration trong Debug panel (Ctrl+Shift+D)
3. Nhấn F5 để bắt đầu debug
4. Gọi API từ Thunder Client hoặc browser
5. Code sẽ pause tại breakpoint

### 3. Debug Multi-Agent System

Thêm breakpoint vào các file:
- `app/engine/multi_agent/graph.py` - Xem routing decisions
- `app/engine/multi_agent/agents/tutor_node.py` - Debug tutor agent
- `app/engine/multi_agent/agents/rag_node.py` - Debug RAG agent

---

## 🧪 Testing

### Unit Tests

```bash
# Chạy tất cả tests
pytest

# Chạy với coverage
pytest --cov=app --cov-report=html

# Chạy test cụ thể
pytest tests/test_chat.py -v
```

### API Testing

Sử dụng Thunder Client trong VS Code hoặc curl:

```bash
# Health check
curl http://localhost:8000/health

# Chat API
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key" \
  -d '{
    "user_id": "test-student-001",
    "message": "Quy tắc 15 là gì?",
    "role": "student"
  }'
```

---

## 🔄 Workflow Phát Triển

### 1. Khởi Động Mới

```bash
# Start tất cả services
./scripts/start-local.sh

# Hoặc từng phần:
docker-compose up -d postgres neo4j chroma redis minio
python -m alembic upgrade head
python scripts/seed-data.py
uvicorn app.main:app --reload
```

### 2. Code → Test Loop

```
1. Sửa code trong VS Code
2. Tự động reload (hot-reload)
3. Test API trong Thunder Client
4. Nếu có lỗi → Debug (F5)
5. Lặp lại
```

### 3. Dừng và Dọn Dẹp

```bash
# Dừng tất cả services
docker-compose down

# Dừng và xóa data
docker-compose down -v

# Chỉ dừng app, giữ database
docker-compose stop app
```

---

## 📊 Quản Lý Data

### Backup Database

```bash
# PostgreSQL backup
docker exec wiii-postgres pg_dump -U wiii wiii_ai > backup.sql

# Restore
docker exec -i wiii-postgres psql -U wiii wiii_ai < backup.sql
```

### Reset Data

```bash
# Xóa tất cả và tạo lại
docker-compose down -v
docker-compose up -d
python -m alembic upgrade head
python scripts/seed-data.py
```

### Xem Data trong Database

**PostgreSQL:**
```bash
# CLI
docker exec -it wiii-postgres psql -U wiii -d wiii_ai

# Hoặc dùng pgAdmin: http://localhost:5050
# Login: admin@wiii.local / admin
```

**Neo4j:**
- Truy cập: http://localhost:7474
- Login: neo4j / neo4j_secret

**MinIO:**
- Console: http://localhost:9001
- Login: wiii / wiii_secret

---

## 🐛 Troubleshooting

### Lỗi Thường Gặp

#### 1. Port đã được sử dụng

```bash
# Kiểm tra port nào đang dùng
netstat -ano | findstr :8000

# Thay đổi port trong docker-compose.yml
ports:
  - "8001:8000"  # Thay vì 8000:8000
```

#### 2. Database connection failed

```bash
# Kiểm tra service có chạy không
docker-compose ps

# Xem logs
docker-compose logs postgres

# Khởi động lại
docker-compose restart postgres
```

#### 3. Hot-reload không hoạt động

```bash
# Kiểm tra volume mount
docker-compose exec app ls -la /app

# Restart app service
docker-compose restart app
```

#### 4. Permission denied (Linux/Mac)

```bash
chmod +x scripts/start-local.sh
```

#### 5. Module not found

```bash
# Cài lại dependencies
pip install -r requirements.txt

# Kiểm tra PYTHONPATH
echo $PYTHONPATH  # Linux/Mac
$env:PYTHONPATH   # Windows PowerShell
```

---

## 🚀 Deploy lên Render (Production)

Khi code đã hoạt động tốt local, deploy lên Render:

```bash
# Commit và push
git add .
git commit -m "Feature: xxx"
git push origin main

# Render sẽ tự động deploy
```

**Lưu ý:** Render sử dụng:
- Neon PostgreSQL (thay vì local Postgres)
- Neo4j Aura (thay vì local Neo4j)
- Supabase Storage (thay vì MinIO)

---

## 📚 Tài Liệu Tham Khảo

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [LangGraph Concepts](https://langchain-ai.github.io/langgraph/concepts/)
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)

---

## 🤝 Đóng Góp

1. Tạo branch mới: `git checkout -b feature/xxx`
2. Code và test local
3. Tạo PR với mô tả rõ ràng

---

## 📝 Changelog

| Date | Change |
|------|--------|
| 2026-01-29 | Tạo local development environment |
| | Thêm docker-compose với full stack |
| | Thêm hot-reload và debug config |

---

**Happy Coding! 🚢⚓**
