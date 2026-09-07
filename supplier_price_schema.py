"""جداول الموردين وقوائم الأسعار + أعمدة الربط على RFQ/PO."""
from sqlalchemy import inspect, text

from models import (
    PurchaseOrder,
    Supplier,
    SupplierPrice,
    SupplierQuoteRequest,
    SupplierQuoteRequestLine,
    db,
)


def _add_column_if_missing(table: str, column: str, col_type: str) -> None:
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    if table not in set(insp.get_table_names()):
        return
    cols = {c['name'] for c in insp.get_columns(table)}
    if column in cols:
        return
    db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
    db.session.commit()


def ensure_supplier_price_schema() -> None:
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())
    if 'suppliers' not in tables:
        Supplier.__table__.create(bind=db.engine, checkfirst=True)
    if 'supplier_prices' not in tables:
        SupplierPrice.__table__.create(bind=db.engine, checkfirst=True)

    dialect = (db.engine.dialect.name or '').lower()
    int_type = 'INTEGER' if dialect != 'postgresql' else 'INTEGER'
    float_type = 'FLOAT' if dialect != 'postgresql' else 'DOUBLE PRECISION'

    _add_column_if_missing('supplier_quote_requests', 'supplier_id', int_type)
    _add_column_if_missing('supplier_quote_request_lines', 'quoted_unit_price', float_type)
    _add_column_if_missing('purchase_orders', 'supplier_id', int_type)
    _add_column_if_missing('purchase_orders', 'rfq_id', int_type)


if __name__ == '__main__':
    from app import app

    with app.app_context():
        ensure_supplier_price_schema()
        print('supplier price schema OK')
