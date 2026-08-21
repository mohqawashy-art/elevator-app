#!/usr/bin/env bash
# تثبيت شهادة Cloudflare Origin بدل الشهادة الذاتية.
#   sudo bash deploy/hetzner/enable_cloudflare_ssl.sh /path/origin.pem /path/origin.key
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: شغّل كـ root"
  exit 1
fi

CERT="${1:?origin certificate pem}"
KEY="${2:?origin private key}"

install -m 0644 "$CERT" /etc/ssl/certs/liftcore-origin.crt
install -m 0640 "$KEY" /etc/ssl/private/liftcore-origin.key
nginx -t
systemctl reload nginx
echo "==> Cloudflare Origin certificate installed"
echo "    في Cloudflare: SSL/TLS → Full (strict)"
