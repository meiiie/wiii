#!/usr/bin/env bash
# baseline_capture.sh — drive Locust against /api/v1/chat to produce a
# repeatable pre-canary baseline. Phase 28 of the runtime migration epic
# (#207). Companion to docs/runtime/CANARY_ONBOARDING.md.
#
# Usage:
#   WIII_HOST=https://api.example.com \
#   WIII_API_KEY=key \
#   WIII_USER_ID=baseline-1 \
#   WIII_ORG_ID=org-A \
#   ./loadtest/baseline_capture.sh [output-prefix]
#
# Defaults to legacy_only profile (the whole point of a "baseline" is
# to measure the legacy path before the canary flip changes anything).
# Override profile via WIII_LOAD_PROFILE if you really want.

set -euo pipefail

OUTPUT_PREFIX="${1:-reports/baseline-$(date -u +%Y%m%dT%H%M%SZ)}"
PROFILE="${WIII_LOAD_PROFILE:-legacy_only}"
USERS="${LOCUST_USERS:-30}"
SPAWN_RATE="${LOCUST_SPAWN_RATE:-3}"
DURATION="${LOCUST_DURATION:-5m}"

if [[ -z "${WIII_HOST:-}" ]]; then
    echo "WIII_HOST not set — refusing to guess. See loadtest/README.md." >&2
    exit 2
fi

mkdir -p "$(dirname "$OUTPUT_PREFIX")"

echo "[baseline] profile=$PROFILE users=$USERS spawn=$SPAWN_RATE duration=$DURATION"
echo "[baseline] writing CSV reports to: $OUTPUT_PREFIX*"

WIII_LOAD_PROFILE="$PROFILE" \
locust -f loadtest/locustfile.py --headless \
    -u "$USERS" -r "$SPAWN_RATE" -t "$DURATION" \
    --host "$WIII_HOST" \
    --csv "$OUTPUT_PREFIX"

echo
echo "[baseline] DONE. Inspect:"
echo "  ${OUTPUT_PREFIX}_stats.csv      — p50 / p95 / p99 / fails per endpoint"
echo "  ${OUTPUT_PREFIX}_failures.csv   — non-200 responses (excluding documented 503s)"
echo
echo "[baseline] Next step: capture canary numbers with WIII_LOAD_PROFILE=edge_only"
echo "[baseline]            and compare per docs/runtime/CANARY_ONBOARDING.md step 5."
