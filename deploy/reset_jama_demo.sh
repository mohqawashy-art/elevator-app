#!/usr/bin/env bash
# إفراغ قاعدة جما + سيناريو 10 عملاء للتجربة الكاملة
#
#   cd ~/liftcore/jama-elevator-app && git pull
#   bash deploy/reset_jama_demo.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
SERVICE="${SERVICE:-liftcore-jama}"

if [[ ! -d "$JAMA_DIR" ]]; then
  echo "Missing app dir: $JAMA_DIR"
  exit 1
fi

export DATABASE_URL="sqlite:////${DB_FILE//\\//}"
echo "==> Reset demo data"
echo "    DB: $DB_FILE"

cd "$JAMA_DIR"
python3 scripts/reset_jama_demo.py

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl restart "$SERVICE" 2>/dev/null || true
fi

echo ""
echo "==> Done. Open https://jama.liftcoreapp.com"
echo "    admin / admin123"
echo "    Field: Tech-001 / 123456"
echo "    Guide: docs/SCENARIO_10_CLIENTS.md"
