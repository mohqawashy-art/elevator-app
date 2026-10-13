"""رصيد أول المدة من نظام سابق، وربح العقد من الإيراد والمصروف المربوطين به."""
from __future__ import annotations

from datetime import date

from sqlalchemy import inspect, text
from sqlalchemy.orm import joinedload

from models import (
    Account,
    Contract,
    Customer,
    CustomerOpeningBalance,
    Expense,
    JournalEntry,
    Revenue,
    db,
)
from tenant_scope import assign_organization, tenant_query

_schema_ready = False


def ensure_extra_schema() -> None:
    """جدول ذمم الافتتاح وعمود عقد المصروف — يعمل على Postgres وSQLite."""
    global _schema_ready
    if _schema_ready:
        return
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    if 'customer_opening_balances' not in tables:
        CustomerOpeningBalance.__table__.create(bind=db.engine, checkfirst=True)
        try:
            db.session.expire_all()
        except Exception:
            pass
        tables.add('customer_opening_balances')
    if 'expenses' in tables:
        cols = {c['name'] for c in insp.get_columns('expenses')}
        if 'contract_id' not in cols:
            db.session.execute(text('ALTER TABLE expenses ADD COLUMN contract_id INTEGER'))
            db.session.commit()
            try:
                db.session.execute(text(
                    'CREATE INDEX IF NOT EXISTS ix_expenses_contract_id ON expenses (contract_id)'
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
    _schema_ready = True


def customer_opening_rows(customer_id: int | None = None) -> list[CustomerOpeningBalance]:
    ensure_extra_schema()
    q = (
        tenant_query(CustomerOpeningBalance)
        .options(joinedload(CustomerOpeningBalance.customer))
        .join(JournalEntry, JournalEntry.id == CustomerOpeningBalance.journal_id)
        .filter(JournalEntry.status == 'posted', JournalEntry.source_type == 'opening')
    )
    if customer_id:
        q = q.filter(CustomerOpeningBalance.customer_id == customer_id)
    return q.order_by(CustomerOpeningBalance.as_of.asc(), CustomerOpeningBalance.id.asc()).all()


def list_opening_journals() -> list[JournalEntry]:
    from accounting_journals import ensure_journal_schema

    ensure_journal_schema()
    ensure_extra_schema()
    return (
        tenant_query(JournalEntry)
        .filter_by(source_type='opening')
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
        .all()
    )


def _ar_account() -> Account | None:
    from chart_of_accounts import account_by_map_key

    acc = account_by_map_key('ar')
    if acc:
        return acc
    return tenant_query(Account).filter_by(code='1140', is_postable=True).first()


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def post_opening_balance(
    entry_date: date,
    lines: list[tuple[int, float, float, str | None]],
    customers: list[tuple[int, float]],
    memo: str = 'قيد افتتاحي',
) -> JournalEntry:
    """يرحّل قيد افتتاحي متوازن، ويحفظ ذمم العملاء إن طابقت حساب الذمم."""
    from accounting_journals import create_manual_journal, ensure_journal_schema

    ensure_journal_schema()
    ensure_extra_schema()
    cleaned_customers: list[tuple[int, float]] = []
    for customer_id, amount in customers:
        amt = _round2(amount)
        if not customer_id or amt <= 0:
            continue
        if not tenant_query(Customer).filter_by(id=int(customer_id)).first():
            raise ValueError('عميل غير معروف في ذمم أول المدة')
        cleaned_customers.append((int(customer_id), amt))

    if cleaned_customers:
        ar = _ar_account()
        if not ar:
            raise ValueError('حساب ذمم العملاء (1140) غير موجود في الشجرة')
        ar_net = 0.0
        for account_id, debit, credit, _memo in lines:
            if int(account_id) != ar.id:
                continue
            ar_net = _round2(ar_net + _round2(debit) - _round2(credit))
        cust_sum = _round2(sum(amt for _cid, amt in cleaned_customers))
        if abs(ar_net - cust_sum) > 0.02:
            raise ValueError(
                f'مجموع ذمم العملاء ({cust_sum:.2f}) لازم يساوي رصيد حساب الذمم في القيد ({ar_net:.2f})'
            )

    je = create_manual_journal(
        entry_date=entry_date,
        memo=(memo or 'رصيد افتتاحي منقول')[:400],
        lines=lines,
        kind='opening',
    )
    if not je:
        raise ValueError('القيد غير متوازن أو ناقص — المدين لازم يساوي الدائن')
    for customer_id, amount in cleaned_customers:
        row = CustomerOpeningBalance(
            customer_id=customer_id,
            amount=amount,
            as_of=entry_date,
            journal_id=je.id,
            memo='رصيد افتتاحي',
        )
        assign_organization(row)
        db.session.add(row)
    return je


def contract_profit_report(date_from: date | None = None, date_to: date | None = None) -> dict:
    """ربح كل عقد: إيراد محصّل بدون الضريبة − مصروف مربوط بالعقد."""
    from customer_billing import COLLECTED_REVENUE_STATUSES

    ensure_extra_schema()
    rq = tenant_query(Revenue).filter(Revenue.status.in_(COLLECTED_REVENUE_STATUSES))
    eq = tenant_query(Expense)
    if date_from:
        rq = rq.filter(Revenue.revenue_date >= date_from)
        eq = eq.filter(Expense.expense_date >= date_from)
    if date_to:
        rq = rq.filter(Revenue.revenue_date <= date_to)
        eq = eq.filter(Expense.expense_date <= date_to)
    revenues = rq.all()
    expenses = eq.all()

    buckets: dict[int, dict] = {}

    def bucket(contract_id: int | None) -> dict:
        key = int(contract_id or 0)
        row = buckets.get(key)
        if row is None:
            row = {
                'contract_id': key,
                'code': 'بدون عقد',
                'customer': '—',
                'revenue': 0.0,
                'expense': 0.0,
                'profit': 0.0,
            }
            buckets[key] = row
        return row

    contract_ids = {
        int(r.contract_id) for r in revenues if r.contract_id
    } | {
        int(e.contract_id) for e in expenses if getattr(e, 'contract_id', None)
    }
    contracts = {}
    if contract_ids:
        for c in (
            tenant_query(Contract)
            .options(joinedload(Contract.customer))
            .filter(Contract.id.in_(contract_ids))
            .all()
        ):
            contracts[c.id] = c
    for cid, contract in contracts.items():
        row = bucket(cid)
        row['code'] = contract.code
        row['customer'] = contract.customer.name if contract.customer else '—'

    for rev in revenues:
        row = bucket(rev.contract_id)
        amount = rev.amount if rev.amount not in (None, 0) else (rev.total or 0)
        row['revenue'] = _round2(row['revenue'] + float(amount or 0))
    for exp in expenses:
        row = bucket(getattr(exp, 'contract_id', None))
        row['expense'] = _round2(row['expense'] + float(exp.amount or 0))

    rows = []
    totals = {'revenue': 0.0, 'expense': 0.0, 'profit': 0.0}
    for row in buckets.values():
        if not row['revenue'] and not row['expense']:
            continue
        row['profit'] = _round2(row['revenue'] - row['expense'])
        totals['revenue'] = _round2(totals['revenue'] + row['revenue'])
        totals['expense'] = _round2(totals['expense'] + row['expense'])
        totals['profit'] = _round2(totals['profit'] + row['profit'])
        rows.append(row)
    rows.sort(key=lambda r: (r['contract_id'] == 0, -r['profit'], r['code'] or ''))
    return {'rows': rows, 'totals': totals}
