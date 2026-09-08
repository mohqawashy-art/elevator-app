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
    InstallQuotation,
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


def record_installment_payment(
    contract: InstallContract,
    seq: int,
    *,
    amount: float | None = None,
    received_date: date | None = None,
    payment_method: str | None = None,
    notes: str | None = None,
) -> str | None:
    """تسجيل سداد دفعة عقد التركيب عبر كارت المشروع."""
    from installation.models import InstallProjectReceipt
    from installation.project_card import ensure_project_card_schema

    project = contract.project
    if not project:
        return 'لا يوجد مشروع مرتبط بهذا العقد'

    sync_install_contract_from_project(project)
    inst = next(
        (i for i in (contract.installments or []) if int(i.seq or 0) == int(seq)),
        None,
    )
    if not inst:
        return 'الدفعة غير موجودة'

    remaining = inst.remaining_amount
    if remaining <= 0:
        return 'هذه الدفعة مسددة بالكامل'

    pay_amount = money_round(amount if amount and amount > 0 else remaining)
    if pay_amount <= 0:
        return 'أدخل مبلغ سداد أكبر من صفر'
    if pay_amount > remaining:
        pay_amount = remaining

    ensure_project_card_schema()
    receipt = InstallProjectReceipt(
        project_id=project.id,
        installment_no=int(seq),
        label=(inst.label or '').strip() or f'دفعة {seq}',
        amount=pay_amount,
        received_date=received_date or date.today(),
        payment_method=(payment_method or '').strip() or None,
        status='مستلمة',
        notes=(notes or '').strip() or None,
    )
    assign_organization(receipt)
    db.session.add(receipt)
    sync_install_contract_from_project(project)
    return None


def update_install_contract_installment(
    contract: InstallContract,
    seq: int,
    form,
) -> str | None:
    """تعديل بيانات دفعة مجدولة على عقد التركيب."""
    inst = next(
        (i for i in (contract.installments or []) if int(i.seq or 0) == int(seq)),
        None,
    )
    if not inst:
        return 'الدفعة غير موجودة'

    label = (form.get('label') or '').strip()
    if not label:
        return 'أدخل وصف الدفعة'
    try:
        pct = float(form.get('pct') or 0)
        amount = money_round(form.get('amount') or 0)
    except (TypeError, ValueError):
        return 'المبلغ أو النسبة غير صالحة'
    if amount <= 0:
        return 'أدخل مبلغ الدفعة'

    collected = float(inst.collected_amount or 0)
    if amount < collected:
        return 'مبلغ الدفعة لا يمكن أن يكون أقل من المحصّل'

    due_raw = (form.get('due_date') or '').strip()
    due_date = None
    if due_raw:
        try:
            due_date = datetime.strptime(due_raw, '%Y-%m-%d').date()
        except ValueError:
            return 'تاريخ الاستحقاق غير صالح'

    inst.label = label
    inst.pct = pct
    inst.amount = amount
    inst.due_date = due_date
    inst.notes = (form.get('notes') or '').strip() or None
    if collected >= amount:
        inst.status = 'محصّلة'
    elif collected > 0:
        inst.status = 'جزئية'
    else:
        inst.status = 'مستحقة'

    rows = [
        {'label': i.label, 'pct': float(i.pct or 0)}
        for i in sorted(contract.installments or [], key=lambda x: x.seq or 0)
    ]
    contract.pay_schedule_json = json.dumps(rows, ensure_ascii=False)

    project = contract.project
    if project:
        sync_install_contract_from_project(project)
    return None


def build_install_contract_summary(contract: InstallContract, project: InstallProject | None = None) -> dict:
    """ملخص العقد للعرض في الجدول أو صفحة التفاصيل."""
    if project is None:
        project = contract.project
    sync_install_contract_from_project(project) if project else None

    installments = []
    paid_count = 0
    for inst in sorted(contract.installments or [], key=lambda x: x.seq or 0):
        status = inst.status or 'مستحقة'
        if status == 'محصّلة':
            paid_count += 1
        installments.append({
            'id': inst.id,
            'seq': inst.seq,
            'label': inst.label,
            'pct': inst.pct,
            'amount': float(inst.amount or 0),
            'collected_amount': float(inst.collected_amount or 0),
            'remaining_amount': inst.remaining_amount,
            'status': status,
            'due_date': inst.due_date.isoformat() if inst.due_date else None,
            'notes': inst.notes or '',
        })

    installments_total = len(installments)

    days_total = None
    days_elapsed = None
    if contract.start_date and contract.end_date:
        days_total = (contract.end_date - contract.start_date).days
        days_elapsed = max((date.today() - contract.start_date).days, 0)

    return {
        'contract': contract,
        'project': project,
        'installments': installments,
        'installments_total': installments_total,
        'installments_paid': paid_count,
        'installments_unpaid': max(installments_total - paid_count, 0),
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
    from installation.documents import remove_contract_documents_folder

    contract_id = contract.id
    db.session.delete(contract)
    db.session.flush()
    remove_contract_documents_folder(contract_id)


def _days_left(end_date: date | None) -> int | None:
    if not end_date:
        return None
    return (end_date - date.today()).days


def install_contract_to_js(contract: InstallContract, project: InstallProject | None = None) -> dict:
    if project is None:
        project = contract.project
    if project:
        sync_install_contract_from_project(project)
    customer = contract.customer
    return {
        'id': contract.id,
        'code': contract.code,
        'customer_id': contract.customer_id,
        'customer': customer.name if customer else contract.client_display,
        'customer_name_en': (customer.name_en or '') if customer else '',
        'contract_type': contract.contract_type or 'عقد تركيب',
        'start_date': contract.start_date.isoformat() if contract.start_date else '',
        'end_date': contract.end_date.isoformat() if contract.end_date else '',
        'duration': contract.duration_months or 0,
        'total': float(contract.total or 0),
        'value': float(contract.value or 0),
        'tax_pct': float(contract.tax_pct or 15),
        'tax_amount': float(contract.tax_amount or 0),
        'collected_amount': float(contract.collected_amount or 0),
        'remaining_amount': float(contract.remaining_amount or 0),
        'progress_pct': int(contract.progress_pct or 0),
        'status': contract.status or 'نشط',
        'notes': contract.notes or '',
        'project_id': project.id if project else None,
        'project_code': project.code if project else '',
        'project_status': project.status if project else '',
        'days_left': _days_left(contract.end_date),
        'quotation_id': contract.quotation_id,
        'quotation_code': contract.quotation.code if contract.quotation else '',
        'installments_total': len(contract.installments or []),
        'installments_paid': sum(
            1 for inst in (contract.installments or []) if (inst.status or '') == 'محصّلة'
        ),
        'installments': [
            {
                'seq': inst.seq,
                'label': inst.label or '',
                'pct': float(inst.pct or 0),
                'amount': float(inst.amount or 0),
                'collected_amount': float(inst.collected_amount or 0),
                'status': inst.status or 'مستحقة',
            }
            for inst in sorted(contract.installments or [], key=lambda x: x.seq or 0)
        ],
    }


def customer_js_dict(customer) -> dict:
    return {
        'id': customer.id,
        'name': customer.name,
        'code': customer.code,
        'city': customer.city or '',
        'phone': customer.phone or '',
        'status': customer.status or 'نشط',
    }


def project_js_dict(project: InstallProject) -> dict:
    return {
        'id': project.id,
        'code': project.code,
        'title': project.title or '',
        'customer_id': project.customer_id,
        'status': project.status or '',
        'has_contract': contract_for_project(project) is not None,
        'accepted_quotation_id': project.accepted_quotation_id,
    }


def quotation_js_dict(quotation: InstallQuotation) -> dict:
    before = float(quotation.before_tax or 0)
    vat = float(quotation.vat_amount or 0)
    total = float(quotation.grand_total or 0)
    tax_pct = 15.0
    if before:
        tax_pct = money_round((vat / before) * 100.0)
    items = quotation.payment_items()
    return {
        'id': quotation.id,
        'code': quotation.code,
        'project_id': quotation.project_id,
        'customer_id': quotation.customer_id,
        'status': quotation.status or '',
        'quote_type': quotation.quote_type or 'new',
        'contract_type': 'عقد تحديث' if (quotation.quote_type or '') == 'upgrade' else 'عقد تركيب',
        'value': before,
        'tax_pct': tax_pct,
        'tax_amount': vat,
        'total': total,
        'installments': [
            {
                'label': it.get('label') or f'دفعة {i + 1}',
                'pct': float(it.get('pct') or 0),
                'amount': float(it.get('amount') or 0),
                'key': it.get('key') or '',
            }
            for i, it in enumerate(items)
        ],
    }


def parse_installments_payload(form, total: float, quotation: InstallQuotation | None = None) -> tuple[list[dict] | None, str | None]:
    raw = (form.get('installments_json') or '').strip()
    rows: list[dict] = []
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None, 'بيانات الدفعات غير صالحة'
        if not isinstance(data, list) or not data:
            return None, 'أدخل دفعة واحدة على الأقل'
        for i, row in enumerate(data, start=1):
            if not isinstance(row, dict):
                continue
            label = (row.get('label') or '').strip() or f'دفعة {i}'
            try:
                pct = float(row.get('pct') or 0)
                amount = money_round(row.get('amount') or 0)
            except (TypeError, ValueError):
                return None, 'قيمة الدفعات غير صالحة'
            if amount <= 0 and pct <= 0:
                continue
            if amount <= 0 and total > 0 and pct > 0:
                amount = money_round(total * pct / 100.0)
            rows.append({'label': label, 'pct': pct, 'amount': amount})
    elif quotation:
        for it in quotation.payment_items():
            rows.append({
                'label': it.get('label') or 'دفعة',
                'pct': float(it.get('pct') or 0),
                'amount': float(it.get('amount') or 0),
            })
    else:
        rows = [{'label': 'دفعة واحدة', 'pct': 100.0, 'amount': money_round(total)}]

    if not rows:
        return None, 'أدخل دفعة واحدة على الأقل'

    if total > 0:
        amount_sum = money_round(sum(float(r['amount'] or 0) for r in rows))
        if abs(amount_sum - total) > 1.0:
            pct_sum = sum(float(r.get('pct') or 0) for r in rows)
            if pct_sum > 0:
                for r in rows:
                    if float(r.get('amount') or 0) <= 0:
                        r['amount'] = money_round(total * float(r['pct'] or 0) / pct_sum)
                amount_sum = money_round(sum(float(r['amount'] or 0) for r in rows))
            if abs(amount_sum - total) > 1.0:
                rows[-1]['amount'] = money_round(max(float(rows[-1]['amount'] or 0) + (total - amount_sum), 0))
    return rows, None


def _replace_contract_installments(contract: InstallContract, rows: list[dict]) -> None:
    old_collected: dict[int, float] = {}
    for inst in list(contract.installments or []):
        old_collected[int(inst.seq or 0)] = float(inst.collected_amount or 0)
        db.session.delete(inst)
    db.session.flush()
    for seq, row in enumerate(rows, start=1):
        amt = money_round(row.get('amount') or 0)
        collected = min(old_collected.get(seq, 0.0), amt)
        if collected >= amt and amt > 0:
            status = 'محصّلة'
        elif collected > 0:
            status = 'جزئية'
        else:
            status = 'مستحقة'
        inst = InstallContractInstallment(
            contract_id=contract.id,
            seq=seq,
            label=(row.get('label') or '').strip() or f'دفعة {seq}',
            pct=float(row.get('pct') or 0),
            amount=amt,
            collected_amount=collected,
            status=status,
        )
        assign_organization(inst)
        db.session.add(inst)


def _schedule_json_from_rows(rows: list[dict]) -> str:
    return json.dumps(
        [{'label': r['label'], 'pct': float(r.get('pct') or 0)} for r in rows],
        ensure_ascii=False,
    )


def parse_install_contract_form(form) -> tuple[dict | None, str | None]:
    customer_raw = (form.get('customer_id') or '').strip()
    if not customer_raw:
        return None, 'اختر العميل'
    try:
        customer_id = int(customer_raw)
    except ValueError:
        return None, 'العميل غير صالح'

    contract_type = (form.get('contract_type') or 'عقد تركيب').strip()
    if contract_type not in ('عقد تركيب', 'عقد تحديث'):
        contract_type = 'عقد تركيب'

    try:
        value = money_round(form.get('value') or 0)
        tax_pct = float(form.get('tax_pct') or 15)
        tax_amount = money_round(form.get('tax_amount') or 0)
        total = money_round(form.get('total') or 0)
    except (TypeError, ValueError):
        return None, 'قيمة العقد غير صالحة'

    if total <= 0:
        return None, 'أدخل قيمة العقد'

    start_raw = (form.get('start_date') or '').strip()
    end_raw = (form.get('end_date') or '').strip()
    duration_raw = (form.get('duration_months') or '').strip()
    try:
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else date.today()
    except ValueError:
        return None, 'تاريخ البداية غير صالح'

    duration_months = 12
    if duration_raw:
        try:
            duration_months = int(duration_raw)
        except ValueError:
            return None, 'مدة العقد غير صالحة'
    end_date = None
    if end_raw:
        try:
            end_date = datetime.strptime(end_raw, '%Y-%m-%d').date()
        except ValueError:
            return None, 'تاريخ النهاية غير صالح'
    elif duration_months:
        end_date = add_months(start_date, duration_months)

    status = (form.get('status') or 'نشط').strip()
    if status not in INSTALL_CONTRACT_STATUSES:
        status = 'نشط'

    project_id = None
    project_raw = (form.get('project_id') or '').strip()
    if project_raw:
        try:
            project_id = int(project_raw)
        except ValueError:
            return None, 'المشروع غير صالح'

    quotation_id = None
    quotation_raw = (form.get('quotation_id') or '').strip()
    if quotation_raw:
        try:
            quotation_id = int(quotation_raw)
        except ValueError:
            return None, 'عرض السعر غير صالح'

    return {
        'customer_id': customer_id,
        'project_id': project_id,
        'quotation_id': quotation_id,
        'contract_type': contract_type,
        'start_date': start_date,
        'end_date': end_date,
        'duration_months': duration_months,
        'value': value,
        'tax_pct': tax_pct,
        'tax_amount': tax_amount if tax_amount else money_round(max(total - value, 0)),
        'total': total,
        'status': status,
        'notes': (form.get('notes') or '').strip() or None,
    }, None


def _resolve_project_for_contract(customer_id: int, project_id: int | None, *, next_project_code_fn, contract_code: str):
    if project_id:
        project = tenant_query(InstallProject).filter_by(id=project_id).first()
        if not project:
            raise ValueError('المشروع غير موجود')
        if project.customer_id and int(project.customer_id) != int(customer_id):
            raise ValueError('المشروع غير موجود لهذا العميل')
        if contract_for_project(project):
            raise ValueError('يوجد عقد مسبقاً على هذا المشروع')
        return project
    project = InstallProject(
        code=next_project_code_fn(InstallProject, 'PRJ-', 4),
        title=f'مشروع {contract_code}',
        status='عقد',
        customer_id=customer_id,
    )
    assign_organization(project)
    db.session.add(project)
    db.session.flush()
    return project


def create_manual_install_contract(form, *, next_code_fn, next_project_code_fn) -> InstallContract:
    ensure_install_contract_schema()
    fields, err = parse_install_contract_form(form)
    if err:
        raise ValueError(err)

    quotation = None
    if fields.get('quotation_id'):
        quotation = tenant_query(InstallQuotation).filter_by(id=fields['quotation_id']).first()
        if not quotation:
            raise ValueError('عرض السعر غير موجود')
        if quotation.customer_id and quotation.customer_id != fields['customer_id']:
            raise ValueError('عرض السعر لا يخص هذا العميل')
        if fields.get('project_id') and quotation.project_id != fields['project_id']:
            raise ValueError('عرض السعر لا يخص المشروع المختار')
        if not fields.get('project_id'):
            fields['project_id'] = quotation.project_id

    rows, ierr = parse_installments_payload(form, fields['total'], quotation)
    if ierr:
        raise ValueError(ierr)

    prefix = contract_prefix_for_type(fields['contract_type'])
    code = next_code_fn(InstallContract, prefix, digits=CONTRACT_CODE_DIGITS)
    project = _resolve_project_for_contract(
        fields['customer_id'],
        fields.get('project_id'),
        next_project_code_fn=next_project_code_fn,
        contract_code=code,
    )

    contract = InstallContract(
        code=code,
        project_id=project.id,
        quotation_id=quotation.id if quotation else None,
        customer_id=fields['customer_id'],
        contract_type=fields['contract_type'],
        start_date=fields['start_date'],
        end_date=fields['end_date'],
        duration_months=fields['duration_months'],
        value=fields['value'],
        tax_pct=fields['tax_pct'],
        tax_amount=fields['tax_amount'],
        total=fields['total'],
        pay_schedule_json=quotation.pay_schedule_json if quotation else _schedule_json_from_rows(rows),
        progress_pct=0,
        collected_amount=0,
        remaining_amount=fields['total'],
        status=fields['status'],
        signed_at=datetime.utcnow(),
        notes=fields['notes'] or (f'من عرض السعر {quotation.code}' if quotation else None),
    )
    assign_organization(contract)
    db.session.add(contract)
    db.session.flush()

    _replace_contract_installments(contract, rows)
    return contract


def apply_install_contract_form(contract: InstallContract, form) -> str | None:
    fields, err = parse_install_contract_form(form)
    if err:
        return err
    if fields['customer_id'] != contract.customer_id:
        return 'لا يمكن تغيير العميل — أنشئ عقداً جديداً'

    quotation = None
    if fields.get('quotation_id'):
        quotation = tenant_query(InstallQuotation).filter_by(id=fields['quotation_id']).first()
        if not quotation:
            return 'عرض السعر غير موجود'
        if quotation.customer_id and quotation.customer_id != fields['customer_id']:
            return 'عرض السعر لا يخص هذا العميل'
        if contract.project_id and quotation.project_id != contract.project_id:
            return 'عرض السعر لا يخص مشروع هذا العقد'

    rows, ierr = parse_installments_payload(form, fields['total'], quotation)
    if ierr:
        return ierr

    contract.contract_type = fields['contract_type']
    contract.start_date = fields['start_date']
    contract.end_date = fields['end_date']
    contract.duration_months = fields['duration_months']
    contract.value = fields['value']
    contract.tax_pct = fields['tax_pct']
    contract.tax_amount = fields['tax_amount']
    contract.total = fields['total']
    contract.status = fields['status']
    contract.notes = fields['notes']
    if quotation:
        contract.quotation_id = quotation.id
        contract.pay_schedule_json = quotation.pay_schedule_json
    else:
        contract.pay_schedule_json = _schedule_json_from_rows(rows)
    contract.remaining_amount = round(max(float(contract.total or 0) - float(contract.collected_amount or 0), 0), 2)
    _replace_contract_installments(contract, rows)
    return None
