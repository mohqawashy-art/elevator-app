#!/usr/bin/env bash
# تعزيز HTTPS وأمان Nginx لجميع نطاقات LiftCore
#   cd ~/liftcore/jama-elevator-app && git pull && bash deploy/fix_https_security.sh
#
# يصلح: شهادة منتهية، إعادة توجيه HTTP→HTTPS، رؤوس الأمان (HSTS)

set -euo pipefail

DOMAINS="${DOMAINS:-jama.liftcoreapp.com app.liftcoreapp.com}"
EMAIL="${CERTBOT_EMAIL:-admin@liftcoreapp.com}"

echo "=============================================="
echo "  LiftCore — HTTPS & security headers"
echo "=============================================="

echo ""
echo "==> 1) رؤوس الأمان (snippet)"
sudo tee /etc/nginx/snippets/liftcore-security.conf >/dev/null <<'EOF'
# LiftCore — أمان المتصفح (قفل آمن)
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
EOF

echo ""
echo "==> 2) تضمين snippet في مواقع Nginx"
for domain in $DOMAINS; do
  site="/etc/nginx/sites-available/${domain}"
  if [ ! -f "$site" ]; then
    echo "  skip (no config): $domain"
    continue
  fi
  if sudo grep -q 'liftcore-security.conf' "$site"; then
    echo "  OK already: $domain"
    continue
  fi
  # أضف بعد أول server { في كتلة SSL إن وُجدت
  if sudo grep -q 'listen 443' "$site"; then
    sudo sed -i '/listen 443 ssl/a\    include snippets/liftcore-security.conf;' "$site" 2>/dev/null || true
  fi
  if ! sudo grep -q 'liftcore-security.conf' "$site"; then
    sudo sed -i '/server {/a\    include snippets/liftcore-security.conf;' "$site" 2>/dev/null || true
  fi
  echo "  patched: $domain"
done

echo ""
echo "==> 3) HTTPS — تجديد/إصدار شهادات Let's Encrypt"
if command -v certbot >/dev/null 2>&1; then
  for domain in $DOMAINS; do
    site="/etc/nginx/sites-available/${domain}"
    [ -f "$site" ] || continue
    if sudo grep -q 'ssl_certificate' "$site" 2>/dev/null; then
      echo "  renew: $domain"
      sudo certbot renew --cert-name "$domain" --nginx --quiet 2>/dev/null || \
      sudo certbot renew --nginx --quiet 2>/dev/null || true
    else
      echo "  issue: $domain"
      sudo certbot --nginx -d "$domain" --non-interactive --agree-tos \
        -m "$EMAIL" --redirect 2>/dev/null || \
      sudo certbot --nginx -d "$domain" || true
    fi
  done
else
  echo "  WARN: certbot غير مثبت — sudo apt install certbot python3-certbot-nginx"
fi

echo ""
echo "==> 4) LIFTCORE_HTTPS على الخدمات"
for svc in liftcore liftcore-jama; do
  drop="/etc/systemd/system/${svc}.service.d"
  if systemctl list-unit-files "${svc}.service" &>/dev/null; then
    sudo mkdir -p "$drop"
    printf '%s\n' '[Service]' 'Environment=LIFTCORE_HTTPS=1' | sudo tee "$drop/https.conf" >/dev/null
    echo "  $svc: LIFTCORE_HTTPS=1"
  fi
done
sudo systemctl daemon-reload 2>/dev/null || true
for svc in liftcore liftcore-jama; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    sudo systemctl restart "$svc"
    echo "  restarted $svc"
  fi
done

echo ""
echo "==> 5) اختبار Nginx"
sudo nginx -t
sudo systemctl reload nginx

echo ""
echo "==> 6) تحقق"
for domain in $DOMAINS; do
  echo -n "  https://$domain/login → "
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 8 "https://${domain}/login" 2>/dev/null || echo 'FAIL')"
  echo "$code"
  curl -sSI --max-time 8 "https://${domain}/login" 2>/dev/null | grep -iE 'strict-transport|location:' | head -2 || true
done

echo ""
echo "=============================================="
echo "  تم. شارك الرابط دائماً بـ HTTPS:"
echo "  https://jama.liftcoreapp.com/login"
echo "  https://app.liftcoreapp.com/login"
echo ""
echo "  لا تشارك http:// أو عنوان IP"
echo "=============================================="
