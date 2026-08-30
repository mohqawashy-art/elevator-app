"""تحويل مشروع التركيب المكتمل إلى عقد ضمان صيانة لسنة واحدة.

الربط الوحيد المسموح بين التركيب والصيانة.
"""
from __future__ import annotations

from datetime import date, datetime

from contract_codes import CONTRACT_CODE_DIGITS, contract_prefix_for_type
from models import Contract, ContractElevator, Elevator, db
from sales.service import add_months
from tenant_scope import assign_organization, tenant_query

WARRANTY_MONTHS = 12
WARRANTY_CONTRACT_TYPE = 'عقد ضمان'
WORK_PHASES = ('توريد', 'تركيب', 'تسليم')


def work_phases_complete(steps) -> bool:
    """True إذا اكتملت مراحل التوريد والتركيب والتسليم بالكامل."""
    by_group = {}
    for step in steps or []:
        g = (getattr(step, 'phase_group', None) or '').strip()
        if g not in WORK_PHASES:
            continue
        info = by_group.setdefault(g, {'total': 0, 'done': 0})
        info['total'] += 1
        if getattr(step, 'status', None) == 'مكتمل':
            info['done'] += 1
    # يجب وجود المراحل الثلاث واكتمال كل خطواتها
    for name in WORK_PHASES:
        info = by_group.get(name)
        if not info or not info['total'] or info['done'] < info['total']:
            return False
    return True


def warranty_start_completed(steps) -> bool:
    for step in steps or []:
        if getattr(step, 'step_key', None) == 'warranty_start' and getattr(step, 'status', None) == 'مكتمل':
            return True
    return False


def should_create_warranty(project) -> bool:
    """يُنشأ عقد الضمان بعد اكتمال المراحل الثلاث، أو عند إكمال خطوة بدء الضمان."""
    steps = list(getattr(project, 'timeline_steps', None) or [])
    if not steps:
        return False
    if getattr(project, 'warranty_contract_id', None):
        return False
    return work_phases_complete(steps) or warranty_start_completed(steps)


def _existing_warranty_for_project(project) -> Contract | None:
    wid = getattr(project, 'warranty_contract_id', None)
    if wid:
        found = tenant_query(Contract).filter_by(id=wid).first()
        if found:
            return found
    customer_id = getattr(project, 'customer_id', None)
    if not customer_id:
        return None
    marker = f'[install-warranty:{project.id}]'
    for c in tenant_query(Contract).filter_by(customer_id=customer_id, contract_type=WARRANTY_CONTRACT_TYPE).all():
        notes = c.notes or ''
        if marker in notes or (project.code and project.code in notes and 'ضمان تركيب' in notes):
            return c
    return None


def create_warranty_contract_from_project(project, *, next_code_fn) -> Contract | None:
    """إنشاء عقد ضمان CN- لسنة واحدة بعد اكتمال التركيب."""
    existing = _existing_warranty_for_project(project)
    if existing:
        if not getattr(project, 'warranty_contract_id', None):
            project.warranty_contract_id = existing.id
        return existing

    customer_id = project.customer_id or (project.customer.id if project.customer else None)
    if not customer_id:
        return None

    start = date.today()
    for step in sorted(project.timeline_steps, key=lambda s: s.sort_order):
        if step.step_key in ('client_delivery', 'warranty_start') and step.completed_at:
            start = step.completed_at.date()
            break
    end = add_months(start, WARRANTY_MONTHS)
    prefix = contract_prefix_for_type(WARRANTY_CONTRACT_TYPE)
    code = next_code_fn(Contract, prefix, digits=CONTRACT_CODE_DIGITS)

    customer = project.customer
    notes = (
        f'عقد ضمان صيانة مجانية سنة واحدة بعد اكتمال التركيب — المشروع {project.code}. '
        f'[install-warranty:{project.id}]'
    )
    contract = Contract(
        code=code,
        customer_id=customer_id,
        contract_type=WARRANTY_CONTRACT_TYPE,
        start_date=start,
        end_date=end,
        duration_months=WARRANTY_MONTHS,
        maint_frequency='شهري',
        visits_per_month=1,
        value=0,
        tax_pct=15,
        tax_amount=0,
        total=0,
        payment_terms='دفعة واحدة',
        invoice_status='مدفوع',
        paid_amount=0,
        status='نشط',
        city=(customer.city if customer else None) or None,
        district=(customer.district if customer else None) or None,
        address=(customer.address if customer else None) or None,
        notes=notes,
    )
    assign_organization(contract)
    db.session.add(contract)
    db.session.flush()

    elevators = tenant_query(Elevator).filter_by(customer_id=customer_id).all()
    for elev in elevators:
        ce = ContractElevator(contract_id=contract.id, elevator_id=elev.id)
        assign_organization(ce)
        db.session.add(ce)
        if not elev.warranty_end or elev.warranty_end < end:
            elev.warranty_end = end
        if not elev.install_date:
            elev.install_date = start

    project.warranty_contract_id = contract.id
    if project.status not in ('ضمان', 'مكتمل', 'مغلق'):
        project.status = 'ضمان'
    project.updated_at = datetime.utcnow()
    return contract


def ensure_warranty_contract(project, *, next_code_fn) -> Contract | None:
    """إن وُجدت شروط التحويل — أنشئ عقد الضمان (مرة واحدة)."""
    existing = _existing_warranty_for_project(project)
    if existing:
        if not getattr(project, 'warranty_contract_id', None):
            project.warranty_contract_id = existing.id
        return existing
    if not should_create_warranty(project):
        return None
    return create_warranty_contract_from_project(project, next_code_fn=next_code_fn)
