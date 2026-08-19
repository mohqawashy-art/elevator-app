#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-https://test.liftcoreapp.com}"
AUTH="${STAGING_BASIC_AUTH:-}"
CURL=(curl --fail --silent --show-error --max-time 15)
if [ -n "$AUTH" ]; then
  CURL+=(-u "$AUTH")
fi

echo "==> service"
systemctl is-active --quiet liftcore-staging
systemctl is-active --quiet liftcore

echo "==> isolated port"
ss -ltn | grep -q '127.0.0.1:5003'
if ss -ltn | grep -qE '(^|[[:space:]])0\.0\.0\.0:5003'; then
  echo "ERROR: staging port is publicly bound"
  exit 1
fi

echo "==> HTTP health"
"${CURL[@]}" "$BASE/api/health" >/dev/null

echo "==> no indexing"
HEADERS="$("${CURL[@]}" -I "$BASE/login")"
echo "$HEADERS" | grep -qi 'x-robots-tag:.*noindex'
"${CURL[@]}" "$BASE/robots.txt" | grep -q 'Disallow: /'

echo "==> environment isolation"
systemctl show liftcore-staging -p Environment | grep -q 'LIFTCORE_ENV_FILE=/etc/liftcore/staging.env'
grep -q '^PGDATABASE=liftcore_staging$' /etc/liftcore/staging.env

echo "OK: staging is healthy and isolated"
