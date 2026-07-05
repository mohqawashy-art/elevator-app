#!/usr/bin/env bash
# تحقق من نشر tenant — health + version + صفحات رئيسية
set -euo pipefail

BASE="${1%/}"
FAIL=0

check() {
  local path="$1"
  local expect="${2:-200}"
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' "$BASE$path" || echo "000")
  if [ "$code" = "$expect" ]; then
    echo "  OK $path ($code)"
  else
    echo "  FAIL $path (got $code, want $expect)"
    FAIL=1
  fi
}

echo "==> Verify $BASE"

HEALTH=$(curl -sS "$BASE/api/health" || echo '{}')
echo "  health: $HEALTH"
echo "$HEALTH" | grep -q '"database": true' || { echo "  FAIL database"; FAIL=1; }

VERSION=$(curl -sS "$BASE/api/version" || echo '{}')
echo "  version: $(echo "$VERSION" | head -c 200)"

check /login 200
check /api/health 200

if [ "$FAIL" -eq 0 ]; then
  echo "==> verify OK"
else
  echo "==> verify FAILED"
  exit 1
fi
