#!/bin/bash
# LiftCore — تطبيق التحديث من ملف zip
# الاستخدام:
#   bash deploy/apply_update_zip.sh ~/liftcore-update.zip
#   bash deploy/apply_update_zip.sh ~/liftcore-update.zip ~/liftcore/jama-elevator-app liftcore-jama
set -euo pipefail

ZIP="${1:-$HOME/liftcore-update.zip}"
APP="${2:-$HOME/liftcore/elevator-app}"
SERVICE="${3:-liftcore}"
BACKUP="$HOME/backups/pre-update-$(basename "$APP")-$(date +%Y%m%d-%H%M%S)"

if [[ ! -f "$ZIP" ]]; then
  echo "Missing: $ZIP"
  echo "Upload deploy/liftcore-update.zip to /home/info/ first."
  exit 1
fi

echo "=== LiftCore ZIP update ==="
echo "ZIP: $ZIP"
echo "APP: $APP"
echo "SERVICE: $SERVICE"

echo ""
echo "Backup key files -> $BACKUP"
mkdir -p "$BACKUP"
for f in app.py models.py operations.py fault_report.py form_validation.py inventory_stock.py customer_billing.py requirements.txt; do
  [[ -f "$APP/$f" ]] && cp -a "$APP/$f" "$BACKUP/" || true
done

echo ""
echo "Extract into $APP"
if command -v python3 >/dev/null 2>&1; then
  python3 - "$ZIP" "$APP" <<'PY'
import os, sys, zipfile
zip_path, app_dir = sys.argv[1], sys.argv[2]
os.makedirs(app_dir, exist_ok=True)
with zipfile.ZipFile(zip_path) as zf:
    for info in zf.infolist():
        name = info.filename.replace("\\", "/").lstrip("/")
        if not name or name.endswith("/"):
            continue
        target = os.path.join(app_dir, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as dst:
            dst.write(src.read())
print("  extracted via python3 (Unix paths)")
PY
else
  unzip -o "$ZIP" -d "$APP"
fi

chmod +x "$APP/deploy/apply_update_zip.sh" 2>/dev/null || true

mkdir -p \
  "$APP/static/uploads/company" \
  "$APP/static/uploads/users" \
  "$APP/static/uploads/clients" \
  "$APP/static/uploads/technicians" \
  "$APP/static/uploads/visits"

echo ""
echo "Install Python dependencies"
cd "$APP"
if [[ -f "$HOME/liftcore/venv/bin/pip" ]]; then
  "$HOME/liftcore/venv/bin/pip" install -q -r requirements.txt
elif [[ -f .venv/bin/pip ]]; then
  .venv/bin/pip install -q -r requirements.txt
else
  pip3 install -q -r requirements.txt
fi

if [[ -f "$APP/deploy/migrate_db.py" ]]; then
  echo ""
  echo "Database migrate"
  for db in "$APP/instance/"*.db "$APP/"*.db; do
    [[ -f "$db" ]] || continue
    python3 "$APP/deploy/migrate_db.py" "$db" || true
  done
fi

echo ""
echo "Restart $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 2
sudo systemctl is-active "$SERVICE"

echo ""
echo "Verify"
test -f "$APP/form_validation.py" && echo "  form_validation.py OK"
test -f "$APP/inventory_stock.py" && echo "  inventory_stock.py OK"
test -f "$APP/templates/partials/flash_messages.html" && echo "  flash_messages.html OK"
test -f "$APP/static/liftcore-shell.js" && echo "  liftcore-shell.js OK"
test -f "$APP/templates/faults.html" && echo "  faults.html OK"
grep -q "sync_entity_parts_stock" "$APP/operations.py" 2>/dev/null && echo "  inventory stock sync OK" || true

echo ""
echo "Done — service $SERVICE updated"
echo "Backup: $BACKUP"
