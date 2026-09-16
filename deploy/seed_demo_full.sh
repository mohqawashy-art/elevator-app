#!/usr/bin/env bash
# ملء demo بالكامل على الإنتاج — slug=demo فقط — لا يمس jama
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f /etc/liftcore/platform.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/liftcore/platform.env
  set +a
fi
PY="${PY:-python3}"
echo "==> seed demo full tenant (slug=demo only)"
exec "$PY" scripts/seed_demo_full_tenant.py "$@"
