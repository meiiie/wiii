#!/usr/bin/env bash
# =============================================================================
# Wiii Web SPA Build Script
# Sprint 175: "Mot Nen Tang — Nhieu To Chuc"
#
# Builds the React SPA for web deployment (no Tauri compilation needed).
# The same React code works in browser — storage.ts already has localStorage
# fallback, and HTTP uses adaptive fetch when Tauri plugin is unavailable.
#
# Usage:
#   ./scripts/build-web.sh                # Build + copy to nginx/html/
#   ./scripts/build-web.sh --skip-copy    # Build only (dist/)
#
# Output:
#   wiii-desktop/dist/          → Vite SPA build
#   maritime-ai-service/nginx/html/ → Copy for Docker Nginx serving
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$(cd "$DESKTOP_DIR/../maritime-ai-service" && pwd)"
NGINX_HTML="$BACKEND_DIR/nginx/html"

echo "=== Wiii Web SPA Build ==="
echo "Desktop dir: $DESKTOP_DIR"
echo "Backend dir: $BACKEND_DIR"

# 1. Install dependencies (if needed)
cd "$DESKTOP_DIR"
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# 2. Build SPA with Vite
echo "Building SPA..."
npm run build

if [ ! -d "dist" ]; then
    echo "ERROR: Build failed — dist/ not found"
    exit 1
fi

echo "Build complete: $(du -sh dist | cut -f1) total"

# 3. Build embed widget (for LMS iframe)
echo "Building embed widget..."
npm run build:embed

if [ ! -d "dist-embed" ]; then
    echo "WARNING: Embed build failed — dist-embed/ not found"
else
    echo "Embed build complete: $(du -sh dist-embed | cut -f1) total"
fi

# 4. Copy to nginx/html/ (unless --skip-copy)
if [[ "${1:-}" != "--skip-copy" ]]; then
    echo "Copying SPA to $NGINX_HTML..."
    mkdir -p "$NGINX_HTML"
    # Preserve embed directory, clear the rest
    rm -rf "$NGINX_HTML"/assets "$NGINX_HTML"/index.html "$NGINX_HTML"/vite.svg 2>/dev/null || true
    cp -r dist/* "$NGINX_HTML/"
    echo "Deployed to nginx/html/ ($(ls "$NGINX_HTML" | wc -l) items)"
else
    echo "Skipping copy (--skip-copy)"
fi

echo "=== Done ==="
