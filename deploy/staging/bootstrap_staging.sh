#!/usr/bin/env bash
# تشغيل مرة واحدة على VM الإنتاج لإنشاء staging معزول على نفس الجهاز.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_USER="liftcore-staging"
DB_NAME="liftcore_staging"
DB_USER="liftcore_staging"
ENV_DIR="/etc/liftcore"
ENV_FILE="$ENV_DIR/staging.env"
NGINX_SITE="/etc/nginx/sites-available/test.liftcoreapp.com"
NGINX_LINK="/etc/nginx/sites-enabled/test.liftcoreapp.com"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run with sudo"
  exit 1
fi
for command in git python3 psql pg_dump nginx openssl curl; do
  command -v "$command" >/dev/null || { echo "ERROR: missing $command"; exit 1; }
done

read -r -p "Staging Basic Auth user [tester]: " BASIC_USER
BASIC_USER="${BASIC_USER:-tester}"
read -r -s -p "Staging Basic Auth password: " BASIC_PASSWORD
echo
if [ -z "$BASIC_PASSWORD" ]; then
  echo "ERROR: Basic Auth password is required"
  exit 1
fi

id "$SERVICE_USER" >/dev/null 2>&1 || \
  useradd --system --home /var/lib/liftcore-staging --shell /usr/sbin/nologin "$SERVICE_USER"
mkdir -p /opt/liftcore-staging /var/lib/liftcore-staging/{uploads,instance} \
  /var/backups/liftcore-staging "$ENV_DIR"

if [ ! -f "$ENV_FILE" ]; then
  DB_PASSWORD="$(openssl rand -hex 24)"
  SECRET_KEY="$(openssl rand -hex 48)"
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    sudo -u postgres psql -v ON_ERROR_STOP=1 \
      -c "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASSWORD' NOSUPERUSER NOCREATEDB NOCREATEROLE;"
  else
    sudo -u postgres psql -v ON_ERROR_STOP=1 \
      -c "ALTER ROLE $DB_USER PASSWORD '$DB_PASSWORD';"
  fi
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    sudo -u postgres createdb --owner="$DB_USER" "$DB_NAME"
  fi
  cat >"$ENV_FILE" <<EOF
SECRET_KEY=$SECRET_KEY
DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_PASSWORD@127.0.0.1:5432/$DB_NAME
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=$DB_NAME
PGUSER=$DB_USER
PGPASSWORD=$DB_PASSWORD
LIFTCORE_ENV=staging
LIFTCORE_PUBLIC_BASE=https://test.liftcoreapp.com
LIFTCORE_HTTPS=1
LIFTCORE_INSTALL_MODULE=1
LIFTCORE_SIGNUP_ENABLED=0
LIFTCORE_ZATCA_MOCK=1
SENTRY_ENVIRONMENT=staging
MAIL_API_KEY=
MOYASAR_SECRET_KEY=
MOYASAR_PUBLISHABLE_KEY=
WHATSAPP_VERIFY_TOKEN=
SENTRY_DSN=
LIFTCORE_GTAG_ID=
EOF
  chmod 640 "$ENV_FILE"
  chown root:"$SERVICE_USER" "$ENV_FILE"
else
  echo "Keeping existing $ENV_FILE"
fi

install -m 0644 "$SCRIPT_DIR/liftcore-staging.service" /etc/systemd/system/liftcore-staging.service
install -m 0644 "$SCRIPT_DIR/test.liftcoreapp.com.nginx" "$NGINX_SITE"
ln -sfn "$NGINX_SITE" "$NGINX_LINK"
printf '%s:%s\n' "$BASIC_USER" "$(openssl passwd -apr1 "$BASIC_PASSWORD")" \
  >/etc/nginx/.htpasswd-liftcore-staging
chmod 640 /etc/nginx/.htpasswd-liftcore-staging
chown root:www-data /etc/nginx/.htpasswd-liftcore-staging

chown -R "$SERVICE_USER:$SERVICE_USER" /opt/liftcore-staging \
  /var/lib/liftcore-staging /var/backups/liftcore-staging
systemctl daemon-reload
systemctl enable liftcore-staging.service
nginx -t
systemctl reload nginx

bash "$SCRIPT_DIR/deploy_staging.sh"

echo
echo "Staging service installed."
echo "After DNS points test.liftcoreapp.com to this VM, run:"
echo "  sudo certbot --nginx -d test.liftcoreapp.com"
