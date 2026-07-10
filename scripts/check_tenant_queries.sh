#!/usr/bin/env bash
# يفشل إذا وُجد استعلام .query. مباشر خارج tenant_scope وسكربتات المنصة.
# استثناءات في نفس السطر: tenant_query | tenant_get_or_404 | skip_tenant | # tenant:
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PATTERN='\.query\.'
ALLOW='tenant_query|tenant_get_or_404|skip_tenant|# tenant:'

SCAN_FILES=(
  app.py
  operations.py
  customer_billing.py
  report_data.py
  entity_links.py
  installation/routes.py
)

VIOLATIONS=""
for f in "${SCAN_FILES[@]}"; do
  [ -f "$f" ] || continue
  while IFS= read -r line; do
    if echo "$line" | grep -Eq "$ALLOW"; then
      continue
    fi
    VIOLATIONS+="$f:$line"$'\n'
  done < <(grep -n "$PATTERN" "$f" 2>/dev/null || true)
done

if [ -n "$VIOLATIONS" ]; then
  echo "Direct .query. without tenant isolation:"
  echo "$VIOLATIONS" | head -40
  COUNT="$(echo "$VIOLATIONS" | grep -c ':' || true)"
  echo ""
  echo "Found $COUNT line(s). Use tenant_query / tenant_get_or_404, or mark platform lookups with # tenant:"
  exit 1
fi

echo "OK: No direct .query. in scanned files"
