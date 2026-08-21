#!/usr/bin/env bash
# يحدّث نطاقات Cloudflare في nginx حتى يظهر IP الحقيقي للزائر.
#   sudo bash deploy/hetzner/cloudflare-realip.sh
set -euo pipefail

OUT="${1:-/etc/nginx/conf.d/cloudflare-realip.conf}"
TMP="$(mktemp)"

{
  echo "# Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) — do not edit by hand"
  echo "real_ip_header CF-Connecting-IP;"
  echo "real_ip_recursive on;"
  echo
  curl -fsSL https://www.cloudflare.com/ips-v4 | awk '{print "set_real_ip_from " $1 ";"}'
  echo
  curl -fsSL https://www.cloudflare.com/ips-v6 | awk '{print "set_real_ip_from " $1 ";"}'
} >"$TMP"

install -m 0644 "$TMP" "$OUT"
rm -f "$TMP"
echo "==> wrote $OUT"
if command -v nginx >/dev/null 2>&1; then
  nginx -t
  systemctl reload nginx
fi
