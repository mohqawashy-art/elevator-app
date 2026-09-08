"""عقود التركيب — إنشاء ومزامنة مع المشروع وكارت المشروع."""
from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy import inspect, text

from contract_codes import CONTRACT_CODE_DIGITS, contract_prefix_for_type
from installation.models import (
    INSTALL_CONTRACT_INSTALLMENT_STATUSES,
    INSTALL_CONTRACT_STATUSES,
    InstallContract,
    InstallContractInstallment,
    InstallProject,
)
from installation.timeline import timeline_progress
from models import db
from sales.service import add_months, money_round
from tenant_scope import assign_organization, tenant_query


def ensure_install_contract_schema() -> None:
    """إنشاء جداول عقود التركيب إن غابت."""
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())
    if 'installation_contracts' not in tables:
        InstallContract.__table__.create(bind=db.engine, checkfirst=True)
    if 'installation_contract_installments' not in tables:
        InstallContractInstallment.__table__.create(bind=db.engine, checkfirst=True)


def contract_for_project(project: InstallProject) -> InstallContract | None:
    if not project or not project.id:
        return None
    return tenant_query(InstallContract).filter_by(project_id=project.id).first()


def create_install_contract_for_project(project, quotation, *, next_code_fn) -> InstallContract | None:
    """إنشاء عقد تركيب مرتبط بالمشروع والعرض المعتمد."""
    ensure_install_contract_schema()
    existing = contract_for_project(project)
    if existing:
        return existing

    customer_id = project.customer_id or getattr(quotation, 'customer_id', None)
    if not customer_id:
        return None

    quote_type = (getattr(quotation, 'quote_type', None) or 'new').strip()
    contract_type = 'عقد تحديث' if quote_type == 'upgrade' else 'عقد تركيب'
    prefix = contract_prefix_for_type(contract_type)
    code = next_code_fn(InstallContract, prefix, digits=CONTRACT_CODE_DIGITS)
    legacy_id = getattr(project, 'contract_id', None)
    if legacy_id:
        from models import Contract
        legacy = tenant_query(Contract).filter_by(id=legacy_id).first()
        if legacy and legacy.code:
            code = legacy.code

    total = money_round(getattr(quotation, 'grand_total', 0) or 0)
    value = money_round(getattr(quotation, 'before_tax', None) or total)
    tax_amount = money_round(getattr(quotation, 'vat_amount', None) or max(total - value, 0))
    tax_pct = 15.0
    if value:
        tax_pct = money_round((tax_amount / value) * 100.0) if value else 15.0

    start = date.today()
    duration_months = 12
    contract = InstallContract(
        code=code,
        project_id=project.id,
        quotation_id=quotation.id,
        customer_id=customer_id,
        contract_type=contract_type,
        start_date=start,
        end_date=add_months(start, duration_months),
        duration_months=duration_months,
        value=value,
        tax_pct=tax_pct,
        tax_amount=tax_amount,
        total=total or money_round(value + tax_amount),
        pay_schedule_json=quotation.pay_schedule_json,
        progress_pct=0,
        collected_amount=0,
        remaining_amount=total or money_round(value + tax_amount),
        status='نشط',
        signed_at=datetime.utcnow(),
        notes=f'من عرض التركيب {quotation.code}',
    )
    assign_organization(contract)
    db.session.add(contract)
    db.session.flush()

    for seq, item in enumerate(quotation.payment_items(), start=1):
        inst = InstallContractInstallment(
            contract_id=contract.id,
            seq=seq,
            label=item.get('label') or f'دفعة {seq}',
            pct=float(item.get('pct') or 0),
            amount=float(item.get('amount') or 0),
            collected_amount=0,
            status='مستحقة',
        )
        assign_organization(inst)
        db.session.add(inst)

    legacy_id = getattr(project, 'contract_id', None)
    if legacy_id:
        contract.legacy_contract_id = legacy_id

    return contract


def sync_install_contract_from_project(project: InstallProject) -> InstallContract | None:
    """مزامنة التحصيل ونسبة الإنجاز من كارت المشروع وجدول التنفيذ."""
    contract = contract_for_project(project)
    if not contract:
        return None

    receipts = list(project.receipts or [])
    by_seq: dict[int, float] = {}
    for receipt in receipts:
        if (receipt.status or 'مستلمة') != 'مستلمة':
            continue
        seq = int(receipt.installment_no or 0)
        by_seq[seq] = round(by_seq.get(seq, 0) + float(receipt.amount or 0), 2)

    collected_total = 0.0
    installments = list(contract.installments or [])
    for inst in sorted(installments, key=lambda x: x.seq or 0):
        collected = round(by_seq.get(inst.seq, 0), 2)
        inst.collected_amount = collected
        amount = float(inst.amount or 0)
        if amount > 0 and collected >= amount:
            inst.status = 'محصّلة'
        elif collected > 0:
            inst.status = 'جزئية'
        else:
            inst.status = 'مستحقة'
        collected_total += collected

    contract.collected_amount = round(collected_total, 2)
    contract.remaining_amount = round(max(float(contract.total or 0) - collected_total, 0), 2)

    if project.execution_active:
        steps = sorted(project.timeline_steps or [], key=lambda s: s.sort_order or 0)
        contract.progress_pct = int(timeline_progress(steps) or 0)
    else:
        contract.progress_pct = int(contract.progress_pct or 0)

    if contract.progress_pct >= 100 and contract.status == 'نشط':
        contract.status = 'مكتمل'
    elif contract.status == 'مسودة' and project.execution_active:
        contract.status = 'نشط'

    return contract


def build_install_contract_summary(contract: InstallContract, project: InstallProject | None = None) -> dict:
    """ملخص العقد للعرض في الجدول أو صفحة التفاصيل."""
    if project is None:
        project = contract.project
    sync_install_contract_from_project(project) if project else None

    installments = []
    for inst in sorted(contract.installments or [], key=lambda x: x.seq or 0):
        installments.append({
            'id': inst.id,
            'seq': inst.seq,
            'label': inst.label,
            'pct': inst.pct,
            'amount': float(inst.amount or 0),
            'collected_amount': float(inst.collected_amount or 0),
            'remaining_amount': inst.remaining_amount,
            'status': inst.status,
            'due_date': inst.due_date.isoformat() if inst.due_date else None,
        })

    days_total = None
    days_elapsed = None
    if contract.start_date and contract.end_date:
        days_total = (contract.end_date - contract.start_date).days
        days_elapsed = max((date.today() - contract.start_date).days, 0)

    return {
        'contract': contract,
        'project': project,
        'installments': installments,
        'collected_amount': float(contract.collected_amount or 0),
        'remaining_amount': float(contract.remaining_amount or 0),
        'total': float(contract.total or 0),
        'progress_pct': int(contract.progress_pct or 0),
        'duration_months': contract.duration_months,
        'start_date': contract.start_date,
        'end_date': contract.end_date,
        'days_total': days_total,
        'days_elapsed': days_elapsed,
        'status': contract.status,
        'contract_type': contract.contract_type,
        'customer': contract.customer,
        'quotation': contract.quotation,
    }


def update_install_contract_schedule(contract: InstallContract, form) -> str | None:
    """تحديث مدة العقد وتواريخه من النموذج."""
    start_raw = (form.get('start_date') or '').strip()
    end_raw = (form.get('end_date') or '').strip()
    duration_raw = (form.get('duration_months') or '').strip()
    notes = (form.get('notes') or '').strip()

    if start_raw:
        try:
            contract.start_date = datetime.strptime(start_raw, '%Y-%m-%d').date()
        except ValueError:
            return 'تاريخ البداية غير صالح'
    if end_raw:
        try:
            contract.end_date = datetime.strptime(end_raw, '%Y-%m-%d').date()
        except ValueError:
            return 'تاريخ النهاية غير صالح'
    if duration_raw:
        try:
            months = int(duration_raw)
            if months < 1 or months > 120:
                return 'مدة العقد يجب أن تكون بين 1 و 120 شهراً'
            contract.duration_months = months
            if contract.start_date and not end_raw:
                contract.end_date = add_months(contract.start_date, months)
        except ValueError:
            return 'مدة العقد غير صالحة'
    if notes or notes == '':
        contract.notes = notes or None
    return None


def delete_install_contract_for_project(project: InstallProject) -> None:
    contract = contract_for_project(project)
    if not contract:
        return
    db.session.delete(contract)
