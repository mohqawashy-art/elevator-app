"""قيود يومية تلقائية + قيود يدوية (مرحلة 3) + دفتر أستاذ + ميزان مراجعة."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, inspect

from models import Account, Expense, JournalEntry, JournalLine, Revenue, db
from tenant_scope import assign_organization, effective_organization_id, tenant_query

from chart_of_accounts import (
    account_by_map_key,
    ensure_chart_schema,
    MAINTENANCE_REVENUE_ACCOUNT_CODES,
    resolve_expense_account_id,
    resolve_revenue_account_id,
)
from customer_billing import COLLECTED_REVENUE_STATUSES


def ensure_journal_schema() -> None:
    """إنشاء جداول القيود إن غابت (Postgres قد لا يشغّل Alembic تلقائياً)."""
    ensure_chart_schema()
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    created = False
    if 'journal_entries' not in tables:
        JournalEntry.__table__.create(bind=db.engine, checkfirst=True)
        created = True
    if 'journal_lines' not in tables:
        JournalLine.__table__.create(bind=db.engine, checkfirst=True)
        created = True
    if created:
        # DDL عبر engine قد يُبقي كائنات منتهية الصلاحية — لا نعمل rollback حتى لا نفقد قيوداً معلّقة
        try:
            db.session.expire_all()
        except Exception:
            pass


def _round2(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def _next_journal_code() -> str:
    from operations import next_code

    return next_code(JournalEntry, 'JE-', digits=4)


def _void_source_journals(source_type: str, source_id: int) -> int:
    q = (
        tenant_query(JournalEntry)
        .filter_by(source_type=source_type, source_id=source_id, status='posted')
    )
    n = 0
    for je in q.all():
        je.status = 'void'
        n += 1
    return n


def _create_entry(
    *,
    entry_date: date,
    memo: str,
    source_type: str,
    source_id: int,
    lines: list[tuple[int, float, float, str | None]],
) -> JournalEntry | None:
    """lines: (account_id, debit, credit, line_memo). يجب أن يتوازن القيد."""
    cleaned: list[tuple[int, float, float, str | None]] = []
    total_d = 0.0
    total_c = 0.0
    for account_id, debit, credit, line_memo in lines:
        if not account_id:
            continue
        d = _round2(debit)
        c = _round2(credit)
        if d <= 0 and c <= 0:
            continue
        if d > 0 and c > 0:
            # لا مدين ودائن على نفس السطر
            if d >= c:
                d, c = _round2(d - c), 0.0
            else:
                c, d = _round2(c - d), 0.0
        cleaned.append((account_id, d, c, line_memo))
        total_d = _round2(total_d + d)
        total_c = _round2(total_c + c)

    if not cleaned or total_d <= 0 or total_d != total_c:
        return None

    if source_id:
        _void_source_journals(source_type, source_id)
    je = JournalEntry(
        code=_next_journal_code(),
        entry_date=entry_date,
        memo=(memo or '')[:400],
        source_type=source_type,
        source_id=source_id,
        status='posted',
    )
    assign_organization(je)
    try:
        from flask import g, has_request_context, session
        if has_request_context():
            user = getattr(g, 'user', None)
            if user is not None:
                je.created_by_user_id = getattr(user, 'id', None)
                je.created_by_name = getattr(user, 'full_name', None) or getattr(user, 'username', None)
            elif session.get('user_id'):
                je.created_by_user_id = session.get('user_id')
                je.created_by_name = session.get('user_name')
    except Exception:
        pass
    db.session.add(je)
    db.session.flush()
    for account_id, d, c, line_memo in cleaned:
        line = JournalLine(
            journal_id=je.id,
            account_id=account_id,
            debit=d,
            credit=c,
            line_memo=(line_memo or '')[:300] or None,
        )
        assign_organization(line)
        db.session.add(line)
    return je


def post_revenue_journal(revenue: Revenue) -> JournalEntry | None:
    """قيد تحصيل إيراد: مدين نقدية / دائن إيراد (+ ضريبة إن وجدت)."""
    revenue_id = revenue.id
    ensure_journal_schema()
    if revenue_id:
        reloaded = db.session.get(Revenue, revenue_id)
        if reloaded is not None:
            revenue = reloaded
    oid = getattr(revenue, 'organization_id', None) or effective_organization_id()
    if oid:
        with db.session.no_autoflush:
            ensure_chart_schema()

    if (revenue.status or '') not in COLLECTED_REVENUE_STATUSES:
        _void_source_journals('revenue', revenue.id)
        return None

    cash = account_by_map_key('cash')
    vat = account_by_map_key('vat_payable')
    rev_id = revenue.account_id or resolve_revenue_account_id(revenue.revenue_type, revenue.notes)
    if not cash or not rev_id:
        return None

    total = _round2(revenue.total if revenue.total is not None else (revenue.amount or 0) + (revenue.tax_amount or 0))
    tax = _round2(revenue.tax_amount)
    net = _round2(revenue.amount if revenue.amount is not None else max(total - tax, 0))
    if total <= 0:
        _void_source_journals('revenue', revenue.id)
        return None

    # إن كان المبلغ شامل الضريبة ولم يُفصل: اعتبر الكل إيراداً
    if tax <= 0:
        net, tax = total, 0.0
    elif _round2(net + tax) != total:
        net = _round2(total - tax)

    lines: list[tuple[int, float, float, str | None]] = [
        (cash.id, total, 0.0, f'تحصيل {revenue.code}'),
        (rev_id, 0.0, net, revenue.revenue_type or 'إيراد'),
    ]
    if tax > 0 and vat:
        lines.append((vat.id, 0.0, tax, 'ضريبة قيمة مضافة'))
    elif tax > 0:
        # لا حساب ضريبة — أضف الضريبة للإيراد
        lines[1] = (rev_id, 0.0, total, revenue.revenue_type or 'إيراد')

    memo = f'إيراد {revenue.code}'
    if revenue.revenue_type:
        memo += f' — {revenue.revenue_type}'
    return _create_entry(
        entry_date=revenue.revenue_date or date.today(),
        memo=memo,
        source_type='revenue',
        source_id=revenue.id,
        lines=lines,
    )


def post_expense_journal(expense: Expense) -> JournalEntry | None:
    """قيد مصروف: مدين مصروف / دائن نقدية."""
    expense_id = expense.id
    ensure_journal_schema()
    if expense_id:
        reloaded = db.session.get(Expense, expense_id)
        if reloaded is not None:
            expense = reloaded
    oid = getattr(expense, 'organization_id', None) or effective_organization_id()
    if oid:
        with db.session.no_autoflush:
            ensure_chart_schema()

    cash = account_by_map_key('cash')
    exp_id = expense.account_id or resolve_expense_account_id(expense.expense_type)
    amount = _round2(expense.amount)
    if not cash or not exp_id or amount <= 0:
        _void_source_journals('expense', expense.id)
        return None

    memo = f'مصروف {expense.code}'
    if expense.expense_type:
        memo += f' — {expense.expense_type}'
    return _create_entry(
        entry_date=expense.expense_date or date.today(),
        memo=memo,
        source_type='expense',
        source_id=expense.id,
        lines=[
            (exp_id, amount, 0.0, expense.description or expense.expense_type or 'مصروف'),
            (cash.id, 0.0, amount, f'صرف {expense.code}'),
        ],
    )


def void_revenue_journal(revenue_id: int) -> int:
    return _void_source_journals('revenue', revenue_id)


def void_expense_journal(expense_id: int) -> int:
    return _void_source_journals('expense', expense_id)


MANUAL_SOURCE_TYPES = frozenset({'manual', 'opening'})


def create_manual_journal(
    *,
    entry_date: date,
    memo: str,
    lines: list[tuple[int, float, float, str | None]],
    kind: str = 'manual',
) -> JournalEntry | None:
    """قيد يدوي متوازن. kind: manual | opening."""
    ensure_journal_schema()
    oid = effective_organization_id()
    if oid:
        with db.session.no_autoflush:
            ensure_chart_schema()
    source_type = kind if kind in MANUAL_SOURCE_TYPES else 'manual'
    return _create_entry(
        entry_date=entry_date or date.today(),
        memo=memo or ('رصيد افتتاحي' if source_type == 'opening' else 'قيد يدوي'),
        source_type=source_type,
        source_id=None,
        lines=lines,
    )


def void_manual_journal(journal_id: int) -> bool:
    """إلغاء قيد يدوي/افتتاحي مرحّل فقط — لا يمس قيود الإيراد/المصروف التلقائية."""
    ensure_journal_schema()
    je = tenant_query(JournalEntry).filter_by(id=journal_id).first()
    if not je or je.status != 'posted' or (je.source_type or '') not in MANUAL_SOURCE_TYPES:
        return False
    je.status = 'void'
    return True


def backfill_journals(limit: int = 5000) -> dict[str, int]:
    """ترحيل قيود للإيرادات/المصروفات التي بلا قيد مرحّل."""
    ensure_journal_schema()
    oid = effective_organization_id()
    if oid:
        ensure_chart_schema()

    posted_rev = {
        je.source_id
        for je in tenant_query(JournalEntry)
        .filter_by(source_type='revenue', status='posted')
        .all()
        if je.source_id
    }
    posted_exp = {
        je.source_id
        for je in tenant_query(JournalEntry)
        .filter_by(source_type='expense', status='posted')
        .all()
        if je.source_id
    }

    stats = {'revenues': 0, 'expenses': 0, 'skipped': 0}
    for rev in tenant_query(Revenue).order_by(Revenue.id.asc()).limit(limit).all():
        if rev.id in posted_rev:
            continue
        if (rev.status or '') not in COLLECTED_REVENUE_STATUSES:
            stats['skipped'] += 1
            continue
        if not rev.account_id:
            rev.account_id = resolve_revenue_account_id(rev.revenue_type, rev.notes)
        je = post_revenue_journal(rev)
        if je:
            stats['revenues'] += 1
        else:
            stats['skipped'] += 1

    for exp in tenant_query(Expense).order_by(Expense.id.asc()).limit(limit).all():
        if exp.id in posted_exp:
            continue
        if not exp.account_id:
            exp.account_id = resolve_expense_account_id(exp.expense_type)
        je = post_expense_journal(exp)
        if je:
            stats['expenses'] += 1
        else:
            stats['skipped'] += 1

    db.session.commit()
    return stats


def trial_balance_rows(date_to: date | None = None) -> list[dict]:
    """ميزان مراجعة: مجموع مدين/دائن ورصيد لكل حساب قابل للترحيل."""
    ensure_journal_schema()
    q = (
        db.session.query(
            Account.id,
            Account.code,
            Account.name,
            Account.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0).label('debit'),
            func.coalesce(func.sum(JournalLine.credit), 0).label('credit'),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .filter(JournalEntry.status == 'posted')
    )
    oid = effective_organization_id()
    if oid:
        q = q.filter(Account.organization_id == oid, JournalEntry.organization_id == oid)
    if date_to:
        q = q.filter(JournalEntry.entry_date <= date_to)
    q = q.group_by(Account.id, Account.code, Account.name, Account.account_type)
    q = q.order_by(Account.code.asc())

    rows = []
    total_d = total_c = 0.0
    for acc_id, code, name, atype, debit, credit in q.all():
        d = _round2(debit)
        c = _round2(credit)
        # أصول/مصروفات: رصيد مدين طبيعي؛ خصوم/حقوق/إيرادات: دائن
        if atype in ('asset', 'expense'):
            balance = _round2(d - c)
            bal_side = 'debit' if balance >= 0 else 'credit'
            balance = abs(balance)
        else:
            balance = _round2(c - d)
            bal_side = 'credit' if balance >= 0 else 'debit'
            balance = abs(balance)
        rows.append({
            'account_id': acc_id,
            'code': code,
            'name': name,
            'account_type': atype,
            'debit': d,
            'credit': c,
            'balance': balance,
            'balance_side': bal_side,
        })
        total_d = _round2(total_d + d)
        total_c = _round2(total_c + c)
    return rows, total_d, total_c


def ledger_lines(account_id: int, date_from: date | None = None, date_to: date | None = None) -> tuple[Account | None, list[dict], float]:
    """دفتر أستاذ لحساب واحد مع رصيد جاري."""
    ensure_journal_schema()
    acc = tenant_query(Account).filter_by(id=account_id).first()
    if not acc:
        return None, [], 0.0

    q = (
        tenant_query(JournalLine)
        .join(JournalEntry)
        .filter(
            JournalLine.account_id == account_id,
            JournalEntry.status == 'posted',
        )
    )
    if date_from:
        q = q.filter(JournalEntry.entry_date >= date_from)
    if date_to:
        q = q.filter(JournalEntry.entry_date <= date_to)
    q = q.order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc(), JournalLine.id.asc())

    running = 0.0
    natural_debit = acc.account_type in ('asset', 'expense')
    out = []
    for line in q.all():
        je = line.journal
        d = _round2(line.debit)
        c = _round2(line.credit)
        if natural_debit:
            running = _round2(running + d - c)
        else:
            running = _round2(running + c - d)
        out.append({
            'date': je.entry_date,
            'journal_code': je.code,
            'journal_id': je.id,
            'memo': line.line_memo or je.memo or '',
            'debit': d,
            'credit': c,
            'balance': running,
        })
    return acc, out, running


def income_statement(date_from: date | None = None, date_to: date | None = None) -> dict:
    """قائمة دخل مبسطة من القيود المرحّلة."""
    ensure_journal_schema()
    oid = effective_organization_id()
    q = (
        db.session.query(
            Account.account_type,
            func.coalesce(func.sum(JournalLine.credit), 0),
            func.coalesce(func.sum(JournalLine.debit), 0),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .filter(JournalEntry.status == 'posted', Account.account_type.in_(['revenue', 'expense']))
    )
    oid = effective_organization_id()
    if oid:
        q = q.filter(Account.organization_id == oid, JournalEntry.organization_id == oid)
    if date_from:
        q = q.filter(JournalEntry.entry_date >= date_from)
    if date_to:
        q = q.filter(JournalEntry.entry_date <= date_to)
    q = q.group_by(Account.account_type)

    revenue = expense = 0.0
    for atype, credit, debit in q.all():
        if atype == 'revenue':
            revenue = _round2(credit - debit)
        elif atype == 'expense':
            expense = _round2(debit - credit)

    detail_q = (
        db.session.query(
            Account.code,
            Account.name,
            Account.account_type,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .filter(JournalEntry.status == 'posted', Account.account_type.in_(['revenue', 'expense']))
    )
    if oid:
        detail_q = detail_q.filter(Account.organization_id == oid, JournalEntry.organization_id == oid)
    if date_from:
        detail_q = detail_q.filter(JournalEntry.entry_date >= date_from)
    if date_to:
        detail_q = detail_q.filter(JournalEntry.entry_date <= date_to)
    detail_q = detail_q.group_by(Account.id, Account.code, Account.name, Account.account_type)
    detail_q = detail_q.order_by(Account.account_type.asc(), Account.code.asc())

    revenue_lines = []
    expense_lines = []
    maintenance_journal_revenue = 0.0
    for code, name, atype, debit, credit in detail_q.all():
        if atype == 'revenue':
            amt = _round2(credit - debit)
            if amt:
                revenue_lines.append({'code': code, 'name': name, 'amount': amt})
                if code in MAINTENANCE_REVENUE_ACCOUNT_CODES:
                    maintenance_journal_revenue = _round2(maintenance_journal_revenue + amt)
        else:
            amt = _round2(debit - credit)
            if amt:
                expense_lines.append({'code': code, 'name': name, 'amount': amt})

    # إيراد عقود الصيانة: مستحق بالزيارات المكتملة (لا قيمة العقد كاملة)
    from contract_cost_allocation import maintenance_contracts_pnl_summary

    maint = maintenance_contracts_pnl_summary(period_from=date_from, period_to=date_to)
    visit_earned = maint['earned_in_period']
    unearned_revenue = maint['unearned_total']
    has_maint_contracts = bool(maint.get('contract_lines'))

    adjusted_revenue = revenue
    if has_maint_contracts:
        if visit_earned > 0 or maintenance_journal_revenue > 0:
            revenue_lines = [
                ln for ln in revenue_lines
                if ln['code'] not in MAINTENANCE_REVENUE_ACCOUNT_CODES
            ]
            if visit_earned > 0:
                revenue_lines.append({
                    'code': '4110',
                    'name': 'عقود صيانة — مستحق بالزيارات',
                    'amount': visit_earned,
                })
            revenue_lines.sort(key=lambda x: x['code'])
        adjusted_revenue = _round2(revenue - maintenance_journal_revenue + visit_earned)

    adjusted_net = _round2(adjusted_revenue - expense)

    return {
        'revenue': adjusted_revenue,
        'expense': expense,
        'net': adjusted_net,
        'revenue_lines': revenue_lines,
        'expense_lines': expense_lines,
        'maintenance_journal_revenue': maintenance_journal_revenue,
        'maintenance_earned_by_visits': visit_earned,
        'unearned_revenue': unearned_revenue,
        'maintenance_contract_lines': maint.get('contract_lines') or [],
    }


def balance_sheet(as_of: date | None = None) -> dict:
    """مركز مالي مبسّط من أرصدة الحسابات."""
    rows, _, _ = trial_balance_rows(date_to=as_of)
    sections = {'asset': [], 'liability': [], 'equity': []}
    totals = {'asset': 0.0, 'liability': 0.0, 'equity': 0.0}
    for r in rows:
        at = r['account_type']
        if at not in sections:
            continue
        # تجاهل الإيراد/المصروف — صافي الدخل يُضاف لحقوق الملكية
        bal = r['balance']
        if r['balance_side'] == 'credit' and at == 'asset':
            bal = -bal
        if r['balance_side'] == 'debit' and at in ('liability', 'equity'):
            bal = -bal
        if not bal:
            continue
        sections[at].append({'code': r['code'], 'name': r['name'], 'amount': bal})
        totals[at] = _round2(totals[at] + bal)

    pnl = income_statement(date_to=as_of)
    net = pnl['net']
    if net:
        sections['equity'].append({'code': 'NI', 'name': 'صافي الدخل (الفترة)', 'amount': net})
        totals['equity'] = _round2(totals['equity'] + net)

    return {
        'assets': sections['asset'],
        'liabilities': sections['liability'],
        'equity': sections['equity'],
        'total_assets': totals['asset'],
        'total_liabilities': totals['liability'],
        'total_equity': totals['equity'],
        'total_liab_equity': _round2(totals['liability'] + totals['equity']),
    }
