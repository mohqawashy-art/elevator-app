#!/usr/bin/env bash
# LiftCore — تجهيز VPS جديد (Hetzner / Ubuntu 24.04)
# شغّل كـ root مرة واحدة:
#   apt-get update && apt-get install -y git
#   git clone https://github.com/mohqawashy-art/elevator-app.git /tmp/liftcore-src
#   bash /tmp/liftcore-src/deploy/hetzner/bootstrap.sh
#
# متغيرات اختيارية:
#   APP_USER=info
#   GIT_URL=https://github.com/mohqawashy-art/elevator-app.git
#   GUNICORN_WORKERS=4
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: شغّل السكربت كـ root (sudo bash deploy/hetzner/bootstrap.sh)"
  exit 1
fi

APP_USER="${APP_USER:-info}"
GIT_URL="${GIT_URL:-https://github.com/mohqawashy-art/elevator-app.git}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-4}"
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_DIR:-${APP_HOME}/liftcore/elevator-app}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_ENV="/etc/liftcore/platform.env"
PG_USER="${PG_USER:-liftcore}"
PG_DB="${PG_DB:-liftcore}"

export DEBIAN_FRONTEND=noninteractive

echo "==> 1/10 حزم النظام"
apt-get update -qq
apt-get install -y \
  git curl ca-certificates ufw fail2ban unattended-upgrades \
  python3 python3-venv python3-pip python3-dev build-essential \
  nginx postgresql postgresql-contrib \
  openssl rsync acl

timedatectl set-timezone Asia/Riyadh || true

if [ ! -f /swapfile ]; then
  echo "==> swap 2G"
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> 2/10 مستخدم ${APP_USER}"
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$APP_USER"
fi
usermod -aG sudo "$APP_USER"
if [ -f /root/.ssh/authorized_keys ]; then
  mkdir -p "${APP_HOME}/.ssh"
  cp /root/.ssh/authorized_keys "${APP_HOME}/.ssh/authorized_keys"
  chmod 700 "${APP_HOME}/.ssh"
  chmod 600 "${APP_HOME}/.ssh/authorized_keys"
  chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}/.ssh"
fi

echo "==> 3/10 جدار ناري"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl enable --now fail2ban

echo "==> 4/10 PostgreSQL"
systemctl enable --now postgresql
if [ ! -f /etc/liftcore/.pg_password ]; then
  PG_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  mkdir -p /etc/liftcore
  umask 077
  printf '%s\n' "$PG_PASSWORD" > /etc/liftcore/.pg_password
  chown root:root /etc/liftcore/.pg_password
else
  PG_PASSWORD="$(tr -d '\r\n' < /etc/liftcore/.pg_password)"
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${PG_USER}'" | grep -q 1; then
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE USER ${PG_USER} WITH PASSWORD '${PG_PASSWORD}';"
else
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER USER ${PG_USER} WITH PASSWORD '${PG_PASSWORD}';"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1; then
  sudo -u postgres createdb -O "$PG_USER" "$PG_DB"
fi

echo "==> 5/10 الكود"
mkdir -p "${APP_HOME}/liftcore/logs" "${APP_HOME}/liftcore/backups"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}/liftcore"
if [ ! -d "${APP_DIR}/.git" ]; then
  sudo -u "$APP_USER" git clone "$GIT_URL" "$APP_DIR"
else
  sudo -u "$APP_USER" git -C "$APP_DIR" fetch origin main
  sudo -u "$APP_USER" git -C "$APP_DIR" checkout main
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only origin main || true
fi
sudo -u "$APP_USER" mkdir -p \
  "${APP_DIR}/instance" \
  "${APP_DIR}/static/uploads" \
  "${APP_DIR}/uploads/signatures"

echo "==> 6/10 Python venv"
if [ ! -x "${APP_DIR}/.venv/bin/python" ]; then
  sudo -u "$APP_USER" python3 -m venv "${APP_DIR}/.venv"
fi
sudo -u "$APP_USER" "${APP_DIR}/.venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "${APP_DIR}/.venv/bin/pip" install -q -r "${APP_DIR}/requirements.txt"

echo "==> 7/10 platform.env"
mkdir -p /etc/liftcore
if [ ! -f "$PLATFORM_ENV" ]; then
  SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat >"$PLATFORM_ENV" <<EOF
SECRET_KEY=${SECRET_KEY}
LIFTCORE_HTTPS=1
LIFTCORE_INSTALL_MODULE=1
LIFTCORE_ALEMBIC=1
LIFTCORE_PUBLIC_BASE=https://app.liftcoreapp.com
DATABASE_URL=postgresql+psycopg://${PG_USER}:${PG_PASSWORD}@127.0.0.1:5432/${PG_DB}
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=${PG_DB}
PGUSER=${PG_USER}
PGPASSWORD=${PG_PASSWORD}
SENTRY_ENVIRONMENT=production
GOOGLE_MAPS_API_KEY=
MAIL_API_KEY=
MAIL_FROM=LiftCore <noreply@liftcoreapp.com>
SENTRY_DSN=
EOF
fi
chown "root:${APP_USER}" "$PLATFORM_ENV"
chmod 640 "$PLATFORM_ENV"

echo "==> 8/10 systemd"
UNIT_SRC="${SCRIPT_DIR}/liftcore.service"
if [ ! -f "$UNIT_SRC" ] && [ -f "${APP_DIR}/deploy/hetzner/liftcore.service" ]; then
  UNIT_SRC="${APP_DIR}/deploy/hetzner/liftcore.service"
fi
sed \
  -e "s|/home/info/liftcore/elevator-app|${APP_DIR}|g" \
  -e "s|^User=info|User=${APP_USER}|" \
  -e "s|^Group=info|Group=${APP_USER}|" \
  -e "s|--workers 4|--workers ${GUNICORN_WORKERS}|" \
  "$UNIT_SRC" > /etc/systemd/system/liftcore.service
systemctl daemon-reload
systemctl enable liftcore.service

echo "==> 9/10 nginx + شهادة مؤقتة"
if [ ! -f /etc/ssl/certs/liftcore-origin.crt ]; then
  openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout /etc/ssl/private/liftcore-origin.key \
    -out /etc/ssl/certs/liftcore-origin.crt \
    -subj "/CN=app.liftcoreapp.com" \
    -addext "subjectAltName=DNS:app.liftcoreapp.com,DNS:jama.liftcoreapp.com,DNS:liftcoreapp.com,DNS:www.liftcoreapp.com"
  chmod 640 /etc/ssl/private/liftcore-origin.key
fi
NGINX_SRC="${SCRIPT_DIR}/nginx.conf"
if [ ! -f "$NGINX_SRC" ]; then
  NGINX_SRC="${APP_DIR}/deploy/hetzner/nginx.conf"
fi
install -m 0644 "$NGINX_SRC" /etc/nginx/sites-available/liftcore
ln -sfn /etc/nginx/sites-available/liftcore /etc/nginx/sites-enabled/liftcore
rm -f /etc/nginx/sites-enabled/default
if [ -x "${APP_DIR}/deploy/hetzner/cloudflare-realip.sh" ]; then
  bash "${APP_DIR}/deploy/hetzner/cloudflare-realip.sh" || true
fi
nginx -t
systemctl enable --now nginx
systemctl reload nginx

echo "==> 10/10 ترحيل قاعدة فارغة + إقلاع"
set -a
# shellcheck disable=SC1090
source "$PLATFORM_ENV"
set +a
sudo -u "$APP_USER" env \
  DATABASE_URL="$DATABASE_URL" \
  SECRET_KEY="$SECRET_KEY" \
  LIFTCORE_HTTPS=1 \
  "${APP_DIR}/.venv/bin/python" "${APP_DIR}/deploy/migrate_db.py" || true
sudo -u "$APP_USER" env \
  DATABASE_URL="$DATABASE_URL" \
  SECRET_KEY="$SECRET_KEY" \
  LIFTCORE_HTTPS=1 \
  "${APP_DIR}/.venv/bin/python" "${APP_DIR}/init_db.py" || true

systemctl restart liftcore
sleep 3
systemctl is-active --quiet liftcore

PUBLIC_IP="$(curl -fsSL https://ifconfig.me/ip || hostname -I | awk '{print $1}')"
HEALTH="$(curl -fsS "http://127.0.0.1/api/health" || true)"

echo ""
echo "=============================================="
echo "  السيرفر جاهز"
echo "  IP: ${PUBLIC_IP}"
echo "  health: ${HEALTH}"
echo ""
echo "  اختبر من جهازك:"
echo "    curl http://${PUBLIC_IP}/api/health"
echo ""
echo "  للدخول على الواجهة قبل DNS — أضف في hosts:"
echo "    ${PUBLIC_IP}  app.liftcoreapp.com jama.liftcoreapp.com"
echo "  ثم افتح: https://app.liftcoreapp.com/login"
echo "  (تحذير شهادة المتصفح متوقع حتى شهادة Cloudflare Origin)"
echo ""
echo "  الخطوة التالية: تصدير بيانات GCP ثم:"
echo "    sudo bash ${APP_DIR}/deploy/hetzner/import_to_new.sh /path/to/bundle.tar.gz"
echo "=============================================="
echo ""
echo "  SECRET_KEY الحالي مؤقت — الاستيراد ينسخ مفتاح الإنتاج."
echo "  كلمة Postgres محفوظة في /etc/liftcore/.pg_password (صلاحيات root)."
