#!/usr/bin/env bash
# إصلاح Nginx — توجيه jama.liftcoreapp.com للتطبيق بدل صفحة Coming Soon
#   cd ~/liftcore/elevator-app && git pull && bash deploy/fix_jama_nginx.sh

set -euo pipefail

DOMAIN="${DOMAIN:-jama.liftcoreapp.com}"
PORT="${PORT:-5002}"
NGINX_SITE="/etc/nginx/sites-available/${DOMAIN}"
ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"

echo "==> Fix Nginx for $DOMAIN -> 127.0.0.1:$PORT"

echo ""
echo "==> إعدادات Nginx الحالية لـ $DOMAIN:"
sudo grep -R "server_name.*${DOMAIN}" /etc/nginx/sites-enabled/ /etc/nginx/sites-available/ 2>/dev/null || echo "  (لا يوجد)"

echo ""
echo "==> كتابة إعداد proxy للتطبيق"
sudo tee "$NGINX_SITE" >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf "$NGINX_SITE" "$ENABLED"

# تعطيل أي ملف قديم يعرض Coming Soon لنفس النطاق
for f in /etc/nginx/sites-enabled/*; do
  [ -f "$f" ] || continue
  if [ "$f" = "$ENABLED" ]; then continue; fi
  if sudo grep -q "server_name.*${DOMAIN}" "$f" 2>/dev/null; then
    echo "  تعطيل تكرار: $f"
    sudo rm -f "$f"
  fi
done

sudo nginx -t
sudo systemctl reload nginx

if command -v certbot >/dev/null 2>&1; then
  echo ""
  echo "==> HTTPS"
  sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect \
    -m "${CERTBOT_EMAIL:-admin@liftcoreapp.com}" 2>/dev/null || \
  sudo certbot --nginx -d "$DOMAIN" || true
  if [ -f /etc/nginx/snippets/liftcore-security.conf ]; then
    sudo grep -q 'liftcore-security.conf' "$NGINX_SITE" || \
      sudo sed -i '/listen 443 ssl/a\    include snippets/liftcore-security.conf;' "$NGINX_SITE" 2>/dev/null || true
    sudo nginx -t && sudo systemctl reload nginx
  fi
fi

echo ""
echo "==> تحقق"
curl -sSI "http://127.0.0.1:${PORT}/" -H "Host: ${DOMAIN}" 2>/dev/null | head -5 || \
curl -sSI "http://127.0.0.1:${PORT}/login" | head -5 || true
echo ""
echo "افتح: https://${DOMAIN}/login"
echo "  admin / admin123"
