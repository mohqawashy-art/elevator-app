#!/usr/bin/env bash
# One-shot: pull latest code + import clients/technicians/elevators on Jama server
#
#   bash deploy/jama_import_now.sh
#   bash deploy/jama_import_now.sh --reset   # wipe DB first, then import
#   bash deploy/jama_import_now.sh --dry-run

set -euo pipefail

JAMA_DIR="${JAMA_DIR:-$HOME/liftcore/jama-elevator-app}"
RESET=0
EXTRA_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --reset) RESET=1 ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

cd "$JAMA_DIR"
git fetch origin main
git reset --hard origin/main

if [ "$RESET" = "1" ]; then
  echo "==> Reset Jama database"
  SEED=0 bash deploy/reset_jama_db.sh
fi

chmod +x deploy/import_jama_core_three.sh
bash deploy/import_jama_core_three.sh "${EXTRA_ARGS[@]}"
