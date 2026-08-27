"""إنشاء جداول طلبات عروض أسعار الموردين إن غابت (Postgres/SQLite)."""
from sqlalchemy import inspect

from models import SupplierQuoteRequest, SupplierQuoteRequestLine, db


def ensure_supplier_rfq_schema() -> None:
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())
    if 'supplier_quote_requests' not in tables:
        SupplierQuoteRequest.__table__.create(bind=db.engine, checkfirst=True)
    if 'supplier_quote_request_lines' not in tables:
        SupplierQuoteRequestLine.__table__.create(bind=db.engine, checkfirst=True)
