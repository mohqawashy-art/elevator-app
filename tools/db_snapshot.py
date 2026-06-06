"""
LiftCore — تصدير واستعادة قاعدة البيانات كاملة

الاستخدام:
    python tools/db_snapshot.py export
        → يُنشئ data/liftcore_snapshot.json من القاعدة الحالية

    python tools/db_snapshot.py restore
        → يستبدل البيانات التشغيلية من data/liftcore_snapshot.json

    python tools/db_snapshot.py restore --keep-users
        → يستعيد البيانات دون مسح المستخدمين/الإعدادات الحالية
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / 'data' / 'liftcore_snapshot.json'

# ترتيب الإدراج حسب علاقات المفاتيح الأجنبية
TABLE_SPECS = [
    ('users', 'User'),
    ('settings', 'Settings'),
    ('customers', 'Customer'),
    ('technicians', 'Technician'),
    ('technician_documents', 'TechnicianDocument'),
    ('inventory_items', 'InventoryItem'),
    ('elevators', 'Elevator'),
    ('contracts', 'Contract'),
    ('contract_elevators', 'ContractElevator'),
    ('maintenance_visits', 'MaintenanceVisit'),
    ('faults', 'Fault'),
    ('revenues', 'Revenue'),
    ('expenses', 'Expense'),
    ('invoices', 'Invoice'),
    ('stock_movements', 'StockMovement'),
    ('parts_billing', 'PartsBilling'),
]

CLEAR_ORDER = [spec[1] for spec in reversed(TABLE_SPECS)]


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    return value


def _deserialize(value, column_type):
    if value is None:
        return None
    if column_type in ('DATE', 'Date'):
        return date.fromisoformat(value[:10])
    if column_type in ('DATETIME', 'DateTime'):
        if 'T' in value:
            return datetime.fromisoformat(value.replace('Z', ''))
        return datetime.fromisoformat(value + 'T00:00:00')
    return value


def _model_map():
    from models import (
        Contract, ContractElevator, Customer, Elevator, Expense, Fault,
        InventoryItem, Invoice, MaintenanceVisit, PartsBilling, Revenue,
        Settings, StockMovement, Technician, TechnicianDocument, User,
    )
    return {
        'User': User,
        'Settings': Settings,
        'Customer': Customer,
        'Technician': Technician,
        'TechnicianDocument': TechnicianDocument,
        'InventoryItem': InventoryItem,
        'Elevator': Elevator,
        'Contract': Contract,
        'ContractElevator': ContractElevator,
        'MaintenanceVisit': MaintenanceVisit,
        'Fault': Fault,
        'Revenue': Revenue,
        'Expense': Expense,
        'Invoice': Invoice,
        'StockMovement': StockMovement,
        'PartsBilling': PartsBilling,
    }


def _row_to_dict(row):
    data = {}
    for col in row.__table__.columns:
        data[col.name] = _serialize(getattr(row, col.name))
    return data


def export_snapshot(out_path: Path) -> dict:
    from app import app, db

    models = _model_map()
    payload = {
        'version': 1,
        'exported_at': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'tables': {},
        'counts': {},
    }

    with app.app_context():
        db.create_all()
        for table_name, model_name in TABLE_SPECS:
            model = models[model_name]
            rows = model.query.order_by(model.id).all()
            payload['tables'][table_name] = [_row_to_dict(r) for r in rows]
            payload['counts'][table_name] = len(rows)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def _column_types(model):
    types = {}
    for col in model.__table__.columns:
        types[col.name] = type(col.type).__name__
    return types


def restore_snapshot(
    in_path: Path,
    *,
    keep_users: bool = False,
    keep_settings: bool = False,
) -> dict:
    from app import app, db

    if not in_path.is_file():
        raise FileNotFoundError(f'Snapshot not found: {in_path}')

    payload = json.loads(in_path.read_text(encoding='utf-8'))
    models = _model_map()
    imported = {}

    with app.app_context():
        db.create_all()

        skip_on_clear = set()
        if keep_users:
            skip_on_clear.add('User')
        if keep_settings:
            skip_on_clear.add('Settings')

        for model_name in CLEAR_ORDER:
            if model_name in skip_on_clear:
                continue
            models[model_name].query.delete()
        db.session.commit()

        for table_name, model_name in TABLE_SPECS:
            if keep_users and model_name == 'User':
                continue
            if keep_settings and model_name == 'Settings':
                continue

            model = models[model_name]
            col_types = _column_types(model)
            rows = payload.get('tables', {}).get(table_name, [])
            for raw in rows:
                values = {}
                for key, val in raw.items():
                    if key in col_types:
                        values[key] = _deserialize(val, col_types[key])
                db.session.add(model(**values))
            db.session.flush()
            imported[table_name] = len(rows)

        db.session.commit()
        _fix_sqlite_sequences(db)

    return imported


def _fix_sqlite_sequences(db):
    from sqlalchemy import inspect, text

    bind = db.session.get_bind()
    if bind.dialect.name != 'sqlite':
        return
    insp = inspect(bind)
    for table_name in insp.get_table_names():
        try:
            result = db.session.execute(text(f'SELECT MAX(id) FROM {table_name}')).scalar()
        except Exception:
            continue
        if result is None:
            continue
        db.session.execute(
            text(
                "INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES (:name, :seq)"
            ),
            {'name': table_name, 'seq': int(result)},
        )
    db.session.commit()


def _print_counts(label: str, counts: dict):
    print(label)
    for table_name, n in counts.items():
        if n:
            print(f'  {table_name}: {n}')


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('export', 'restore'):
        print(__doc__)
        sys.exit(1)

    cmd = args[0]
    out_path = DEFAULT_OUT
    keep_users = '--keep-users' in args
    keep_settings = '--keep-settings' in args

    for i, arg in enumerate(args):
        if arg == '--out' and i + 1 < len(args):
            out_path = Path(args[i + 1])
        if arg == '--from' and i + 1 < len(args):
            out_path = Path(args[i + 1])

    if cmd == 'export':
        payload = export_snapshot(out_path)
        _print_counts(f'Exported → {out_path}', payload['counts'])
        print(f'\nTo restore at home:\n  python tools/db_snapshot.py restore')
        return

    imported = restore_snapshot(
        out_path,
        keep_users=keep_users,
        keep_settings=keep_settings,
    )
    _print_counts(f'Restored from {out_path}', imported)
    print('\nDone. Restart the app if it is running.')


if __name__ == '__main__':
    main()
