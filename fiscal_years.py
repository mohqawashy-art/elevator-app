"""تقفيل السنة المالية: إقفال الإيراد والمصروف في الأرباح المبقاة، ومنع تعديل الفترة المقفلة."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import inspect

from models import Account, FiscalYear, JournalEntry, JournalLine, db
from tenant_scope import assign_organization, effective_organization_id, tenant_query


class ClosedFiscalYearError(ValueError):
    """تاريخ داخل سنة مالية مقفلة."""


_schema_ready = False


def ensure_fiscal_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    insp = inspect(db.engine)
    if 'fiscal_years' not in set(insp.get_table_names()):
        FiscalYear.__table__.create(bind=db.engine, checkfirst=True)
        try:
            db.session.expire_all()
        except Exception:
            pass
    _schema_ready = True


def closed_period_for(day: date | None) -> FiscalYear | None:
    if not day:
        return None
    ensure_fiscal_schema()
    return (
        tenant_query(FiscalYear)
        .filter(
            FiscalYear.status == 'closed',
            FiscalYear.start_date <= day,
            FiscalYear.end_date >= day,
        )
        .order_by(FiscalYear.end_date.desc())
        .first()
    )


def assert_date_open(day: date | None) -> None:
    period = closed_period_for(day)
    if not period:
        return
    raise ClosedFiscalYearError(
        f'السنة المالية من {period.start_date} إلى {period.end_date} مقفلة. أعد فتحها قبل إضافة أو إلغاء قيد في هذه الفترة.'
    )


def last_closed_end(as_of: date | None = None) -> date | None:
    ensure_fiscal_schema()
    q = tenant_query(FiscalYear).filter(FiscalYear.status == 'closed')
    if as_of:
        q = q.filter(FiscalYear.end_date <= as_of)
    row = q.order_by(FiscalYear.end_date.desc()).first()
    return row.end_date if row else None


def list_fiscal_years() -> list[FiscalYear]:
    ensure_fiscal_schema()
    return (
        tenant_query(FiscalYear)
        .order_by(FiscalYear.end_date.desc(), FiscalYear.id.desc())
        .all()
    )


def _retained_earnings() -> Account | None:
    from chart_of_accounts import account_by_map_key

    acc = account_by_map_key('retained_earnings')
    if acc:
        return acc
    return tenant_query(Account).filter_by(code='3300', is_postable=True).first()


def preview_close(start: date, end: date) -> dict:
    """أرصدة الإيراد والمصروف داخل الفترة، بدون قيد الإقفال."""
    from accounting_journals import ensure_journal_schema, _round2

    ensure_journal_schema()
    if end < start:
        raise ValueError('تاريخ النهاية قبل تاريخ البداية')
    if end > date.today():
        raise ValueError('لا يُقفل تاريخ في المستقبل')

    oid = effective_organization_id()
    q = (
        db.session.query(
            Account.id,
            Account.code,
            Account.name,
            Account.account_type,
            db.func.coalesce(db.func.sum(JournalLine.debit), 0),
            db.func.coalesce(db.func.sum(JournalLine.credit), 0),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .filter(
            JournalEntry.status == 'posted',
            JournalEntry.source_type.is_distinct_from('year_close'),
            JournalEntry.entry_date >= start,
            JournalEntry.entry_date <= end,
            Account.account_type.in_(['revenue', 'expense']),
            Account.is_postable.is_(True),
        )
    )
    if oid:
        q = q.filter(Account.organization_id == oid, JournalEntry.organization_id == oid)
    q = q.group_by(Account.id, Account.code, Account.name, Account.account_type)
    q = q.order_by(Account.code.asc())

    lines = []
    revenue = expense = 0.0
    for acc_id, code, name, atype, debit, credit in q.all():
        if atype == 'revenue':
            net = _round2(credit - debit)
            revenue = _round2(revenue + net)
        else:
            net = _round2(debit - credit)
            expense = _round2(expense + net)
        if not net:
            continue
        lines.append({
            'account_id': acc_id,
            'code': code,
            'name': name,
            'account_type': atype,
            'amount': net,
        })
    return {
        'start': start,
        'end': end,
        'revenue': revenue,
        'expense': expense,
        'net': _round2(revenue - expense),
        'lines': lines,
    }


def _overlap(start: date, end: date, ignore_id: int | None = None) -> FiscalYear | None:
    q = tenant_query(FiscalYear).filter(
        FiscalYear.start_date <= end,
        FiscalYear.end_date >= start,
    )
    if ignore_id:
        q = q.filter(FiscalYear.id != ignore_id)
    return q.first()


def close_fiscal_year(start: date, end: date) -> FiscalYear:
    from accounting_journals import _create_entry, _round2, ensure_journal_schema

    ensure_journal_schema()
    preview = preview_close(start, end)
    existing = (
        tenant_query(FiscalYear)
        .filter_by(start_date=start, end_date=end, status='open')
        .first()
    )
    if _overlap(start, end, ignore_id=existing.id if existing else None):
        raise ValueError('هذه الفترة تتداخل مع سنة مالية مسجّلة')
    retained = _retained_earnings()
    if not retained:
        raise ValueError('حساب الأرباح المبقاة (3300) غير موجود في الشجرة')

    year = existing or FiscalYear(start_date=start, end_date=end, status='open', net_income=0)
    if not existing:
        assign_organization(year)
        db.session.add(year)
        db.session.flush()

    journal_lines: list[tuple[int, float, float, str | None]] = []
    re_credit = 0.0
    re_debit = 0.0
    for row in preview['lines']:
        amt = row['amount']
        if row['account_type'] == 'revenue':
            if amt > 0:
                journal_lines.append((row['account_id'], amt, 0, 'إقفال إيراد'))
                re_credit = _round2(re_credit + amt)
            else:
                journal_lines.append((row['account_id'], 0, abs(amt), 'إقفال إيراد'))
                re_debit = _round2(re_debit + abs(amt))
        else:
            if amt > 0:
                journal_lines.append((row['account_id'], 0, amt, 'إقفال مصروف'))
                re_debit = _round2(re_debit + amt)
            else:
                journal_lines.append((row['account_id'], abs(amt), 0, 'إقفال مصروف'))
                re_credit = _round2(re_credit + abs(amt))

    net_to_re = _round2(re_credit - re_debit)
    if net_to_re > 0:
        journal_lines.append((retained.id, 0, net_to_re, 'أرباح العام إلى الأرباح المبقاة'))
    elif net_to_re < 0:
        journal_lines.append((retained.id, abs(net_to_re), 0, 'خسائر العام إلى الأرباح المبقاة'))

    journal = None
    if journal_lines:
        journal = _create_entry(
            entry_date=end,
            memo=f'إقفال السنة المالية {start.isoformat()} — {end.isoformat()}',
            source_type='year_close',
            source_id=year.id,
            lines=journal_lines,
        )
        if journal is None:
            raise ValueError('تعذّر بناء قيد الإقفال')

    year.status = 'closed'
    year.net_income = preview['net']
    year.journal_id = journal.id if journal else None
    year.closed_at = datetime.utcnow()
    try:
        from flask import g, has_request_context
        if has_request_context():
            user = getattr(g, 'user', None)
            if user is not None:
                year.closed_by_name = getattr(user, 'full_name', None) or getattr(user, 'username', None)
    except Exception:
        pass
    return year


def reopen_fiscal_year(year_id: int) -> FiscalYear:
    """يعيد فتح آخر سنة مقفلة ويلغي قيد إقفالها."""
    ensure_fiscal_schema()
    year = tenant_query(FiscalYear).filter_by(id=year_id).first()
    if not year or year.status != 'closed':
        raise ValueError('السنة غير مقفلة')
    later = (
        tenant_query(FiscalYear)
        .filter(FiscalYear.status == 'closed', FiscalYear.end_date > year.end_date)
        .first()
    )
    if later:
        raise ValueError('أغلق السنة الأحدث أولاً بإعادة فتحها قبل هذه السنة')
    if year.journal_id:
        je = tenant_query(JournalEntry).filter_by(id=year.journal_id, status='posted').first()
        if je:
            je.status = 'void'
    year.status = 'open'
    year.journal_id = None
    return year
