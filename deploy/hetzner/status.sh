#!/usr/bin/env bash
# فحص سريع للسيرفر الجديد
set -euo pipefail
PUBLIC_IP="$(curl -fsSL https://ifconfig.me/ip || hostname -I | awk '{print $1}')"
echo "IP: $PUBLIC_IP"
echo "timezone: $(timedatectl show -p Timezone --value 2>/dev/null || true)"
echo
systemctl is-active liftcore && echo "liftcore: active" || echo "liftcore: DOWN"
systemctl is-active nginx && echo "nginx: active" || echo "nginx: DOWN"
systemctl is-active postgresql && echo "postgres: active" || echo "postgres: DOWN"
echo
echo "local health: $(curl -fsS http://127.0.0.1/api/health || echo FAIL)"
echo "public health: $(curl -fsS --max-time 8 "http://${PUBLIC_IP}/api/health" || echo FAIL)"
echo
df -h / | tail -1
free -h | head -2
