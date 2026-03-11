#!/bin/bash
# ingest-production.sh
# Ingest maritime PDFs into production knowledge base.
#
# Prerequisites:
#   - PDFs in /opt/wiii/data/pdfs/
#   - Docker containers running
#   - API accessible at localhost:8000
#
# Usage:
#   API_KEY=your-key bash ingest-production.sh [--dry-run]
#
# Pipeline (SOTA 2026):
#   PDF → PyMuPDF/Gemini Vision → Semantic Chunking (800 chars, 100 overlap)
#   → Gemini models/gemini-embedding-001 (768-dim) → pgvector HNSW

set -euo pipefail

APP_DIR="/opt/wiii"
PDF_DIR="${APP_DIR}/data/pdfs"
API_URL="http://localhost:8000/api/v1/knowledge"
HEALTH_URL="http://localhost:8000/api/v1/health/live"
API_KEY="${API_KEY:-}"
LOG_FILE="${APP_DIR}/ingestion.log"
DRY_RUN="${1:-}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

if [ -z "$API_KEY" ]; then
    echo "ERROR: API_KEY environment variable required"
    echo "Usage: API_KEY=your-key bash ingest-production.sh"
    exit 1
fi

if [ ! -d "$PDF_DIR" ]; then
    echo "ERROR: PDF directory not found: $PDF_DIR"
    echo "Create it and add maritime PDFs (COLREGs, SOLAS, MARPOL, etc.)"
    exit 1
fi

PDF_COUNT=$(find "$PDF_DIR" -name "*.pdf" | wc -l)
log "Found ${PDF_COUNT} PDFs in ${PDF_DIR}"

if [ "$PDF_COUNT" -eq 0 ]; then
    log "No PDFs found. Add files to ${PDF_DIR} and re-run."
    exit 0
fi

if [ "$DRY_RUN" = "--dry-run" ]; then
    log "DRY RUN — listing files only:"
    find "$PDF_DIR" -name "*.pdf" -exec echo "  {}" \;
    exit 0
fi

# Check API health
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || echo "000")
if [ "$HEALTH" != "200" ]; then
    log "ERROR: API not responding at ${HEALTH_URL} (HTTP ${HEALTH}). Is the server running?"
    exit 1
fi

SUCCESS=0
FAILED=0

for pdf in "$PDF_DIR"/*.pdf; do
    filename=$(basename "$pdf")
    log "Ingesting: ${filename}..."

    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST "${API_URL}/ingest-multimodal" \
        -H "X-API-Key: ${API_KEY}" \
        -F "file=@${pdf}" \
        -F "domain_id=maritime" \
        --max-time 300 \
        2>/dev/null)

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
        log "  OK: ${filename} (HTTP ${HTTP_CODE})"
        SUCCESS=$((SUCCESS + 1))
    else
        log "  FAILED: ${filename} (HTTP ${HTTP_CODE})"
        log "  Response: ${BODY}"
        FAILED=$((FAILED + 1))
    fi

    sleep 2
done

log "=== Ingestion complete: ${SUCCESS} success, ${FAILED} failed ==="

log "Knowledge base stats:"
curl -s "${API_URL}/stats" -H "X-API-Key: ${API_KEY}" | python3 -m json.tool 2>/dev/null || true
