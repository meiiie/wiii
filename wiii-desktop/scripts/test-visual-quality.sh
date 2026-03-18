#!/bin/bash
# Visual Quality Test — tests multiple simulation types via API
# Usage: bash scripts/test-visual-quality.sh

set -e

API_URL="http://localhost:8000"
ENV_FILE="$(dirname "$0")/../../maritime-ai-service/.env"
API_KEY=$(grep "^API_KEY=" "$ENV_FILE" | head -1 | sed 's/API_KEY=//' | tr -d '"' | tr -d "'" | tr -d '\r')
PYTHON="$(dirname "$0")/../../maritime-ai-service/.venv/Scripts/python"
OUTDIR="C:/Users/Admin/AppData/Local/Temp"

echo "=== Visual Quality Test Suite ==="
echo "API Key length: ${#API_KEY}"
echo ""

QUERIES=(
  "projectile|Mo phong chuyen dong nem xien bang Canvas co dieu chinh goc va van toc"
  "solar-system|Mo phong he mat troi don gian voi cac hanh tinh quay quanh bang Canvas"
  "spring-mass|Mo phong he lo xo khoi luong bang Canvas co dieu chinh do cung va khoi luong"
)

TOTAL_SCORE=0
TOTAL_TESTS=0

for entry in "${QUERIES[@]}"; do
  IFS='|' read -r NAME QUERY <<< "$entry"
  OUTFILE="$OUTDIR/wiii_test_${NAME}.txt"

  echo "--- Test: $NAME ---"
  echo "Query: $QUERY"

  curl -sN -X POST "$API_URL/api/v1/chat/stream/v3" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    --data-raw "{\"message\":\"$QUERY\",\"user_id\":\"test-$NAME\",\"session_id\":\"pw-$NAME-$(date +%s)\",\"role\":\"student\"}" \
    --max-time 180 -o "$OUTFILE" 2>/dev/null

  SIZE=$(wc -c < "$OUTFILE")
  echo "Response: ${SIZE} bytes"

  # Analyze with Python
  RESULT=$("$PYTHON" << PYEOF
import json, re, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
with open('$OUTFILE', 'r', encoding='utf-8', errors='replace') as f:
    raw = f.read()
events = re.findall(r'data: ({.*?})\n', raw)
qr = raw.count('Quality score')
tc = raw.count('tool_create_visual_code')
best = ''
for e in events:
    try:
        obj = json.loads(e)
        c = obj.get('content', {})
        if isinstance(c, dict):
            h = c.get('fallback_html') or c.get('code_html', '')
            if h and len(h) > len(best): best = h
    except: pass
if best:
    lo = best.lower()
    s = 0
    m = []
    if '--bg' in best and '--accent' in best: s += 1; m.append('css_vars')
    if '<canvas' in lo and 'requestAnimationFrame' in best: s += 1; m.append('canvas_raf')
    if any(k in best for k in ['deltaTime','dt ','elapsed']): s += 1; m.append('deltaTime')
    if 'wiiivisualbridge' in lo: s += 1; m.append('bridge')
    if 'readout' in lo or 'aria-live' in best or lo.count('<span id=')>=3: s += 1; m.append('readouts')
    if 'STATE MODEL' in best: s += 1; m.append('planning')
    if 'prefers-color-scheme' in best: s += 1; m.append('dark_mode')
    if 'DOCTYPE' not in best: s += 1; m.append('fragment')
    if 'grid' in lo or 'flex' in lo: s += 1; m.append('grid_flex')
    if lo.count('range') >= 2: s += 1; m.append('controls')
    lines = best.count(chr(10)) + 1
    print(f'{lines}|{len(best)}|{s}|{qr}|{tc}|{",".join(m)}')
else:
    print('0|0|0|0|0|none')
PYEOF
)

  IFS='|' read -r LINES CHARS SCORE REJECTS TOOLS MARKERS <<< "$RESULT"

  echo "Lines: $LINES | Chars: $CHARS | Score: $SCORE/10 | Rejections: $REJECTS | Tool calls: $TOOLS"
  echo "Markers: $MARKERS"
  echo ""

  TOTAL_SCORE=$((TOTAL_SCORE + SCORE))
  TOTAL_TESTS=$((TOTAL_TESTS + 1))
done

AVG_SCORE=$((TOTAL_SCORE / TOTAL_TESTS))
echo "=== SUMMARY ==="
echo "Tests: $TOTAL_TESTS | Avg Score: $AVG_SCORE/10 | Total Score: $TOTAL_SCORE/${TOTAL_TESTS}0"
echo ""
if [ "$AVG_SCORE" -ge 6 ]; then
  echo "PASS - Average quality score >= 6/10"
else
  echo "NEEDS IMPROVEMENT - Average quality score < 6/10"
fi
