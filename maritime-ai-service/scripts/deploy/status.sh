#!/bin/bash
# =============================================================================
# Wiii Production Status Dashboard
# by The Wiii Lab (Hong Linh Linh Hung)
#
# Usage: ./status.sh
# Shows: container status, resource usage, disk, DB stats, uptime
# =============================================================================

set -euo pipefail

SERVICE_DIR="/opt/wiii/maritime-ai-service"
COMPOSE_FILE="docker-compose.prod.yml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}============================================="
echo "   Wiii Production Dashboard"
echo "   $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo -e "=============================================${NC}"

# ─────────────────────────────────────────────────
# Container Status
# ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}--- Container Status ---${NC}"
cd "$SERVICE_DIR"
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker compose not running"

# ─────────────────────────────────────────────────
# Resource Usage
# ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}--- Resource Usage ---${NC}"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null || echo "No running containers"

# ─────────────────────────────────────────────────
# System Resources
# ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}--- System ---${NC}"
echo "  Uptime:  $(uptime -p 2>/dev/null || uptime)"
echo "  RAM:     $(free -h | awk 'NR==2 {printf "%s used / %s total (%s free)", $3, $2, $7}')"
echo "  Swap:    $(free -h | awk 'NR==3 {printf "%s used / %s total", $3, $2}')"
echo "  Disk:    $(df -h / | awk 'NR==2 {printf "%s used / %s total (%s free, %s)", $3, $2, $4, $5}')"

# ─────────────────────────────────────────────────
# PostgreSQL
# ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}--- PostgreSQL ---${NC}"
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U wiii -d wiii_ai -t -c \
    "SELECT 'Active connections: ' || count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || echo "  PostgreSQL not reachable"
docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U wiii -d wiii_ai -t -c \
    "SELECT 'Database size: ' || pg_size_pretty(pg_database_size('wiii_ai'));" 2>/dev/null || true

# ─────────────────────────────────────────────────
# Backups
# ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}--- Backups ---${NC}"
BACKUP_COUNT=$(find /opt/wiii/backups -name "wiii_ai_*.dump" 2>/dev/null | wc -l)
LATEST_BACKUP=$(ls -t /opt/wiii/backups/wiii_ai_*.dump 2>/dev/null | head -1 || echo "none")
echo "  Total backups: ${BACKUP_COUNT}"
if [ "$LATEST_BACKUP" != "none" ]; then
    BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 3600 ))
    BACKUP_SIZE=$(du -h "$LATEST_BACKUP" | awk '{print $1}')
    echo "  Latest: $(basename "$LATEST_BACKUP") (${BACKUP_SIZE}, ${BACKUP_AGE}h ago)"
else
    echo -e "  Latest: ${RED}No backups found!${NC}"
fi

# ─────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}--- Health ---${NC}"
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8000/api/v1/health/live 2>/dev/null || echo "unreachable")
NGINX_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:80/health 2>/dev/null || echo "unreachable")

if [ "$API_STATUS" = "200" ]; then
    echo -e "  API:   ${GREEN}OK${NC} (200)"
else
    echo -e "  API:   ${RED}FAIL${NC} (${API_STATUS})"
fi

if [ "$NGINX_STATUS" = "200" ]; then
    echo -e "  Nginx: ${GREEN}OK${NC} (200)"
else
    echo -e "  Nginx: ${RED}FAIL${NC} (${NGINX_STATUS})"
fi

CADDY_STATUS=$(sudo systemctl is-active caddy 2>/dev/null || echo "inactive")
if [ "$CADDY_STATUS" = "active" ]; then
    echo -e "  Caddy: ${GREEN}active${NC}"
else
    echo -e "  Caddy: ${RED}${CADDY_STATUS}${NC}"
fi

echo ""
