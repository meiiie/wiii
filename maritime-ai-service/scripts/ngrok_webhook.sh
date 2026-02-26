#!/bin/bash
# =============================================================================
# Wiii Soul AGI — Webhook Testing via ngrok
# =============================================================================
#
# Quick setup for local webhook testing without VPS.
# Tunnels localhost to a public ngrok URL for Facebook/Zalo webhooks.
#
# Prerequisites:
#   - ngrok installed: choco install ngrok (Windows) / brew install ngrok (Mac)
#   - ngrok account: https://ngrok.com (free tier)
#   - Backend running: uvicorn app.main:app --reload --port 8000
#
# Usage:
#   ./scripts/ngrok_webhook.sh [port]
#
# After starting:
#   1. Copy the https://xxx.ngrok-free.app URL
#   2. Facebook Developer Console → Webhooks → Callback URL:
#      https://xxx.ngrok-free.app/api/v1/messenger/webhook
#   3. Zalo OA Admin → API → Webhook URL:
#      https://xxx.ngrok-free.app/api/v1/zalo/webhook
# =============================================================================

set -euo pipefail

PORT="${1:-8000}"
NGROK_DOMAIN="${NGROK_DOMAIN:-}"

echo "============================================"
echo "  Wiii Soul AGI — Webhook Testing"
echo "============================================"
echo ""

# Check ngrok installed
if ! command -v ngrok &> /dev/null; then
    echo "[ERROR] ngrok not found. Install with:"
    echo "  Windows: choco install ngrok"
    echo "  Mac:     brew install ngrok"
    echo "  Linux:   snap install ngrok"
    echo "  Or:      https://ngrok.com/download"
    exit 1
fi

# Check backend is running
if ! curl -s "http://localhost:${PORT}/docs" > /dev/null 2>&1; then
    echo "[WARN] Backend not detected on port ${PORT}"
    echo "  Start with: uvicorn app.main:app --reload --port ${PORT}"
    echo "  Continuing anyway..."
    echo ""
fi

# Required .env flags
echo "Required .env flags:"
echo "  ENABLE_LIVING_AGENT=true"
echo "  ENABLE_CROSS_PLATFORM_IDENTITY=true"
echo "  ENABLE_ZALO_WEBHOOK=true"
echo "  DEFAULT_PERSONALITY_MODE=soul"
echo ""
echo "Required tokens:"
echo "  FACEBOOK_VERIFY_TOKEN=<your_verify_token>"
echo "  FACEBOOK_PAGE_ACCESS_TOKEN=<from_facebook_developer>"
echo "  ZALO_OA_ACCESS_TOKEN=<from_zalo_oa_admin>"
echo "  ZALO_OA_SECRET_KEY=<from_zalo_oa_admin>"
echo ""

# Webhook paths
echo "Webhook endpoints:"
echo "  Messenger: /api/v1/messenger/webhook"
echo "  Zalo:      /api/v1/zalo/webhook"
echo ""

# Start ngrok
if [ -n "$NGROK_DOMAIN" ]; then
    echo "Starting ngrok with custom domain: ${NGROK_DOMAIN}"
    echo "  ngrok http ${PORT} --domain=${NGROK_DOMAIN}"
    echo ""
    ngrok http "${PORT}" --domain="${NGROK_DOMAIN}"
else
    echo "Starting ngrok (free tier — URL changes each restart)"
    echo "  Tip: Set NGROK_DOMAIN=your-name.ngrok-free.app for stable URL"
    echo "  ngrok http ${PORT}"
    echo ""
    ngrok http "${PORT}"
fi
