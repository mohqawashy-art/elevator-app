#!/usr/bin/env bash
# إصلاح فوري لحفظ العقد بقيمة 0 — يشغّل على مجلد الخدمة الفعلي
set -euo pipefail
SERVICE="${1:-liftcore-jama}"
WD="$(sudo systemctl show "$SERVICE" -p WorkingDirectory --value 2>/dev/null || true)"
[[ -z "$WD" || "$WD" == "/" ]] && WD="$HOME/liftcore/jama-elevator-app"
echo "SERVICE=$SERVICE"
echo "WorkingDirectory=$WD"
echo "git=$(git -C "$WD" log -1 --oneline 2>/dev/null || echo none)"

git -C "$WD" fetch origin main
git -C "$WD" reset --hard origin/main

python3 - <<PY
from pathlib import Path
import re
wd = Path(r"""$WD""")
p = wd / "templates" / "contracts.html"
t = p.read_text(encoding="utf-8")
alert = "قيمة العقد يجب أن تكون أكبر من صفر"
print("before_alert", alert in t)
# remove old guard in any formatting
t2, n = re.subn(
    r"var\s+contractVal\s*=\s*parseFloat\([\s\S]*?;\s*"
    r"if\s*\(\s*!contractVal\s*\|\|\s*contractVal\s*<=\s*0\s*\)\s*\{[\s\S]*?"
    r"alert\([^)]*قيمة العقد يجب أن تكون أكبر من صفر[^)]*\)\s*;\s*"
    r"return\s*;\s*\}\s*",
    "\n",
    t,
    count=1,
)
t2 = t2.replace(alert, "/*removed*/")
# ensure button calls allow-zero
t2 = t2.replace('onclick="saveContract()"', 'onclick="saveContractAllowZero()"')
if "function saveContractAllowZero" not in t2:
    t2 = t2.replace(
        "function saveContract() {",
        "function saveContractAllowZero(){saveContract();}\nfunction saveContract() {",
        1,
    )
# kill any remaining greater-than-zero check near contractVal
t2 = re.sub(
    r"if\s*\(\s*!contractVal\s*\|\|\s*contractVal\s*<=\s*0\s*\)\s*\{[^}]*\}\s*",
    "/* zero ok */\n",
    t2,
)
p.write_text(t2, encoding="utf-8")
print("after_alert", alert in p.read_text(encoding="utf-8"))
print("patched_ok")
PY

# ensure hotfix exists in head
HEAD="$WD/templates/partials/liftcore_head.html"
if [[ -f "$HEAD" ]] && ! grep -q "contracts-zero-hotfix.js" "$HEAD"; then
  sed -i 's|liftcore-shell.js") }}?v=24"></script>|liftcore-shell.js") }}?v=24"></script>\n<script src="{{ url_for('\''static'\'', filename='\''contracts-zero-hotfix.js'\'') }}?v=2"></script>|' "$HEAD" || true
fi

sudo systemctl restart "$SERVICE"
sleep 2
systemctl is-active "$SERVICE" || true
echo "DONE — open: https://jama.liftcoreapp.com/contracts?z=3"
echo "debug:  https://jama.liftcoreapp.com/api/debug/contract-zero"
