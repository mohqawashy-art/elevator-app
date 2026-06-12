"""
إنشاء جداول موديول التركيب فقط (لا يمس بيانات LiftCore الحالية).
شغّل: python scripts/init_install_module.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from app import app, db
import installation.models  # noqa: F401

_INSTALL_MIGRATIONS = {
    'installation_quotations': [
        ('customer_id', 'INTEGER'),
        ('approved_at', 'DATETIME'),
        ('pay_advance_pct', 'FLOAT'),
        ('pay_supply_pct', 'FLOAT'),
        ('pay_final_pct', 'FLOAT'),
    ],
    'installation_projects': [
        ('accepted_quotation_id', 'INTEGER'),
        ('execution_started_at', 'DATETIME'),
    ],
    'installation_leads': [
        ('customer_id', 'INTEGER'),
    ],
    'installation_timeline_steps': [
        ('started_at', 'DATETIME'),
    ],
}


def _migrate_install_columns():
    insp = inspect(db.engine)
    for table, cols in _INSTALL_MIGRATIONS.items():
        if table not in insp.get_table_names():
            continue
        existing = {c['name'] for c in insp.get_columns(table)}
        for col_name, col_type in cols:
            if col_name in existing:
                continue
            db.session.execute(text(
                f'ALTER TABLE {table} ADD COLUMN {col_name} {col_type}'
            ))
            db.session.commit()
            print(f'[+] {table}.{col_name}')


with app.app_context():
    db.create_all()
    _migrate_install_columns()
    print('[OK] installation tables ready (leads, projects, quotations, timeline)')
