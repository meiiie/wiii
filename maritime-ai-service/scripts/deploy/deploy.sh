#!/bin/bash
# =============================================================================
# Wiii Production Deployment Script
# by The Wiii Lab (Hong Linh Linh Hung)
#
# Domain: holilihu.online
#
# Usage:
#   cd /opt/wiii && ./maritime-ai-service/scripts/deploy/deploy.sh
#
# What this does:
#   1. Pulls latest code from git
#   2. Builds Docker images
#   3. Starts databases, waits for health
#   4. Runs Alembic migrations
#   5. Starts App, waits for health
#   6. Starts Nginx reverse proxy
#   7. Reloads Caddy (SSL) + final health check
#
# First-time setup:
#   1. Run setup-server.sh first
#   2. Clone repo: git clone <repo-url> /opt/wiii
#   3. Create .env.production: cp scripts/deploy/.env.production.template maritime-ai-service/.env.production
#   4. Edit .env.production with real secrets
#   5. Copy Caddyfile: sudo cp scripts/deploy/Caddyfile /etc/caddy/Caddyfile
#   6. Run this script
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Configuration
APP_DIR="/opt/wiii"
SERVICE_DIR="${APP_DIR}/maritime-ai-service"
COMPOSE_FILE="docker-compose.prod.yml"
DOMAIN="${WIII_DOMAIN:-holilihu.online}"

echo ""
echo "============================================="
echo "   Wiii Production Deploy"
echo "   $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================="
echo ""

# ─────────────────────────────────────────────────
# Pre-checks
# ─────────────────────────────────────────────────
if [ ! -d "$SERVICE_DIR" ]; then
    error "Service directory not found: $SERVICE_DIR"
    error "Clone the repo first: git clone <repo-url> $APP_DIR"
    exit 1
fi

if [ ! -f "$SERVICE_DIR/.env.production" ]; then
    error "Missing .env.production!"
    error "Copy and edit the template:"
    error "  cp $SERVICE_DIR/scripts/deploy/.env.production.template $SERVICE_DIR/.env.production"
    exit 1
fi

# Check for CHANGE_ME placeholder values
if grep -q "CHANGE_ME" "$SERVICE_DIR/.env.production"; then
    warn "Found CHANGE_ME placeholders in .env.production!"
    warn "Update ALL secrets before deploying to production."
    echo ""
    grep "CHANGE_ME" "$SERVICE_DIR/.env.production" | head -5
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ─────────────────────────────────────────────────
# Step 1: Pull latest code
# ─────────────────────────────────────────────────
info "Step 1/7: Pulling latest code..."
cd "$APP_DIR"
git pull origin main

# ─────────────────────────────────────────────────
# Step 2: Build Docker images
# ─────────────────────────────────────────────────
info "Step 2/7: Building Docker images..."
cd "$SERVICE_DIR"
docker compose -f "$COMPOSE_FILE" build app

# ─────────────────────────────────────────────────
# Step 3: Start database services first
# ─────────────────────────────────────────────────
info "Step 3/7: Starting database services..."
docker compose -f "$COMPOSE_FILE" up -d postgres minio minio-init valkey

# Wait for databases to be healthy
info "Waiting for databases to be ready..."
TIMEOUT=60
ELAPSED=0
while ! docker compose -f "$COMPOSE_FILE" ps postgres | grep -q "healthy"; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        error "PostgreSQL did not become healthy within ${TIMEOUT}s"
        docker compose -f "$COMPOSE_FILE" logs postgres --tail 20
        exit 1
    fi
done
info "PostgreSQL is healthy."

# ─────────────────────────────────────────────────
# Step 4: Run database migrations
# ─────────────────────────────────────────────────
info "Step 4/7: Running Alembic migrations..."
docker compose -f "$COMPOSE_FILE" run --rm app alembic upgrade head
info "Migrations complete."

# ─────────────────────────────────────────────────
# Step 5: Start/restart app
# ─────────────────────────────────────────────────
info "Step 5/7: Starting application..."
docker compose -f "$COMPOSE_FILE" up -d app

# Wait for app to be healthy before starting Nginx
info "Waiting for app health check..."
TIMEOUT=90
ELAPSED=0
while ! docker compose -f "$COMPOSE_FILE" ps app | grep -q "healthy"; do
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        error "App did not become healthy within ${TIMEOUT}s"
        docker compose -f "$COMPOSE_FILE" logs app --tail 50
        exit 1
    fi
    echo -n "."
done
echo ""
info "App is healthy."

# ─────────────────────────────────────────────────
# Step 6: Start/restart Nginx
# ─────────────────────────────────────────────────
info "Step 6/7: Starting Nginx reverse proxy..."
docker compose -f "$COMPOSE_FILE" up -d nginx

# ─────────────────────────────────────────────────
# Step 7: Reload Caddy + final health check
# ─────────────────────────────────────────────────
info "Step 7/7: Reloading Caddy (SSL)..."
sudo systemctl reload caddy 2>/dev/null || warn "Caddy reload failed (may not be configured yet)"

# Final health check via localhost
sleep 3
if curl -sf "http://localhost:8000/api/v1/health/live" > /dev/null 2>&1; then
    info "Health check passed! (localhost:8000)"
else
    warn "Direct health check failed — app may still be starting"
fi

# ─────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────
echo ""
echo "============================================="
info "Deployment successful!"
echo "============================================="
echo ""
echo "  URL:      https://${DOMAIN}"
echo "  API:      https://${DOMAIN}/api/v1/health/live"
echo "  API Docs: https://${DOMAIN}/docs"
echo ""
echo "Useful commands:"
echo "  docker compose -f $COMPOSE_FILE ps              # Service status"
echo "  docker compose -f $COMPOSE_FILE logs -f app     # App logs"
echo "  docker compose -f $COMPOSE_FILE logs -f nginx   # Nginx logs"
echo "  docker compose -f $COMPOSE_FILE restart app     # Restart app"
echo "  sudo journalctl -u caddy -f                     # Caddy SSL logs"
echo ""
