#!/usr/bin/env bash
# تحديث نسخة عميل (مثل جما) — نفس الكود، خدمة ومجلد مختلفان
# على السيرفر:
#   bash deploy/tenant_update.sh jama ~/jama/elevator-app

set -euo pipefail

SERVICE_NAME="${1:?usage: tenant_update.sh SERVICE_NAME APP_DIR}"
APP_DIR="${2:?usage: tenant_update.sh SERVICE_NAME APP_DIR}"

export SERVICE_NAME
export APP_DIR
bash "$(dirname "$0")/gcp_update.sh"

echo ""
echo "==> Tenant $SERVICE_NAME updated — test maps on your subdomain"
