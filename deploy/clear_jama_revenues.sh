#!/usr/bin/env bash
# مسح جميع الإيرادات من قاعدة جما
#
#   bash deploy/clear_jama_revenues.sh --dry-run
#   bash deploy/clear_jama_revenues.sh --yes

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
VENV="${VENV:-$JAMA_DIR/.venv}"
DB_FILE="${DB_FILE:-$JAMA_DIR/instance/jama.db}"
SERVICE="${SERVICE:-liftcore-jama}"
EXTRA=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) EXTRA+=(--dry-run) ;;
    --yes) EXTRA+=(--yes) ;;
    *) EXTRA+=("$arg") ;;
  esac
done

if [[ ! -d "$JAMA_DIR" ]]; then
  echo "Missing app dir: $JAMA_DIR"
  exit 1
fi

if [[ ! -f "$DB_FILE" && -f "$HOME/jama-elevator-app/instance/jama.db" ]]; then
  JAMA_DIR="$HOME/jama-elevator-app"
  DB_FILE="$JAMA_DIR/instance/jama.db"
  VENV="${VENV:-$JAMA_DIR/.venv}"
fi

DB_ABS="$(cd "$(dirname "$DB_FILE")" && pwd)/$(basename "$DB_FILE")"
export DATABASE_URL="sqlite:////${DB_ABS}"

echo "==> Clear all revenues (Jama)"
echo "    App: $JAMA_DIR"
echo "    DB:  $DB_ABS"

sudo systemctl stop "$SERVICE" 2>/dev/null || true

cd "$JAMA_DIR"
if [[ -f "$VENV/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
fi

python3 scripts/clear_jama_revenues.py "${EXTRA[@]}"
EXIT=$?

if [[ $EXIT -ne 0 ]]; then
  echo "ERROR: clear failed (exit $EXIT)"
  sudo systemctl start "$SERVICE" 2>/dev/null || true
  exit "$EXIT"
fi

if [[ " ${EXTRA[*]} " != *" --dry-run "* ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start "$SERVICE" 2>/dev/null || true
    sleep 2
  fi
  echo ""
  echo "Done — https://jama.liftcoreapp.com/revenues"
fi
