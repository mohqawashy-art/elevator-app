#!/usr/bin/env bash
# DEPRECATED — لا تستخدم لتجهيز عملاء جدد.
# البديل بعد Multi-Tenant: تسجيل من /signup أو دعوة من لوحة المنصة.
# ⚠️ جما = بيئة اختبار/demo فقط — ليست عميل B2B. يُستبدل بـ tenant demo.
# شغّل من GCP Console SSH (للتراجع/الصيانة فقط):
#   cd ~/liftcore/elevator-app && git pull origin main
#   bash deploy/provision_jama.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
MAIN_DIR="${MAIN_DIR:-$HOME/liftcore/elevator-app}"
SERVICE_NAME="${SERVICE_NAME:-liftcore-jama}"
PORT="${PORT:-5002}"
DOMAIN="${DOMAIN:-jama.liftcoreapp.com}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
SEED_DEMO="${SEED_DEMO:-1}"

echo "==> LiftCore Jama tenant: $DOMAIN"
echo "    App dir: $JAMA_DIR"
echo "    Port:    $PORT"
echo "    DB:      $DB_FILE"

if [ ! -d "$MAIN_DIR/.git" ]; then
  echo "ERROR: main app not found at $MAIN_DIR"
  exit 1
fi

echo ""
echo "==> 1) نسخ/تحديث كود التطبيق"
if [ -d "$JAMA_DIR/.git" ]; then
  cd "$JAMA_DIR"
  git fetch origin main
  git reset --hard origin/main
else
  git clone https://github.com/mohqawashy-art/elevator-app.git "$JAMA_DIR"
  cd "$JAMA_DIR"
fi

echo ""
echo "==> 2) بيئة Python"
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -q --upgrade pip
if [ -f requirements.txt ]; then
  pip install -q -r requirements.txt
fi
pip install -q gunicorn flask flask-sqlalchemy werkzeug cryptography

GUNICORN_BIN="$VENV/bin/gunicorn"
if [ ! -x "$GUNICORN_BIN" ]; then
  echo "ERROR: gunicorn missing after pip install — run: $VENV/bin/pip install gunicorn"
  exit 1
fi
echo "  gunicorn OK: $GUNICORN_BIN"

mkdir -p "$(dirname "$DB_FILE")"
export DATABASE_URL="sqlite:///${DB_FILE}"
# لا تترك liftcore.db في مجلد جما — يُربك التطبيق
rm -f "$JAMA_DIR/instance/liftcore.db" "$JAMA_DIR/liftcore.db" 2>/dev/null || true

echo ""
echo "==> 3) قاعدة بيانات جما"
if [ ! -f "$DB_FILE" ]; then
  python init_db.py
  python scripts/init_install_module.py
  if [ "$SEED_DEMO" = "1" ]; then
    python seed_data.py || true
  fi
  echo "  created new DB: $DB_FILE"
else
  echo "  DB exists — skipped init (delete file to recreate)"
  python scripts/init_install_module.py || true
fi

echo ""
echo "==> 4) خدمة systemd: $SERVICE_NAME"
JAMA_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=LiftCore — Jama Elevators ($DOMAIN)
After=network.target

[Service]
Type=simple
User=${USER}
Group=${USER}
WorkingDirectory=${JAMA_DIR}
Environment=DATABASE_URL=sqlite:///${DB_FILE}
Environment=LIFTCORE_HTTPS=1
Environment=LIFTCORE_INSTALL_MODULE=1
EnvironmentFile=-/etc/liftcore/platform.env
Environment=SECRET_KEY=${JAMA_SECRET}
ExecStart=${GUNICORN_BIN} -w 2 -b 127.0.0.1:${PORT} --timeout 120 app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
sleep 3
if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "ERROR: service failed — journalctl -u $SERVICE_NAME -n 30 --no-pager"
  sudo journalctl -u "$SERVICE_NAME" -n 30 --no-pager || true
  exit 1
fi
echo "  service active on :$PORT"

echo ""
echo "==> 5) Nginx: $DOMAIN"
NGINX_SITE="/etc/nginx/sites-available/${DOMAIN}"
sudo tee "$NGINX_SITE" >/dev/null <<EOF
server {
    listen 80;
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

sudo ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/${DOMAIN}"
sudo nginx -t
sudo systemctl reload nginx

echo ""
echo "==> 6) HTTPS (Let's Encrypt)"
if command -v certbot >/dev/null 2>&1; then
  sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@${DOMAIN#*.}" --redirect 2>/dev/null || \
  sudo certbot --nginx -d "$DOMAIN" || echo "  WARN: certbot failed — شغّل يدوياً: sudo certbot --nginx -d $DOMAIN"
else
  echo "  certbot غير مثبت — بعد التثبيت: sudo certbot --nginx -d $DOMAIN"
fi

echo ""
echo "==> 7) تحقق"
curl -sS --max-time 5 "http://127.0.0.1:${PORT}/api/version" | head -c 400 || true
echo ""
echo ""
echo "=============================================="
echo "  تم تجهيز جما"
echo "  https://${DOMAIN}"
echo "  تسجيل الدخول الافتراضي: admin / admin123"
echo "  غيّر كلمة المرور من: الإعدادات → حسابي"
echo "  بيانات الشركة من: الإعدادات → الشركة والهوية"
echo "=============================================="
