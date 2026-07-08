"""ترقية SQLite legacy — organization_id على جداول النواة + التركيب."""
from __future__ import annotations

from sqlalchemy import inspect, text

DEFAULT_ORG_SLUG = 'default'
DEFAULT_ORG_NAME = 'LiftCore Default'

TENANT_TABLES: tuple[str, ...] = (
    'customers',
    'elevators',
    'contracts',
    'contract_elevators',
    'technicians',
    'technician_documents',
    'maintenance_teams',
    'maintenance_visits',
    'visit_technicians',
    'faults',
    'fault_technicians',
    'revenues',
    'expenses',
    'invoices',
    'inventory_items',
    'stock_movements',
    'parts_billing',
    'purchase_orders',
    'purchase_order_lines',
    'elevator_estimates',
    'elevator_estimate_lines',
    'signatories',
    'settings',
    'users',
    'audit_logs',
    'installation_leads',
    'installation_projects',
    'installation_quotations',
    'installation_quotation_lines',
    'installation_timeline_steps',
)


def ensure_default_organization(db_session):
    from models import Organization

    org = Organization.query.filter_by(slug=DEFAULT_ORG_SLUG).first()
    if org:
        return org
    org = Organization(
        slug=DEFAULT_ORG_SLUG,
        name=DEFAULT_ORG_NAME,
        status='active',
    )
    db_session.add(org)
    db_session.commit()
    return org


def _drop_app_live_state_org_column(db_session, engine) -> None:
    """app_live_state جدول منصة — أزل organization_id إن أُضيف بالخطأ."""
    insp = inspect(engine)
    if 'app_live_state' not in insp.get_table_names():
        return
    cols = {c['name'] for c in insp.get_columns('app_live_state')}
    if 'organization_id' not in cols:
        return
    try:
        db_session.execute(text('ALTER TABLE app_live_state DROP COLUMN organization_id'))
        db_session.commit()
        return
    except Exception:
        db_session.rollback()
    db_session.execute(text(
        'CREATE TABLE IF NOT EXISTS app_live_state_new ('
        'id INTEGER NOT NULL PRIMARY KEY, revision INTEGER NOT NULL)'
    ))
    db_session.execute(text(
        'INSERT INTO app_live_state_new (id, revision) '
        'SELECT id, revision FROM app_live_state'
    ))
    db_session.execute(text('DROP TABLE app_live_state'))
    db_session.execute(text('ALTER TABLE app_live_state_new RENAME TO app_live_state'))
    db_session.commit()


def ensure_multitenant_schema(db_session, engine) -> bool:
    """أعمدة organization_id + backfill للقواعد القديمة (SQLite)."""
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if 'organizations' not in tables:
        return False

    changed = False
    org = ensure_default_organization(db_session)
    oid = org.id

    for table in TENANT_TABLES:
        if table not in tables:
            continue
        existing = {c['name'] for c in insp.get_columns(table)}
        if 'organization_id' not in existing:
            db_session.execute(text(
                f'ALTER TABLE {table} ADD COLUMN organization_id INTEGER'
            ))
            changed = True
        db_session.execute(
            text(f'UPDATE {table} SET organization_id = :oid '
                 f'WHERE organization_id IS NULL'),
            {'oid': oid},
        )
    db_session.commit()
    _drop_app_live_state_org_column(db_session, engine)
    _seed_zatca_from_settings(db_session, engine)
    return changed


def _seed_zatca_from_settings(db_session, engine) -> None:
    """ترحيل الرقم الضريبي من settings إلى zatca_credentials."""
    insp = inspect(engine)
    if 'zatca_credentials' not in insp.get_table_names():
        return
    if 'settings' not in insp.get_table_names():
        return
    db_session.execute(text(
        'INSERT INTO zatca_credentials (organization_id, vat_number, cr_number, status, environment) '
        'SELECT s.organization_id, TRIM(s.vat_number), TRIM(s.cr_number), '
        "'active', 'sandbox' "
        'FROM settings s '
        'WHERE s.vat_number IS NOT NULL AND TRIM(s.vat_number) != \'\' '
        'AND NOT EXISTS ('
        '  SELECT 1 FROM zatca_credentials z WHERE z.organization_id = s.organization_id'
        ')'
    ))
    db_session.commit()
