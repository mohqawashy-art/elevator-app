#!/usr/bin/env bash
# تشخيص فشل إضافة فرصة تركيب — شغّل من GCP SSH:
#   cd ~/liftcore/elevator-app && bash deploy/diagnose_install_lead.sh
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/liftcore/elevator-app}"
cd "$APP_DIR"

echo "==> git: $(git log -1 --oneline)"
echo "==> service WorkingDirectory: $(sudo systemctl show liftcore -p WorkingDirectory --value)"
echo "==> api/version:"
curl -sS http://127.0.0.1:5000/api/version || true
echo ""

if [ -f /etc/liftcore/platform.env ]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/liftcore/platform.env
  set +a
fi

PY="${APP_DIR}/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="${HOME}/liftcore/jama-elevator-app/.venv/bin/python"
fi

echo "==> محاكاة إضافة فرصة (مستأجر jama إن وُجد)"
"$PY" - <<'PY'
import traceback
from app import app, db
from models import Organization, Customer
from installation.models import InstallLead, InstallProject
from installation.project_card import ensure_project_card_schema
from sqlalchemy import text, inspect

with app.app_context():
    try:
        ensure_project_card_schema()
        print('ensure_project_card_schema: OK')
    except Exception as e:
        print('ensure_project_card_schema FAIL:', e)
        traceback.print_exc()
        db.session.rollback()

    insp = inspect(db.engine)
    for t in ('installation_leads', 'installation_projects', 'installation_project_costs', 'installation_project_receipts'):
        if t not in insp.get_table_names():
            print(f'TABLE MISSING: {t}')
            continue
        cols = {c['name'] for c in insp.get_columns(t)}
        print(f'{t}: {len(cols)} cols; contract_value={("contract_value" in cols)} org={("organization_id" in cols)}')

    org = Organization.query.filter_by(slug='jama').first() or Organization.query.order_by(Organization.id).first()
    print('org:', org.id if org else None, getattr(org, 'slug', None))
    if not org:
        raise SystemExit(1)

    cust = Customer.query.filter_by(organization_id=org.id).filter(Customer.status != 'غير نشط').first()
    print('customer:', cust.id if cust else None, getattr(cust, 'code', None))
    if not cust:
        raise SystemExit('no customer')

    # duplicate projects per lead?
    dups = db.session.execute(text('''
        SELECT lead_id, COUNT(*) AS c
        FROM installation_projects
        WHERE lead_id IS NOT NULL AND organization_id = :oid
        GROUP BY lead_id HAVING COUNT(*) > 1
        ORDER BY c DESC LIMIT 10
    '''), {'oid': org.id}).fetchall()
    print('duplicate lead_id projects:', dups or 'none')

    try:
        from flask import g
        g.organization_id = org.id
        code = f'DIAG-{org.id}'
        existing = InstallLead.query.filter_by(organization_id=org.id, code=code).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
        lead = InstallLead(
            organization_id=org.id,
            code=code,
            client_name=cust.name,
            customer_id=cust.id,
            phone=cust.phone or '',
            email=(cust.email or '')[:120],
            city=(cust.city or '')[:100],
            district=(cust.district or '')[:100],
            status='جديد',
        )
        db.session.add(lead)
        db.session.commit()
        print('INSERT OK id=', lead.id)
        # cleanup
        db.session.delete(lead)
        db.session.commit()
        print('CLEANUP OK')
    except Exception as e:
        db.session.rollback()
        print('INSERT FAIL:', type(e).__name__, e)
        traceback.print_exc()

print('==> last liftcore errors:')
PY

sudo journalctl -u liftcore -n 40 --no-pager | tail -n 40
