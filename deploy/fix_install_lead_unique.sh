#!/usr/bin/env bash
# إصلاح فوري: UNIQUE(code) العالمي يمنع فرص التركيب بين المستأجرين
#   cd ~/liftcore/elevator-app && bash deploy/fix_install_lead_unique.sh
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
cd "$APP_DIR"

echo "==> قبل: $(git log -1 --oneline 2>/dev/null || echo no-git)"
git fetch origin main
git pull --ff-only origin main || git reset --hard origin/main
echo "==> بعد: $(git log -1 --oneline)"

if [ -f /etc/liftcore/platform.env ]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/liftcore/platform.env
  set +a
fi

echo "==> إسقاط UNIQUE(code) العالمي على جداول التركيب"
sudo -u postgres psql -d liftcore -v ON_ERROR_STOP=1 <<'SQL'
-- leads
ALTER TABLE installation_leads DROP CONSTRAINT IF EXISTS installation_leads_code_key;
DROP INDEX IF EXISTS installation_leads_code_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_install_lead_org_code
  ON installation_leads (organization_id, code);

-- projects
ALTER TABLE installation_projects DROP CONSTRAINT IF EXISTS installation_projects_code_key;
DROP INDEX IF EXISTS installation_projects_code_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_install_project_org_code
  ON installation_projects (organization_id, code);

-- quotations
ALTER TABLE installation_quotations DROP CONSTRAINT IF EXISTS installation_quotations_code_key;
DROP INDEX IF EXISTS installation_quotations_code_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_install_quote_org_code
  ON installation_quotations (organization_id, code);

SELECT 'leads' AS t, indexname, indexdef FROM pg_indexes
 WHERE tablename = 'installation_leads' AND indexdef ILIKE '%UNIQUE%'
UNION ALL
SELECT 'projects', indexname, indexdef FROM pg_indexes
 WHERE tablename = 'installation_projects' AND indexdef ILIKE '%UNIQUE%'
UNION ALL
SELECT 'quotes', indexname, indexdef FROM pg_indexes
 WHERE tablename = 'installation_quotations' AND indexdef ILIKE '%UNIQUE%';
SQL

echo "==> إعادة تشغيل liftcore"
sudo systemctl daemon-reload
sudo systemctl restart liftcore
sleep 2
sudo systemctl is-active liftcore
curl -sS http://127.0.0.1:5000/api/version || true
echo ""
echo "==> تم. جرّب حفظ فرصة بيع من جما الآن."
