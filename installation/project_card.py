"""ملخص كارت المشروع — قيمة / تكاليف / دفعات عميل (نمط جدول Excel)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import inspect, text

from installation.models import (
    COST_CATEGORIES,
    COST_PAYMENT_STATUSES,
    COST_PHASE_LABELS,
    InstallProject,
    InstallQuotation,
    normalize_cost_category,
)
from models import db
from tenant_scope import tenant_query

_cost_phases_migrated = False

_AR_ORDINAL = {
    1: 'أولى',
    2: 'ثانية',
    3: 'ثالثة',
    4: 'رابعة',
    5: 'خامسة',
    6: 'سادسة',
    7: 'سابعة',
    8: 'ثامنة',
    9: 'تاسعة',
    10: 'عاشرة',
}


def parse_cost_item_form(form) -> tuple[dict | None, str | None]:
    """تحليل نموذج إضافة/تعديل بند تكلفة — (حقول، رسالة خطأ)."""
    title = (form.get('title') or '').strip()
    category = (form.get('category') or COST_CATEGORIES[0]).strip()
    if category not in COST_CATEGORIES:
        category = normalize_cost_category(category)
    try:
        amount = float(form.get('amount') or 0)
    except ValueError:
        amount = 0
    date_raw = (form.get('cost_date') or '').strip()
    try:
        cost_date = datetime.strptime(date_raw, '%Y-%m-%d').date() if date_raw else date.today()
    except ValueError:
        cost_date = date.today()
    inst_raw = (form.get('installment_no') or '').strip()
    installment_no = int(inst_raw) if inst_raw.isdigit() else None
    pay_status = (form.get('payment_status') or '').strip()
    if pay_status and pay_status not in COST_PAYMENT_STATUSES:
        pay_status = None
    if not pay_status and installment_no:
        pay_status = 'غير مدفوعة'
    if not title:
        if installment_no:
            title = installment_label(installment_no)
        else:
            title = category
    if amount <= 0:
        return None, 'أدخل مبلغاً أكبر من صفر'
    return {
        'title': title,
        'category': category,
        'amount': amount,
        'cost_date': cost_date,
        'installment_no': installment_no,
        'payment_status': pay_status,
        'notes': (form.get('notes') or '').strip() or None,
    }, None


def installment_label(n: int | None, title: str | None = None) -> str:
    if title and title.strip():
        return title.strip()
    if not n:
        return 'دفعة'
    ord_ar = _AR_ORDINAL.get(int(n), str(n))
    return f'دفعة {ord_ar}'


def ensure_project_card_schema() -> None:
    """إنشاء جداول الكارت وعمود قيمة العقد وحالة السداد إن غابا."""
    from installation.models import InstallProjectCostItem, InstallProjectReceipt

    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())
    if 'installation_project_costs' not in tables:
        InstallProjectCostItem.__table__.create(bind=db.engine, checkfirst=True)
    if 'installation_project_receipts' not in tables:
        InstallProjectReceipt.__table__.create(bind=db.engine, checkfirst=True)

    dialect = (db.engine.dialect.name or '').lower()

    if 'installation_projects' in tables:
        cols = {c['name'] for c in insp.get_columns('installation_projects')}
        if 'contract_value' not in cols:
            if dialect == 'postgresql':
                sql = (
                    'ALTER TABLE installation_projects '
                    'ADD COLUMN IF NOT EXISTS contract_value DOUBLE PRECISION'
                )
            else:
                sql = 'ALTER TABLE installation_projects ADD COLUMN contract_value FLOAT'
            db.session.execute(text(sql))
            db.session.commit()
        if 'contract_id' not in cols:
            if dialect == 'postgresql':
                sql = (
                    'ALTER TABLE installation_projects '
                    'ADD COLUMN IF NOT EXISTS contract_id INTEGER'
                )
            else:
                sql = 'ALTER TABLE installation_projects ADD COLUMN contract_id INTEGER'
            db.session.execute(text(sql))
            db.session.commit()
            try:
                # فهرس فقط — FK اختياري لتفادي فشل على قواعد قديمة
                db.session.execute(text(
                    'CREATE INDEX IF NOT EXISTS ix_installation_projects_contract_id '
                    'ON installation_projects (contract_id)'
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()

    if 'installation_project_costs' in set(inspect(db.engine).get_table_names()):
        try:
            insp.clear_cache()
        except Exception:
            pass
        cost_cols = {c['name'] for c in inspect(db.engine).get_columns('installation_project_costs')}
        if 'payment_status' not in cost_cols:
            if dialect == 'postgresql':
                sql = (
                    'ALTER TABLE installation_project_costs '
                    'ADD COLUMN IF NOT EXISTS payment_status VARCHAR(30)'
                )
            else:
                sql = 'ALTER TABLE installation_project_costs ADD COLUMN payment_status VARCHAR(30)'
            db.session.execute(text(sql))
            db.session.commit()

    global _cost_phases_migrated
    if not _cost_phases_migrated:
        _migrate_legacy_cost_categories()
        _cost_phases_migrated = True


def _migrate_legacy_cost_categories() -> None:
    """ترقية بنود الكارت القديمة إلى مراحل التركيب الثلاث."""
    from installation.models import InstallProjectCostItem

    try:
        items = InstallProjectCostItem.query.execution_options(skip_tenant=True).all()
    except Exception:
        db.session.rollback()
        return
    changed = False
    for item in items:
        norm = normalize_cost_category(item.category, item.installment_no)
        if (item.category or '').strip() != norm:
            item.category = norm
            changed = True
    if changed:
        db.session.commit()


def cost_phase_label(category: str) -> str:
    cat = (category or '').strip()
    return COST_PHASE_LABELS.get(cat, cat or '—')


def delete_install_project(project: InstallProject) -> str:
    """حذف مشروع تركيب (عروضه، كارت المشروع، جدول التنفيذ). يُرجع كود المشروع."""
    from models import ElevatorEstimate

    code = project.code or ''
    lead = project.lead
    if lead and lead.status == 'تم تحويله لمشروع':
        lead.status = 'جاري التواصل'

    for est in tenant_query(ElevatorEstimate).filter_by(result_project_id=project.id).all():
        est.result_project_id = None
        est.result_quotation_id = None

    project.accepted_quotation_id = None
    project.contract_id = None
    project.lead_id = None
    db.session.flush()
    db.session.delete(project)
    return code


def project_contract_value(project: InstallProject) -> float:
    if project.contract_value is not None and float(project.contract_value) > 0:
        return round(float(project.contract_value), 2)
    linked = getattr(project, 'contract', None)
    if linked:
        for attr in ('total', 'value'):
            raw = getattr(linked, attr, None)
            if raw is not None and float(raw) > 0:
                return round(float(raw), 2)
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
        cat = normalize_cost_category(c.category, c.installment_no)
        by_cat[cat].append(c)
        cat_totals[cat] = round(cat_totals[cat] + float(c.amount or 0), 2)

    ordered_cats = []
    for cat in COST_CATEGORIES:
        if cat in by_cat:
            ordered_cats.append(cat)
    for cat in by_cat:
        if cat not in ordered_cats:
            ordered_cats.append(cat)

    sheet_rows = []
    # صف قيمة المشروع
    sheet_rows.append({
        'kind': 'value',
        'label': 'قيمة المشروع',
        'amount': value,
        'status': None,
        'note': None,
        'item': None,
        'category': None,
    })
    # عنوان قسم التكاليف
    sheet_rows.append({
        'kind': 'section',
        'label': 'تكاليف المشروع',
        'amount': total_cost if total_cost else None,
        'status': None,
        'note': None,
        'item': None,
        'category': None,
    })

    groups = []
    for cat in ordered_cats:
        lines = sorted(
            by_cat[cat],
            key=lambda x: (
                x.installment_no is None,
                x.installment_no or 0,
                x.id or 0,
            ),
        )
        groups.append({
            'category': cat,
            'total': cat_totals[cat],
            'lines': lines,
        })
        phase_label = cost_phase_label(cat)
        sheet_rows.append({
            'kind': 'category',
            'label': phase_label,
            'amount': cat_totals[cat],
            'status': None,
            'note': None,
            'item': None,
            'category': cat,
        })
        detail_lines = [
            item for item in lines
            if item.installment_no
            or (item.title or '').strip() not in ('', cat, phase_label)
        ]
        if (
            len(lines) == 1
            and not lines[0].installment_no
            and (lines[0].title or '').strip() in ('', cat, phase_label)
        ):
            detail_lines = []
        for item in detail_lines:
            if item.installment_no:
                label = installment_label(item.installment_no, item.title)
            else:
                label = (item.title or phase_label).strip()
            status = (item.payment_status or '').strip() or None
            if item.installment_no:
                status = status or 'غير مدفوعة'
            sheet_rows.append({
                'kind': 'line',
                'label': label,
                'amount': float(item.amount or 0),
                'status': status,
                'note': None,
                'item': item,
                'category': cat,
            })

    if not ordered_cats:
        sheet_rows.append({
            'kind': 'empty',
            'label': 'لا بنود تكلفة بعد — أضف مصروفات لمراحل التركيب الثلاث',
            'amount': None,
            'status': None,
            'note': None,
            'item': None,
            'category': None,
        })

    # تحصيل العميل
    if receipts:
        sheet_rows.append({
            'kind': 'section',
            'label': 'تحصيل العميل',
            'amount': received,
            'status': None,
            'note': None,
            'item': None,
            'category': None,
        })
        for r in sorted(receipts, key=lambda x: (x.installment_no or 0, x.id or 0)):
            sheet_rows.append({
                'kind': 'receipt',
                'label': r.label or installment_label(r.installment_no),
                'amount': float(r.amount or 0),
                'status': 'مدفوعة' if (r.status or '') == 'مستلمة' else 'غير مدفوعة',
                'note': None,
                'item': r,
                'category': None,
            })

    profit = round(value - total_cost, 2)
    sheet_rows.append({
        'kind': 'profit',
        'label': 'الربح التقديري',
        'amount': profit,
        'status': None,
        'note': None,
        'item': None,
        'category': None,
    })

    linked_contract = getattr(project, 'contract', None)
    if project.contract_value is not None and float(project.contract_value or 0) > 0:
        value_source = 'يدوي'
    elif linked_contract:
        value_source = f'عقد {linked_contract.code}'
    elif project.accepted_quotation_id:
        value_source = 'عرض معتمد'
    else:
        value_source = 'عرض محفوظ'

    return {
        'contract_value': value,
        'received': received,
        'pending_receipts': pending_receipts,
        'client_remaining': client_remaining,
        'total_cost': total_cost,
        'profit': profit,
        'receipts': receipts,
        'cost_groups': groups,
        'sheet_rows': sheet_rows,
        'cost_count': len(costs),
        'quote_code': project.accepted_quotation.code if project.accepted_quotation else None,
        'contract': linked_contract,
        'contract_code': linked_contract.code if linked_contract else None,
        'value_source': value_source,
    }
