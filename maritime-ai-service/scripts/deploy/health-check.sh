#!/bin/bash
# =============================================================================
# Wiii Production Health Check — External Monitoring
# by The Wiii Lab (Hong Linh Linh Hung)
#
# Usage:
#   ./health-check.sh                  # Manual check
#   crontab: */2 * * * * /opt/wiii/maritime-ai-service/scripts/deploy/health-check.sh
#   (Every 2 minutes)
#
# What this does:
#   1. Checks API health endpoint
#   2. Checks all Docker containers are healthy
#   3. Checks disk usage (alert if >85%)
#   4. Checks available memory (alert if <256MB)
#   5. Sends Discord/Telegram alert on failure (with deduplication)
#   6. Sends recovery notification when issues resolve
# =============================================================================

set -euo pipefail

# Configuration
DOMAIN="${WIII_DOMAIN:-holilihu.online}"
COMPOSE_FILE="/opt/wiii/maritime-ai-service/docker-compose.prod.yml"
ALERT_FILE="/tmp/wiii_alert_sent"
LOG_FILE="/var/log/wiii-health.log"

# Alert webhook (set in environment or .env)
# Discord: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
# Telegram: TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# ─────────────────────────────────────────────────
# Check functions
# ─────────────────────────────────────────────────

check_api() {
    local response_code
    response_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 --connect-timeout 5 \
        "http://localhost:8000/api/v1/health/live") || response_code=0

    if [ "$response_code" != "200" ]; then
        echo "API health returned ${response_code} (expected 200)"
        return 1
    fi
    return 0
}

check_nginx() {
    local response_code
    response_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 5 --connect-timeout 3 \
        "http://localhost:80/health") || response_code=0

    if [ "$response_code" != "200" ]; then
        echo "Nginx health returned ${response_code}"
        return 1
    fi
    return 0
}

check_containers() {
    local unhealthy
    unhealthy=$(docker ps --filter "health=unhealthy" --format "{{.Names}}" 2>/dev/null || echo "")
    if [ -n "$unhealthy" ]; then
        echo "Unhealthy containers: ${unhealthy}"
        return 1
    fi
    return 0
}

check_disk() {
    local usage
    usage=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
    if [ "$usage" -gt 85 ]; then
        echo "Disk usage at ${usage}%"
        return 1
    fi
    return 0
}

check_memory() {
    local available
    available=$(free -m | awk 'NR==2 {print $7}')
    if [ "$available" -lt 256 ]; then
        echo "Only ${available}MB RAM available"
        return 1
    fi
    return 0
}

# ─────────────────────────────────────────────────
# Alert functions
# ─────────────────────────────────────────────────

send_alert() {
    local message=$1
    local is_recovery=${2:-false}
    local emoji="🚨"
    local title="Wiii Production Alert"

    if [ "$is_recovery" = "true" ]; then
        emoji="✅"
        title="Wiii Production Recovered"
    fi

    # Discord webhook
    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        curl -s -H "Content-Type: application/json" \
            -d "{\"content\":\"${emoji} **${title}**\n${message}\nTime: $(date -Iseconds)\nDomain: ${DOMAIN}\"}" \
            "$DISCORD_WEBHOOK_URL" > /dev/null 2>&1 || true
    fi

    # Telegram bot
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=${emoji} ${title}%0A${message}%0ATime: $(date -Iseconds)" \
            -d "parse_mode=HTML" > /dev/null 2>&1 || true
    fi
}

# ─────────────────────────────────────────────────
# Run all checks
# ─────────────────────────────────────────────────
ERRORS=""

api_err=$(check_api 2>&1) || ERRORS+="${api_err}. "
nginx_err=$(check_nginx 2>&1) || ERRORS+="${nginx_err}. "
container_err=$(check_containers 2>&1) || ERRORS+="${container_err}. "
disk_err=$(check_disk 2>&1) || ERRORS+="${disk_err}. "
memory_err=$(check_memory 2>&1) || ERRORS+="${memory_err}. "

# ─────────────────────────────────────────────────
# Handle results
# ─────────────────────────────────────────────────
if [ -n "$ERRORS" ]; then
    # Alert (with 30-minute deduplication)
    if [ ! -f "$ALERT_FILE" ] || [ $(( $(date +%s) - $(stat -c %Y "$ALERT_FILE" 2>/dev/null || echo 0) )) -gt 1800 ]; then
        send_alert "$ERRORS"
        touch "$ALERT_FILE"
    fi
    echo "[$(date)] ALERT: ${ERRORS}" >> "$LOG_FILE" 2>/dev/null || true
else
    # Recovery notification
    if [ -f "$ALERT_FILE" ]; then
        send_alert "All checks passing." "true"
        rm -f "$ALERT_FILE"
    fi
fi
