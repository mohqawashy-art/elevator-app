#!/usr/bin/env bash
# إفراغ قاعدة جما + سيناريو 10 عملاء للتجربة الكاملة
#
#   cd ~/liftcore/jama-elevator-app && git pull
#   bash deploy/reset_jama_demo.sh

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
SERVICE="${SERVICE:-liftcore-jama}"

if [[ ! -d "$JAMA_DIR" ]]; then
  echo "Missing app dir: $JAMA_DIR"
  exit 1
fi

if [[ ! -f "$DB_FILE" && -f "$HOME/jama-elevator-app/instance/jama.db" ]]; then
  JAMA_DIR="$HOME/jama-elevator-app"
  DB_FILE="$JAMA_DIR/instance/jama.db"
  VENV="${VENV:-$JAMA_DIR/.venv}"
fi

# مسار مطلق لـ SQLite (4 شرطات)
DB_ABS="$(cd "$(dirname "$DB_FILE")" && pwd)/$(basename "$DB_FILE")"
export DATABASE_URL="sqlite:////${DB_ABS}"

echo "==> Reset demo data (Jama)"
echo "    App: $JAMA_DIR"
echo "    DB:  $DB_ABS"

# قاعدة خاطئة قد تُربك التطبيق
rm -f "$JAMA_DIR/instance/liftcore.db" "$JAMA_DIR/liftcore.db" 2>/dev/null || true

sudo systemctl stop "$SERVICE" 2>/dev/null || true

cd "$JAMA_DIR"
if [[ -f "$VENV/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

python3 scripts/reset_jama_demo.py
EXIT=$?

if [[ $EXIT -ne 0 ]]; then
  echo "ERROR: reset failed (exit $EXIT)"
  sudo systemctl start "$SERVICE" 2>/dev/null || true
  exit "$EXIT"
fi

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl start "$SERVICE" 2>/dev/null || true
  sleep 2
fi

echo ""
echo "==> Done — https://jama.liftcoreapp.com/login"
echo "    المكتب: admin / admin123"
echo "    الفني:  Tech-001 / 123456  (أو 0552001001)"
echo "    لا تستخدم Tech-006 (إجازة) أو Tech-007 (غير نشط)"
echo "    الدليل: docs/SCENARIO_10_CLIENTS.md"
