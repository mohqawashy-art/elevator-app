"""ربط الجداول: عميل ← عقد ← مصعد ← زيارة / عطل / قطع غيار."""

from __future__ import annotations

from datetime import date

from models import Contract, ContractElevator, Customer, Elevator, Fault, MaintenanceVisit, PartsBilling
import re
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query


def normalize_code(code: str, prefix: str) -> str:
    code = (code or '').strip().upper().replace(' ', '')
    if not code:
        return ''
    if code.startswith(prefix):
        return code
    digits = re.sub(r'\D', '', code)
    if digits:
        return f'{prefix}{digits.zfill(5 if prefix in ("VI-", "FA-") else 3)}'
    return code


def natural_code_key(code: str | None):
    """مفتاح ترتيب طبيعي: EL-2 قبل EL-11 (وليس ترتيب نصي)."""
    text = str(code or '')
    parts = re.split(r'(\d+)', text)
    key = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.casefold()))
    return tuple(key) if key else ((1, ''),)


def sort_by_natural_code(rows, *, code_attr: str = 'code'):
    """ترتيب قائمة كائنات أو dict حسب كود طبيعي."""
    def _code(row):
        if isinstance(row, dict):
            return row.get(code_attr) or row.get('elevator') or row.get('elevator_code') or ''
        return getattr(row, code_attr, None) or ''
    return sorted(rows, key=lambda row: natural_code_key(_code(row)))


def lookup_visit(code: str) -> MaintenanceVisit | None:
    norm = normalize_code(code, 'VI-')
    if not norm:
        return None
    return tenant_query(MaintenanceVisit).filter_by(code=norm).first()


def lookup_fault(code: str) -> Fault | None:
    norm = normalize_code(code, 'FA-')
    if not norm:
        return None
    return tenant_query(Fault).filter_by(code=norm).first()


def active_contract_for_elevator(elevator_id: int, on_date: date | None = None) -> Contract | None:
    """أحدث عقد نشط يربط المصعد (أو عقد العميل) في التاريخ المحدد."""
    if not elevator_id:
        return None
    elev = tenant_query(Elevator).filter_by(id=elevator_id).first()
    if not elev:
        return None
    on_date = on_date or date.today()

    links = tenant_query(ContractElevator).filter_by(elevator_id=elevator_id).all()
    contract_ids = [lk.contract_id for lk in links]
    if contract_ids:
        contracts = (
            tenant_query(Contract).filter(Contract.id.in_(contract_ids))
            .order_by(Contract.end_date.desc())
            .all()
        )
    else:
        contracts = (
            tenant_query(Contract).filter_by(customer_id=elev.customer_id)
            .order_by(Contract.end_date.desc())
            .all()
        )

    for c in contracts:
        if c.start_date and c.end_date and c.start_date <= on_date <= c.end_date:
            return c
    return contracts[0] if contracts else None


def resolve_visit_links(elevator_id, contract_id=None, visit_date=None) -> dict:
    """يُرجع contract_id محسوباً من المصعد إن لم يُرسل."""
    elev_id = int(elevator_id) if elevator_id else None
    cid = int(contract_id) if contract_id else None
    vdate = visit_date
    if isinstance(vdate, str) and vdate:
        from datetime import datetime
        vdate = datetime.strptime(vdate[:10], '%Y-%m-%d').date()

    if not cid and elev_id:
        c = active_contract_for_elevator(elev_id, vdate)
        cid = c.id if c else None
    return {'elevator_id': elev_id, 'contract_id': cid}


def contract_by_code(code: str) -> Contract | None:
    code = (code or '').strip().upper().replace(' ', '')
    if not code:
        return None
    m = re.match(r'CN-?(\d+)$', code)
    if m:
        num = int(m.group(1))
        variants = (
            f'CN-{num:05d}',
            f'CN-{num}',
            f'CN-{num:04d}',
            f'CN-{num:03d}',
        )
        seen: set[str] = set()
        for variant in variants:
            if variant in seen:
                continue
            seen.add(variant)
            found = tenant_query(Contract).filter_by(code=variant).first()
            if found:
                return found
        return None
    if code.isdigit():
        return contract_by_code(f'CN-{code}')
    if code.startswith('CN') and not code.startswith('CN-'):
        return contract_by_code('CN-' + code[2:].lstrip('-'))
    return tenant_query(Contract).filter_by(code=code).first()


def customer_by_name(name: str) -> Customer | None:
    name = (name or '').strip()
    if not name:
        return None
    return tenant_query(Customer).filter(Customer.name == name).first()


def resolve_parts_links(
    *,
    customer_id=None,
    contract_id=None,
    contract_code=None,
    customer_name=None,
    elevator_id=None,
    technician_id=None,
    visit_id=None,
    fault_id=None,
    visit_code=None,
    fault_code=None,
) -> dict:
    """يربط قطع الغيار بالعميل والعقد والمصعد."""
    cid = int(contract_id) if contract_id else None
    cust_id = int(customer_id) if customer_id else None
    elev_id = int(elevator_id) if elevator_id else None
    tech_id = int(technician_id) if technician_id else None
    vid = int(visit_id) if visit_id else None
    fid = int(fault_id) if fault_id else None

    visit = tenant_query(MaintenanceVisit).filter_by(id=vid).first() if vid else None
    fault = tenant_query(Fault).filter_by(id=fid).first() if fid else None
    if not visit and visit_code:
        visit = lookup_visit(visit_code)
    if not fault and fault_code:
        fault = lookup_fault(fault_code)
    if visit:
        vid = visit.id
        elev_id = elev_id or visit.elevator_id
        cid = cid or visit.contract_id
        tech_id = tech_id or visit.technician_id
    if fault:
        fid = fault.id
        elev_id = elev_id or fault.elevator_id
        tech_id = tech_id or fault.technician_id
        if not visit and fault.visit_id:
            visit = tenant_query(MaintenanceVisit).filter_by(id=fault.visit_id).first()
            if visit:
                vid = visit.id
                cid = cid or visit.contract_id

    contract = tenant_query(Contract).filter_by(id=cid).first() if cid else None
    if not contract and contract_code:
        contract = contract_by_code(contract_code)
    if contract:
        cid = contract.id
        cust_id = contract.customer_id

    if not cust_id and customer_name:
        cust = customer_by_name(customer_name)
        if cust:
            cust_id = cust.id

    if not cid and cust_id:
        cust = tenant_query(Customer).filter_by(id=cust_id).first()
        if cust:
            c = _primary_contract(cust)
            if c:
                cid = c.id

    if not elev_id and cid:
        link = tenant_query(ContractElevator).filter_by(contract_id=cid).first()
        if link:
            elev_id = link.elevator_id
    if not elev_id and cust_id:
        elev = tenant_query(Elevator).filter_by(customer_id=cust_id).first()
        if elev:
            elev_id = elev.id

    if not cust_id and elev_id:
        elev = tenant_query(Elevator).filter_by(id=elev_id).first()
        if elev:
            cust_id = elev.customer_id

    return {
        'customer_id': cust_id,
        'contract_id': cid,
        'elevator_id': elev_id,
        'technician_id': tech_id,
        'visit_id': vid,
        'fault_id': fid,
    }


def link_fault_to_visit(fault: Fault, visit: MaintenanceVisit) -> None:
    """ربط عطل بزيارة معالجة."""
    if not fault or not visit:
        return
    fault.visit_id = visit.id
    visit.fault_id = fault.id
    if not fault.technician_id and visit.technician_id:
        fault.technician_id = visit.technician_id
    if fault.status in ('مفتوح', 'قيد المعالجة') and visit.status == 'مكتملة':
        fault.status = 'محلول'


def _primary_contract(customer: Customer) -> Contract | None:
    today = date.today()
    contracts = (
        tenant_query(Contract).filter_by(customer_id=customer.id)
        .order_by(Contract.end_date.desc())
        .all()
    )
    if not contracts:
        return None
    for c in contracts:
        if c.start_date and c.end_date and c.start_date <= today <= c.end_date:
            return c
        if c.end_date and (c.end_date - today).days <= 30:
            return c
    return contracts[0]


def normalize_parts_status(status: str) -> str:
    s = (status or '').strip()
    if s in ('محصل', 'محصّل', 'مكتملة'):
        return 'محصل'
    if s in ('غير محصل', 'معلقة', ''):
        return 'غير محصل'
    return s


def _code_from_text(text: str, prefix: str) -> str | None:
    if not text:
        return None
    for pattern in (
        rf'{prefix}-\s*(\d+)',
        rf'{prefix}\s*:\s*(\d+)',
        rf'رقم\s*{"الزيارة" if prefix == "VI" else "العقد"}\s*:\s*{prefix}-?\s*(\d+)',
    ):
        m = re.search(pattern, text, re.I)
        if m:
            n = int(m.group(1))
            if prefix.upper() == 'CN':
                return f'CN-{n:05d}'
            if prefix.upper() == 'VI':
                return f'VI-{n:05d}'
    return None


def fault_parts_link_fields(f: Fault) -> dict:
    """حقول الربط لبيان قطع الغيار — زيارة، عقد، تاريخ (LiftCore + Jama)."""
    combined = '\n'.join(
        x for x in (f.notes or '', f.description or '', f.client_report or '', f.tech_notes or '') if x
    )
    visit_code = _code_from_text(combined, 'VI')
    cn_code = _code_from_text(combined, 'CN')

    visit = tenant_query(MaintenanceVisit).filter_by(id=f.visit_id).first() if f.visit_id else None
    if not visit:
        visit = (
            tenant_query(MaintenanceVisit).filter_by(fault_id=f.id)
            .order_by(MaintenanceVisit.visit_date.desc(), MaintenanceVisit.id.desc())
            .first()
        )
    if not visit and visit_code:
        visit = lookup_visit(visit_code)

    elev = f.elevator
    ref_date = visit.visit_date if visit and visit.visit_date else (
        f.reported_at.date() if f.reported_at else None
    )

    contract = tenant_query(Contract).filter_by(id=visit.contract_id).first() if visit and visit.contract_id else None
    if not contract and cn_code:
        contract = contract_by_code(cn_code)
    if not contract and elev:
        contract = active_contract_for_elevator(elev.id, ref_date)
    if not contract and elev:
        link = tenant_query(ContractElevator).filter_by(elevator_id=elev.id).first()
        if link:
            contract = tenant_query(Contract).filter_by(id=link.contract_id).first()

    resolved_visit_code = visit.code if visit else (visit_code or '')
    resolved_cn = contract.code if contract else (cn_code or '')

    billing_date = ''
    if visit and visit.visit_date:
        billing_date = visit.visit_date.isoformat()
    elif f.reported_at:
        billing_date = f.reported_at.strftime('%Y-%m-%d')

    return {
        'visit_id': visit.id if visit else None,
        'visit_code': resolved_visit_code,
        'contract_code': resolved_cn,
        'contract_id': contract.id if contract else None,
        'billing_date': billing_date,
    }


def elevator_link_payload(elevator_id: int) -> dict:
    elev = tenant_get_or_404(Elevator, elevator_id)
    contract_ids = [
        lk.contract_id for lk in tenant_query(ContractElevator).filter_by(elevator_id=elevator_id).all()
    ]
    if contract_ids:
        contracts = tenant_query(Contract).filter(Contract.id.in_(contract_ids)).order_by(Contract.end_date.desc()).all()
    else:
        contracts = (
            tenant_query(Contract).filter_by(customer_id=elev.customer_id)
            .order_by(Contract.end_date.desc())
            .all()
        )
    active = active_contract_for_elevator(elevator_id)
    return {
        'elevator_id': elev.id,
        'elevator_code': elev.code,
        'customer_id': elev.customer_id,
        'customer_name': elev.customer.name if elev.customer else '',
        'default_contract_id': active.id if active else None,
        'contracts': [
            {'id': c.id, 'code': c.code, 'start': str(c.start_date or ''), 'end': str(c.end_date or '')}
            for c in contracts
        ],
    }
