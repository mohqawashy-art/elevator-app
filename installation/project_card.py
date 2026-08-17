"""ملخص كارت المشروع — قيمة / تكاليف / دفعات عميل."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import inspect, text

from installation.models import COST_CATEGORIES, InstallProject, InstallQuotation
from models import db


def ensure_project_card_schema() -> None:
    """إنشاء جداول الكارت وعمود قيمة العقد إن غابا."""
    from installation.models import InstallProjectCostItem, InstallProjectReceipt

    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    if 'installation_project_costs' not in tables:
        InstallProjectCostItem.__table__.create(bind=db.engine, checkfirst=True)
    if 'installation_project_receipts' not in tables:
        InstallProjectReceipt.__table__.create(bind=db.engine, checkfirst=True)
    if 'installation_projects' in tables:
        cols = {c['name'] for c in insp.get_columns('installation_projects')}
        if 'contract_value' not in cols:
            db.session.execute(text('ALTER TABLE installation_projects ADD COLUMN contract_value FLOAT'))
            db.session.commit()


def project_contract_value(project: InstallProject) -> float:
    if project.contract_value is not None and float(project.contract_value) > 0:
        return round(float(project.contract_value), 2)
    q = project.accepted_quotation
    if q and q.grand_total:
        return round(float(q.grand_total), 2)
    latest = project.quotations.order_by(InstallQuotation.created_at.desc()).first()
    if latest and latest.grand_total:
        return round(float(latest.grand_total), 2)
    return 0.0


def build_project_card(project: InstallProject) -> dict:
    value = project_contract_value(project)

    receipts = list(project.receipts or [])
    received = round(sum(
        float(r.amount or 0)
        for r in receipts
        if (r.status or 'مستلمة') == 'مستلمة'
    ), 2)
    pending_receipts = round(sum(
        float(r.amount or 0)
        for r in receipts
        if (r.status or '') == 'معلقة'
    ), 2)
    client_remaining = round(max(value - received, 0), 2)

    costs = list(project.cost_items or [])
    total_cost = round(sum(float(c.amount or 0) for c in costs), 2)
    by_cat: dict[str, list] = defaultdict(list)
    cat_totals: dict[str, float] = defaultdict(float)
    for c in costs:
        cat = (c.category or 'أخرى').strip() or 'أخرى'
        by_cat[cat].append(c)
        cat_totals[cat] = round(cat_totals[cat] + float(c.amount or 0), 2)

    ordered_cats = []
    for cat in COST_CATEGORIES:
        if cat in by_cat:
            ordered_cats.append(cat)
    for cat in by_cat:
        if cat not in ordered_cats:
            ordered_cats.append(cat)

    groups = [
        {
            'category': cat,
            'total': cat_totals[cat],
            'lines': by_cat[cat],
        }
        for cat in ordered_cats
    ]

    profit = round(value - total_cost, 2)
    return {
        'contract_value': value,
        'received': received,
        'pending_receipts': pending_receipts,
        'client_remaining': client_remaining,
        'total_cost': total_cost,
        'profit': profit,
        'receipts': receipts,
        'cost_groups': groups,
        'cost_count': len(costs),
        'quote_code': project.accepted_quotation.code if project.accepted_quotation else None,
        'value_source': (
            'يدوي' if project.contract_value is not None and float(project.contract_value or 0) > 0
            else ('عرض معتمد' if project.accepted_quotation_id else 'عرض محفوظ')
        ),
    }
