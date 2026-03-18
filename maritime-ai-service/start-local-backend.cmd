@echo off
cd /d E:\Sach\Sua\AI_v1\maritime-ai-service
set "PYTHONIOENCODING=utf-8"
set "ENABLE_CODE_STUDIO_STREAMING=true"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 > server-local-8001.log 2>&1
