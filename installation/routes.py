"""مسارات موديول التركيب — prefix: /installation"""

import json
import re
from datetime import datetime, date

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from models import db, Customer, Contract
from installation.models import (
    InstallLead,
    InstallProject,
    InstallQuotation,
    InstallQuotationLine,
    InstallTimelineStep,
    InstallProjectCostItem,
    InstallProjectReceipt,
    LEAD_STATUSES,
    LEAD_SOURCES,
    PROJECT_STATUSES,
    QUOTE_STATUSES,
    TIMELINE_STEP_STATUSES,
    COST_CATEGORIES,
    COST_PAYMENT_STATUSES,
    RECEIPT_STATUSES,
)
from installation.timeline import (
    create_execution_timeline,
    sync_project_status_from_timeline,
    timeline_progress,
    steps_by_group,
    active_timeline_steps,
    advance_next_step,
    is_execution_complete,
    payment_totals,
    client_payment_amount,
    phase_track,
    current_timeline_step,
    upcoming_timeline_steps,
    step_amount_pct,
    calculate_step_amount,
    step_has_auto_amount,
    apply_auto_amount,
    sync_project_auto_amounts,
    sync_timeline_from_templates,
    sync_step_timeline_dates,
    chain_step_dates_after_edit,
)
from installation.catalog import (
    MACHINE_ORIGINS,
    MACHINE_BRANDS,
    CONTROL_PANEL_BRANDS,
    origins_for_js,
)
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query

install_bp = Blueprint('installation', __name__, url_prefix='/installation')

_schema_ensured = False


@install_bp.before_request
def _ensure_install_schema():
    """ضمان أعمدة/جداول/قيود التركيب قبل أي صفحة (يمنع 500 على الفرص)."""
    global _schema_ensured
    if _schema_ensured:
        return
    try:
        from installation.project_card import ensure_project_card_schema
        from installation.schema import ensure_install_tenant_uniques
        ensure_project_card_schema()
        ensure_install_tenant_uniques()
        _schema_ensured = True
    except Exception:
        db.session.rollback()


def _next_code(model, prefix, digits=4):
    max_num = 0
    pattern = re.compile(r'^' + re.escape(prefix) + r'(\d+)$')
    for (code,) in tenant_query(model).with_entities(model.code).all():
        if not code:
            continue
        m = pattern.match(str(code).strip())
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f'{prefix}{str(max_num + 1).zfill(digits)}'


def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(str(val)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_datetime(val):
    d = _parse_date(val)
    if not d:
        return None
    return datetime.combine(d, datetime.min.time())


def _apply_step_dates(step, status, old_status, form):
    """تطبيق تواريخ البدء والاكتمال من النموذج أو من منطق الانتقال."""
    started_raw = (form.get('started_date') or '').strip()
    completed_raw = (form.get('completed_date') or '').strip()
    if started_raw:
        step.started_at = _parse_datetime(started_raw)
    if status == 'مكتمل':
        if completed_raw:
            step.completed_at = _parse_datetime(completed_raw)
        elif old_status != 'مكتمل':
            step.completed_at = datetime.utcnow()
    elif status in ('قادم', 'جاري', 'متأخر'):
        if form.get('clear_completed'):
            step.completed_at = None
        if status == 'جاري' and not step.started_at and not started_raw:
            step.started_at = datetime.utcnow()


def _dim_to_cm(val):
    """عرض المقاس بالسم — يدعم القيم النصية والبيانات القديمة بالمليمتر."""
    if val is None or val == '':
        return None
    try:
        n = float(str(val).replace(',', '').strip())
    except (TypeError, ValueError):
        return str(val)
    if n > 500:
        n = n / 10
    return int(round(n))


def _customer_address(customer):
    parts = [p for p in (customer.district, customer.city) if p]
    return ' — '.join(parts) if parts else (customer.address or '')


def _customer_to_js(customer):
    return {
        'id': customer.id,
        'code': customer.code,
        'name': customer.name,
        'phone': customer.phone or customer.phone2 or '',
        'email': customer.email or '',
        'address': _customer_address(customer),
        'city': customer.city or '',
        'district': customer.district or '',
    }


def _active_customers():
    return tenant_query(Customer).filter(
        Customer.status != 'غير نشط'
    ).order_by(Customer.name).all()


def _customer_snapshot(customer):
    return {
        'customer_id': customer.id,
        'client_name': customer.name,
        'client_phone': customer.phone or customer.phone2 or '',
        'client_address': _customer_address(customer),
    }


def _project_prefill(project):
    if project.customer:
        return _customer_snapshot(project.customer)
    lead = project.lead
    addr = ''
    if lead:
        parts = [p for p in (lead.district, lead.city) if p]
        addr = ' — '.join(parts) if parts else (lead.address or '')
    return {
        'customer_id': project.customer_id,
        'client_name': project.client_display,
        'client_phone': lead.phone if lead else '',
        'client_address': addr,
    }


def _latest_editable_quotation(project):
    """آخر عرض قابل للتعديل (غير مقبول/مرفوض)."""
    return (
        tenant_query(InstallQuotation).filter_by(project_id=project.id)
        .filter(InstallQuotation.status.notin_(('مقبول', 'مرفوض')))
        .order_by(InstallQuotation.updated_at.desc(), InstallQuotation.id.desc())
        .first()
    )


def _quotation_to_dict(q):
    spec = q.spec()
    return {
        'id': q.id,
        'code': q.code,
        'customer_id': q.customer_id,
        'quote_type': q.quote_type,
        'status': q.status,
        'client_name': q.client_name,
        'client_phone': q.client_phone,
        'client_address': q.client_address,
        'valid_days': q.valid_days,
        'labor': q.labor,
        'transport': q.transport,
        'other_costs': q.other_costs,
        'profit_pct': q.profit_pct,
        'grand_total': q.grand_total,
        'pay_advance_pct': q.pay_advance_pct if q.pay_advance_pct is not None else 50,
        'pay_supply_pct': q.pay_supply_pct if q.pay_supply_pct is not None else 40,
        'pay_final_pct': q.pay_final_pct if q.pay_final_pct is not None else 10,
        'spec': spec,
        'lines': [
            {
                'stage': ln.stage,
                'name': ln.name,
                'unit': ln.unit,
                'qty': ln.qty,
                'price': ln.unit_price,
            }
            for ln in q.lines
        ],
    }


@install_bp.route('/')
def index():
    lead_count = tenant_query(InstallLead).count()
    project_count = tenant_query(InstallProject).count()
    active_leads = tenant_query(InstallLead).filter(
        InstallLead.status.notin_(('ملغي', 'تم تحويله لمشروع'))
    ).count()
    recent_projects = tenant_query(InstallProject).order_by(InstallProject.created_at.desc()).limit(5).all()
    return render_template(
        'installation/index.html',
        lead_count=lead_count,
        project_count=project_count,
        active_leads=active_leads,
        recent_projects=recent_projects,
        page_title='مشاريع التركيب',
    )


@install_bp.route('/projects')
def projects_list():
    projects = tenant_query(InstallProject).order_by(InstallProject.created_at.desc()).all()
    return render_template(
        'installation/projects.html',
        projects=projects,
        statuses=PROJECT_STATUSES,
        page_title='مشاريع التركيب',
    )


@install_bp.route('/projects/<int:project_id>')
def project_detail(project_id):
    from installation.project_card import build_project_card, ensure_project_card_schema

    project = tenant_get_or_404(InstallProject, project_id)
    quotations = project.quotations.order_by(InstallQuotation.created_at.desc()).all()
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    progress = timeline_progress(steps) if project.execution_active else 0
    execution_complete = is_execution_complete(steps) if project.execution_active else False
    latest_draft = _latest_editable_quotation(project) if not project.execution_active else None
    card = {
        'contract_value': 0,
        'received': 0,
        'pending_receipts': 0,
        'client_remaining': 0,
        'total_cost': 0,
        'profit': 0,
        'receipts': [],
        'cost_groups': [],
        'sheet_rows': [],
        'cost_count': 0,
        'quote_code': None,
        'contract': None,
        'contract_code': None,
        'value_source': '—',
        'schema_error': None,
    }
    try:
        ensure_project_card_schema()
        card = build_project_card(project)
        card['schema_error'] = None
    except Exception as exc:
        db.session.rollback()
        card['schema_error'] = str(exc)

    customer_contracts = []
    if project.customer_id or (project.customer and project.customer.id):
        from contract_codes import is_installation_contract_type

        cid = project.customer_id or project.customer.id
        raw_contracts = (
            tenant_query(Contract)
            .filter_by(customer_id=cid)
            .order_by(Contract.created_at.desc())
            .limit(100)
            .all()
        )
        customer_contracts = [
            c for c in raw_contracts
            if is_installation_contract_type(c.contract_type)
        ][:50]

    return render_template(
        'installation/project_detail.html',
        project=project,
        quotations=quotations,
        latest_draft=latest_draft,
        execution_progress=progress,
        execution_complete=execution_complete,
        quote_statuses=QUOTE_STATUSES,
        card=card,
        customer_contracts=customer_contracts,
        cost_categories=COST_CATEGORIES,
        cost_payment_statuses=COST_PAYMENT_STATUSES,
        receipt_statuses=RECEIPT_STATUSES,
        today=date.today().isoformat(),
        page_title=f'مشروع {project.code}',
    )


@install_bp.route('/projects/<int:project_id>/card/value', methods=['POST'])
def project_card_set_value(project_id):
    from installation.project_card import ensure_project_card_schema

    ensure_project_card_schema()
    project = tenant_get_or_404(InstallProject, project_id)
    raw = (request.form.get('contract_value') or '').strip()
    if not raw:
        project.contract_value = None
    else:
        try:
            project.contract_value = float(raw)
        except ValueError:
            flash('قيمة المشروع غير صحيحة', 'error')
            return redirect(url_for('installation.project_detail', project_id=project.id))
    db.session.commit()
    flash('تم تحديث قيمة المشروع', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')


@install_bp.route('/projects/<int:project_id>/card/link-contract', methods=['POST'])
def project_card_link_contract(project_id):
    """ربط كارت المشروع بعقد LiftCore وحفظ القيمة من العقد إن طُلب."""
    from installation.project_card import ensure_project_card_schema

    ensure_project_card_schema()
    project = tenant_get_or_404(InstallProject, project_id)
    raw_id = (request.form.get('contract_id') or '').strip()
    sync_value = (request.form.get('sync_value') or '').strip() in ('1', 'on', 'true', 'yes')

    if not raw_id:
        project.contract_id = None
        db.session.commit()
        flash('تم فك ربط العقد عن كارت المشروع', 'success')
        return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')

    try:
        cid = int(raw_id)
    except ValueError:
        flash('عقد غير صالح', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')

    contract = tenant_query(Contract).filter_by(id=cid).first()
    if not contract:
        flash('العقد غير موجود', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')

    from contract_codes import is_installation_contract_type
    if not is_installation_contract_type(contract.contract_type):
        flash('يُسمح بالربط بعقود التركيب أو التحديث فقط (وليس عقود الصيانة)', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')

    if project.customer_id and contract.customer_id != project.customer_id:
        flash('العقد لا يخص عميل هذا المشروع', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')

    project.contract_id = contract.id
    if not project.customer_id:
        project.customer_id = contract.customer_id
    if sync_value:
        amount = float(contract.total or contract.value or 0)
        if amount > 0:
            project.contract_value = amount
    db.session.commit()
    flash(f'تم ربط الكارت بالعقد {contract.code}', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')


@install_bp.route('/projects/<int:project_id>/card/print')
def project_card_print(project_id):
    """صفحة طباعة كارت المشروع."""
    from installation.project_card import build_project_card, ensure_project_card_schema

    ensure_project_card_schema()
    project = tenant_get_or_404(InstallProject, project_id)
    card = build_project_card(project)
    settings = None
    try:
        from models import Settings
        settings = tenant_query(Settings).first()
    except Exception:
        db.session.rollback()
    return render_template(
        'installation/project_card_print.html',
        project=project,
        card=card,
        settings=settings,
        print_date=date.today(),
        page_title=f'كارت مشروع {project.code}',
    )


@install_bp.route('/projects/<int:project_id>/card/costs/add', methods=['POST'])
def project_card_cost_add(project_id):
    from installation.project_card import ensure_project_card_schema

    ensure_project_card_schema()
    project = tenant_get_or_404(InstallProject, project_id)
    title = (request.form.get('title') or '').strip()
    category = (request.form.get('category') or 'أخرى').strip()
    if category not in COST_CATEGORIES:
        category = 'أخرى'
    try:
        amount = float(request.form.get('amount') or 0)
    except ValueError:
        amount = 0
    date_raw = (request.form.get('cost_date') or '').strip()
    try:
        cost_date = datetime.strptime(date_raw, '%Y-%m-%d').date() if date_raw else date.today()
    except ValueError:
        cost_date = date.today()
    inst_raw = (request.form.get('installment_no') or '').strip()
    installment_no = int(inst_raw) if inst_raw.isdigit() else None
    pay_status = (request.form.get('payment_status') or '').strip()
    if pay_status not in COST_PAYMENT_STATUSES:
        pay_status = 'غير مدفوعة' if installment_no or category == 'عمالة' else None
    if not title:
        if category == 'عمالة' and installment_no:
            from installation.project_card import installment_label
            title = installment_label(installment_no)
        elif installment_no:
            title = f'دفعة {installment_no}'
        else:
            title = category
    if amount <= 0:
        flash('أدخل مبلغاً أكبر من صفر', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')
    item = InstallProjectCostItem(
        project_id=project.id,
        category=category,
        title=title,
        amount=amount,
        cost_date=cost_date,
        installment_no=installment_no,
        payment_status=pay_status,
        notes=(request.form.get('notes') or '').strip() or None,
    )
    assign_organization(item)
    db.session.add(item)
    db.session.commit()
    flash('تمت إضافة بند التكلفة', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')


@install_bp.route('/projects/<int:project_id>/card/costs/<int:item_id>/status', methods=['POST'])
def project_card_cost_status(project_id, item_id):
    from installation.project_card import ensure_project_card_schema

    ensure_project_card_schema()
    project = tenant_get_or_404(InstallProject, project_id)
    item = tenant_query(InstallProjectCostItem).filter_by(id=item_id, project_id=project.id).first_or_404()
    status = (request.form.get('payment_status') or '').strip()
    if status not in COST_PAYMENT_STATUSES:
        flash('حالة السداد غير صحيحة', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')
    item.payment_status = status
    db.session.commit()
    flash('تم تحديث حالة الدفعة', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')


@install_bp.route('/projects/<int:project_id>/card/costs/<int:item_id>/delete', methods=['POST'])
def project_card_cost_delete(project_id, item_id):
    project = tenant_get_or_404(InstallProject, project_id)
    item = tenant_query(InstallProjectCostItem).filter_by(id=item_id, project_id=project.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash('تم حذف بند التكلفة', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')


@install_bp.route('/projects/<int:project_id>/card/receipts/add', methods=['POST'])
def project_card_receipt_add(project_id):
    from installation.project_card import ensure_project_card_schema

    ensure_project_card_schema()
    project = tenant_get_or_404(InstallProject, project_id)
    try:
        amount = float(request.form.get('amount') or 0)
    except ValueError:
        amount = 0
    inst_raw = (request.form.get('installment_no') or '').strip()
    installment_no = int(inst_raw) if inst_raw.isdigit() else (len(project.receipts) + 1)
    if amount <= 0:
        flash('أدخل مبلغ دفعة أكبر من صفر', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')
    date_raw = (request.form.get('received_date') or '').strip()
    try:
        received_date = datetime.strptime(date_raw, '%Y-%m-%d').date() if date_raw else date.today()
    except ValueError:
        received_date = date.today()
    status = (request.form.get('status') or 'مستلمة').strip()
    if status not in RECEIPT_STATUSES:
        status = 'مستلمة'
    label = (request.form.get('label') or '').strip() or f'دفعة رقم {installment_no}'
    receipt = InstallProjectReceipt(
        project_id=project.id,
        installment_no=installment_no,
        label=label,
        amount=amount,
        received_date=received_date,
        payment_method=(request.form.get('payment_method') or '').strip() or None,
        status=status,
        notes=(request.form.get('notes') or '').strip() or None,
    )
    assign_organization(receipt)
    db.session.add(receipt)
    db.session.commit()
    flash(f'تم تسجيل {label}', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')


@install_bp.route('/projects/<int:project_id>/card/receipts/<int:receipt_id>/delete', methods=['POST'])
def project_card_receipt_delete(project_id, receipt_id):
    project = tenant_get_or_404(InstallProject, project_id)
    receipt = tenant_query(InstallProjectReceipt).filter_by(id=receipt_id, project_id=project.id).first_or_404()
    db.session.delete(receipt)
    db.session.commit()
    flash('تم حذف الدفعة', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id) + '#project-card')


@install_bp.route('/projects/<int:project_id>/quote')
def project_quote(project_id):
    project = tenant_get_or_404(InstallProject, project_id)
    if project.execution_active:
        flash('التنفيذ بدأ — لا يمكن تعديل التسعير. افتح جدول التنفيذ أو التقرير.', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    quotation_id = request.args.get('quotation_id', type=int)
    force_new = request.args.get('new', type=int) == 1
    if not quotation_id and not force_new:
        latest = _latest_editable_quotation(project)
        if latest:
            return redirect(url_for(
                'installation.project_quote',
                project_id=project.id,
                quotation_id=latest.id,
            ))
    quotation = None
    saved = None
    if quotation_id:
        quotation = tenant_query(InstallQuotation).filter_by(id=quotation_id, project_id=project.id).first_or_404()
        if quotation.status == 'مقبول':
            flash('هذا العرض مقبول — افتح صفحة التنفيذ', 'error')
            return redirect(url_for('installation.project_execution', project_id=project.id))
        saved = _quotation_to_dict(quotation)
    next_code = quotation.code if quotation else _next_code(InstallQuotation, 'Q-', 4)
    customers = _active_customers()
    default_customer_id = None
    if quotation and quotation.customer_id:
        default_customer_id = quotation.customer_id
    elif project.customer_id:
        default_customer_id = project.customer_id
    return render_template(
        'installation/quote.html',
        project=project,
        quotation=quotation,
        next_quote_code=next_code,
        prefill=_project_prefill(project),
        saved_json=json.dumps(saved, ensure_ascii=False) if saved else 'null',
        customers_js=[_customer_to_js(c) for c in customers],
        machine_origins=MACHINE_ORIGINS,
        machine_brands=MACHINE_BRANDS,
        panel_brands=CONTROL_PANEL_BRANDS,
        default_customer_id=default_customer_id,
        page_title=f'تسعير — {project.code}',
    )


@install_bp.route('/projects/<int:project_id>/quote/save', methods=['POST'])
def project_quote_save(project_id):
    project = tenant_get_or_404(InstallProject, project_id)
    data = request.get_json(silent=True) or {}
    lines = data.get('lines') or []
    if not lines:
        return jsonify({'ok': False, 'error': 'قائمة البنود فارغة'}), 400

    customer_id = data.get('customer_id')
    if not customer_id:
        return jsonify({'ok': False, 'error': 'اختر عميلاً مسجّلاً من قائمة العملاء'}), 400

    customer = tenant_query(Customer).filter_by(id=customer_id).first()
    if not customer:
        return jsonify({'ok': False, 'error': 'العميل غير موجود — أضفه من صفحة العملاء أولاً'}), 400

    snapshot = _customer_snapshot(customer)
    project.customer_id = customer.id

    quotation_id = data.get('quotation_id')
    if quotation_id:
        q = tenant_query(InstallQuotation).filter_by(id=quotation_id, project_id=project.id).first()
        if not q:
            return jsonify({'ok': False, 'error': 'عرض السعر غير موجود'}), 404
        for ln in list(q.lines):
            db.session.delete(ln)
    else:
        q = InstallQuotation(
            code=_next_code(InstallQuotation, 'Q-', 4),
            project_id=project.id,
        )
        assign_organization(q)
        db.session.add(q)

    q.customer_id = customer.id
    q.quote_type = data.get('quote_type') or 'new'
    q.client_name = snapshot['client_name']
    q.client_phone = snapshot['client_phone']
    q.client_address = snapshot['client_address']
    q.valid_days = int(data.get('valid_days') or 30)
    q.spec_json = json.dumps(data.get('spec') or {}, ensure_ascii=False)
    q.labor = round(float(data.get('labor') or 0))
    q.transport = round(float(data.get('transport') or 0))
    q.other_costs = round(float(data.get('other_costs') or 0))
    q.profit_pct = float(data.get('profit_pct') or 20)
    pay_adv = float(data.get('pay_advance_pct') if data.get('pay_advance_pct') is not None else 50)
    pay_sup = float(data.get('pay_supply_pct') if data.get('pay_supply_pct') is not None else 40)
    pay_fin = float(data.get('pay_final_pct') if data.get('pay_final_pct') is not None else 10)
    if pay_adv < 0 or pay_sup < 0 or pay_fin < 0:
        return jsonify({'ok': False, 'error': 'نسب الدفعات لا يمكن أن تكون سالبة'}), 400
    if round(pay_adv + pay_sup + pay_fin, 2) != 100:
        return jsonify({'ok': False, 'error': 'مجموع نسب الدفعات (مقدمة + توريد + نهائية) يجب أن يساوي 100%'}), 400
    q.pay_advance_pct = pay_adv
    q.pay_supply_pct = pay_sup
    q.pay_final_pct = pay_fin
    if q.status != 'مقبول':
        q.status = 'مسودة'

    materials = 0.0
    for i, row in enumerate(lines):
        qty = round(float(row.get('qty') or 0))
        price = round(float(row.get('price') or 0))
        materials += qty * price
        line = InstallQuotationLine(
            quotation=q,
            stage=(row.get('stage') or '').strip(),
            name=(row.get('name') or 'بند').strip(),
            unit=(row.get('unit') or '—').strip(),
            qty=qty,
            unit_price=price,
            sort_order=i,
        )
        assign_organization(line)
        db.session.add(line)

    cost = materials + q.labor + q.transport + q.other_costs
    profit = cost * q.profit_pct / 100
    before = cost + profit
    vat = before * 0.15
    q.materials_total = int(round(round(materials) / 10.0) * 10)
    q.cost_total = int(round(round(cost) / 10.0) * 10)
    q.profit_amount = int(round(round(profit) / 10.0) * 10)
    q.before_tax = int(round(round(before) / 10.0) * 10)
    q.vat_amount = int(round(round(vat) / 10.0) * 10)
    q.grand_total = int(round(round(before + vat) / 10.0) * 10)

    if project.status in ('استفسار', 'معاينة', 'هندسة'):
        project.status = 'تسعير'
    db.session.commit()

    return jsonify({
        'ok': True,
        'id': q.id,
        'code': q.code,
        'print_url': url_for('installation.quote_print', quotation_id=q.id),
    })


@install_bp.route('/projects/<int:project_id>/quotes/<int:quotation_id>/send', methods=['POST'])
def quote_send(project_id, quotation_id):
    project = tenant_get_or_404(InstallProject, project_id)
    q = tenant_query(InstallQuotation).filter_by(id=quotation_id, project_id=project.id).first_or_404()
    if q.status == 'مقبول':
        flash('لا يمكن تعديل عرض مقبول', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    q.status = 'مُرسل'
    if project.status in ('استفسار', 'معاينة', 'هندسة', 'تسعير'):
        project.status = 'عرض سعر'
    db.session.commit()
    flash(f'تم تسجيل إرسال العرض {q.code} للعميل', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id))


@install_bp.route('/projects/<int:project_id>/quotes/<int:quotation_id>/cancel', methods=['POST'])
def quote_cancel(project_id, quotation_id):
    project = tenant_get_or_404(InstallProject, project_id)
    q = tenant_query(InstallQuotation).filter_by(id=quotation_id, project_id=project.id).first_or_404()
    if q.status == 'مقبول':
        flash('لا يمكن إلغاء عرض مقبول — المشروع في مرحلة التنفيذ', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    if q.status == 'مرفوض':
        flash('هذا العرض ملغى مسبقاً', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    if project.execution_active:
        flash('لا يمكن إلغاء العروض بعد بدء التنفيذ', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    q.status = 'مرفوض'
    db.session.commit()
    flash(f'تم إلغاء العرض {q.code}', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id))


@install_bp.route('/projects/<int:project_id>/quotes/<int:quotation_id>/approve', methods=['POST'])
def quote_approve(project_id, quotation_id):
    project = tenant_get_or_404(InstallProject, project_id)
    q = tenant_query(InstallQuotation).filter_by(id=quotation_id, project_id=project.id).first_or_404()
    if not project.customer_id and not q.customer_id:
        flash('اربط المشروع بعميل مسجّل قبل قبول العرض', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    if project.accepted_quotation_id and project.accepted_quotation_id != q.id:
        flash('يوجد عرض مقبول آخر على هذا المشروع', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    q.status = 'مقبول'
    q.approved_at = datetime.utcnow()
    project.accepted_quotation_id = q.id
    project.execution_started_at = project.execution_started_at or datetime.utcnow()
    project.status = 'عقد'
    if not project.customer_id and q.customer_id:
        project.customer_id = q.customer_id
    create_execution_timeline(project, db.session)
    sync_project_auto_amounts(project, force=True)
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    if steps and steps[0].status == 'قادم':
        steps[0].status = 'جاري'
        steps[0].started_at = project.execution_started_at or datetime.utcnow()
        apply_auto_amount(steps[0], q, force=True)
    db.session.commit()
    flash(f'تم قبول العرض {q.code} — بدأت مرحلة التنفيذ', 'success')
    return redirect(url_for('installation.project_execution', project_id=project.id))


@install_bp.route('/projects/<int:project_id>/execution')
def project_execution(project_id):
    project = tenant_get_or_404(InstallProject, project_id)
    if not project.execution_active:
        flash('ابدأ التنفيذ بقبول عرض سعر من صفحة المشروع', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    changed = sync_timeline_from_templates(project)
    accepted = project.accepted_quotation
    if accepted and accepted.grand_total:
        changed = sync_project_auto_amounts(project, force=True) > 0 or changed
    if changed:
        db.session.commit()
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    active_steps = active_timeline_steps(steps)
    current_step = current_timeline_step(active_steps)
    completed_count = sum(1 for s in steps if s.status == 'مكتمل')
    grand_total = (accepted.grand_total or 0) if accepted else 0
    payments_received = payment_totals(steps, accepted).get('client_paid', 0) if accepted else 0
    auto_amount = None
    if current_step and grand_total:
        pct = step_amount_pct(current_step.step_key, accepted)
        if pct is not None:
            auto_amount = {
                'pct': int(round(pct)),
                'amount': calculate_step_amount(grand_total, current_step.step_key, accepted),
            }
    return render_template(
        'installation/project_execution.html',
        project=project,
        accepted_quote=accepted,
        current_step=current_step,
        auto_amount=auto_amount,
        upcoming_steps=upcoming_timeline_steps(active_steps, current_step),
        phase_track=phase_track(steps),
        progress=timeline_progress(steps),
        completed_count=completed_count,
        total_steps=len(steps),
        remaining_count=len(active_steps),
        payments_received=payments_received,
        step_statuses=TIMELINE_STEP_STATUSES,
        page_title=f'تنفيذ — {project.code}',
    )


@install_bp.route('/projects/<int:project_id>/timeline/<int:step_id>/update', methods=['POST'])
def timeline_step_update(project_id, step_id):
    project = tenant_get_or_404(InstallProject, project_id)
    step = tenant_query(InstallTimelineStep).filter_by(id=step_id, project_id=project.id).first_or_404()
    old_status = step.status
    status = (request.form.get('status') or '').strip()
    if status in TIMELINE_STEP_STATUSES:
        step.status = status
    step.planned_date = _parse_date(request.form.get('planned_date'))
    step.notes = (request.form.get('notes') or '').strip()
    accepted = project.accepted_quotation
    grand_total = (accepted.grand_total or 0) if accepted else 0
    if step_has_auto_amount(step.step_key) and accepted and grand_total:
        step.amount = calculate_step_amount(grand_total, step.step_key, accepted)
    else:
        amount_raw = (request.form.get('amount') or '').strip()
        if amount_raw:
            try:
                step.amount = float(amount_raw.replace(',', ''))
            except ValueError:
                pass
    _apply_step_dates(step, step.status, old_status, request.form)
    if step.status == 'مكتمل' and old_status != 'مكتمل':
        advance_next_step(project, step)
    sync_project_status_from_timeline(project)
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    if is_execution_complete(steps):
        project.status = 'مغلق'
    db.session.commit()
    if is_execution_complete(steps):
        flash('تم إكمال المشروع — يمكنك عرض تقرير الإغلاق', 'success')
        return redirect(url_for('installation.project_report', project_id=project.id))
    flash(f'تم تحديث: {step.title}', 'success')
    return redirect(url_for('installation.project_execution', project_id=project.id))


def _project_report_context(project):
    from installation.catalog import origin_label_from_spec
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    accepted = project.accepted_quotation
    spec = accepted.spec() if accepted else {}
    payments = payment_totals(steps, accepted)
    lines_by_stage = {}
    if accepted:
        for ln in accepted.lines:
            lines_by_stage.setdefault(ln.stage or '—', []).append(ln)
    return {
        'steps': steps,
        'step_groups': steps_by_group(steps),
        'accepted_quote': accepted,
        'spec': spec,
        'dims': {
            'shaft_w': _dim_to_cm(spec.get('shaft_width')),
            'shaft_d': _dim_to_cm(spec.get('shaft_depth')),
            'cabin_w': _dim_to_cm(spec.get('cabin_width')),
            'cabin_d': _dim_to_cm(spec.get('cabin_depth')),
        },
        'origin_label': origin_label_from_spec(spec, 'machine_origin', 'machine_origin_country'),
        'machine_brand': spec.get('machine_brand') or '—',
        'panel_origin_label': origin_label_from_spec(spec, 'panel_origin', 'panel_origin_country'),
        'panel_brand': spec.get('panel_brand') or '—',
        'progress': timeline_progress(steps),
        'is_complete': is_execution_complete(steps),
        'payments': payments,
        'lines_by_stage': lines_by_stage,
        'quotations': project.quotations.order_by(InstallQuotation.created_at.desc()).all(),
        'client_payment_amount': client_payment_amount,
    }


def _handover_context(project):
    from installation.catalog import origin_label_from_spec
    ctx = _project_report_context(project)
    delivery_date = datetime.utcnow().date()
    delivery_notes = ''
    for step in project.timeline_steps:
        if step.step_key == 'client_delivery':
            if step.completed_at:
                delivery_date = step.completed_at.date()
            elif step.planned_date:
                delivery_date = step.planned_date
            delivery_notes = step.notes or ''
            break
    site_address = ''
    if project.customer:
        parts = [p for p in (project.customer.district, project.customer.city, project.customer.address) if p]
        site_address = ' — '.join(parts)
    elif ctx.get('accepted_quote'):
        site_address = ctx['accepted_quote'].client_address or ''
    return {
        **ctx,
        'delivery_date': delivery_date,
        'delivery_notes': delivery_notes,
        'site_address': site_address or '—',
        'customer_code': project.customer.code if project.customer else '—',
        'machine_type_label': (
            'جيرلس MRL' if ctx.get('spec', {}).get('machine') == 'gearless'
            else ('جير بغرفة ماكينة' if ctx.get('spec', {}).get('machine') == 'geared' else '—')
        ),
    }


@install_bp.route('/projects/<int:project_id>/handover')
def project_handover(project_id):
    from installation.handover import HANDOVER_CHECKLIST, HANDOVER_TERMS
    project = tenant_get_or_404(InstallProject, project_id)
    if not project.execution_active or not project.accepted_quotation:
        flash('محضر الاستلام متاح بعد قبول العرض وبدء التنفيذ', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    ctx = _handover_context(project)
    return render_template(
        'installation/delivery_handover.html',
        project=project,
        checklist=HANDOVER_CHECKLIST,
        terms=HANDOVER_TERMS,
        page_title=f'محضر استلام — {project.code}',
        **ctx,
    )


@install_bp.route('/projects/<int:project_id>/timeline/<int:step_id>/edit', methods=['GET', 'POST'])
def timeline_step_edit(project_id, step_id):
    project = tenant_get_or_404(InstallProject, project_id)
    if not project.execution_active:
        flash('التعديل متاح بعد بدء التنفيذ', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    step = tenant_query(InstallTimelineStep).filter_by(id=step_id, project_id=project.id).first_or_404()
    return_to = request.args.get('return') or request.form.get('return') or 'report'
    if request.method == 'POST':
        old_status = step.status
        status = (request.form.get('status') or '').strip()
        if status in TIMELINE_STEP_STATUSES:
            step.status = status
        step.planned_date = _parse_date(request.form.get('planned_date'))
        step.notes = (request.form.get('notes') or '').strip()
        accepted = project.accepted_quotation
        grand_total = (accepted.grand_total or 0) if accepted else 0
        if step_has_auto_amount(step.step_key) and accepted and grand_total:
            step.amount = calculate_step_amount(grand_total, step.step_key, accepted)
        else:
            amount_raw = (request.form.get('amount') or '').strip()
            if amount_raw:
                try:
                    step.amount = float(amount_raw.replace(',', ''))
                except ValueError:
                    pass
        _apply_step_dates(step, step.status, old_status, request.form)
        if step.status == 'مكتمل' and old_status != 'مكتمل':
            advance_next_step(project, step)
        chain_step_dates_after_edit(project, step)
        sync_step_timeline_dates(project)
        sync_project_status_from_timeline(project)
        steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
        if is_execution_complete(steps):
            project.status = 'مغلق'
        db.session.commit()
        flash(f'تم تحديث: {step.title}', 'success')
        if return_to == 'execution':
            return redirect(url_for('installation.project_execution', project_id=project.id))
        return redirect(url_for('installation.project_report', project_id=project.id))
    auto_amount = None
    accepted = project.accepted_quotation
    if accepted:
        pct = step_amount_pct(step.step_key, accepted)
        if pct is not None:
            auto_amount = {
                'pct': int(round(pct)),
                'amount': calculate_step_amount(accepted.grand_total, step.step_key, accepted),
            }
    return render_template(
        'installation/timeline_step_edit.html',
        project=project,
        step=step,
        step_statuses=TIMELINE_STEP_STATUSES,
        auto_amount=auto_amount,
        return_to=return_to,
        page_title=f'تعديل خطوة — {step.title}',
    )


@install_bp.route('/projects/<int:project_id>/report')
def project_report(project_id):
    project = tenant_get_or_404(InstallProject, project_id)
    if not project.execution_active:
        flash('التقرير متاح بعد قبول العرض وبدء التنفيذ', 'error')
        return redirect(url_for('installation.project_detail', project_id=project.id))
    if sync_step_timeline_dates(project) or sync_project_auto_amounts(project, force=True):
        db.session.commit()
    ctx = _project_report_context(project)
    return render_template(
        'installation/project_report.html',
        project=project,
        report_date=datetime.utcnow().date(),
        page_title=f'تقرير مشروع {project.code}',
        **ctx,
    )


@install_bp.route('/quotes/<int:quotation_id>/print')
def quote_print(quotation_id):
    from installation.catalog import origin_label_from_spec
    q = tenant_get_or_404(InstallQuotation, quotation_id)
    spec = q.spec()
    dims = {
        'shaft_w': _dim_to_cm(spec.get('shaft_width')),
        'shaft_d': _dim_to_cm(spec.get('shaft_depth')),
        'cabin_w': _dim_to_cm(spec.get('cabin_width')),
        'cabin_d': _dim_to_cm(spec.get('cabin_depth')),
    }
    stage_blocks, labor_sell = _quote_stage_blocks(q)
    return render_template(
        'installation/quote_print.html',
        quotation=q,
        project=q.project,
        spec=spec,
        dims=dims,
        origin_label=origin_label_from_spec(spec, 'machine_origin', 'machine_origin_country'),
        machine_brand=spec.get('machine_brand') or '—',
        panel_origin_label=origin_label_from_spec(spec, 'panel_origin', 'panel_origin_country'),
        panel_brand=spec.get('panel_brand') or '—',
        customer_code=q.customer.code if q.customer else (q.project.customer.code if q.project.customer else '—'),
        stage_blocks=stage_blocks,
        labor_sell=labor_sell,
        quote_type=q.quote_type or 'new',
        page_title=f'عرض سعر {q.code}',
    )


def _quote_stage_blocks(quotation):
    """تجميع بنود العرض حسب مرحلة التركيب + توزيع الأجور على المراحل الموجودة فقط."""
    factor = 1 + float(quotation.profit_pct or 0) / 100.0
    labor_pool = (
        float(quotation.labor or 0)
        + float(quotation.transport or 0)
        + float(quotation.other_costs or 0)
    )
    labor_sell = round(labor_pool * factor, 2)
    shares = [
        ('مرحلة 1 — سكك وأبواب', 'أجور وتركيب — سكك وأبواب', 0.30),
        ('مرحلة 2 — تركيب كبينة وأحبال وماكينة', 'أجور وتركيب — كبينة وأحبال وماكينة', 0.45),
        ('مرحلة 3 — تركيب كنترول وتشغيل', 'أجور وتركيب — كنترول وتشغيل', 0.25),
    ]

    ordered = []
    by_stage = {}
    for ln in quotation.lines:
        st = (ln.stage or '—').strip() or '—'
        if st not in by_stage:
            by_stage[st] = []
            ordered.append(st)
        by_stage[st].append(ln)

    labor_by_stage = {}
    used = 0.0
    is_new = (quotation.quote_type or 'new') != 'upgrade'
    active_shares = [s for s in shares if s[0] in by_stage]
    if is_new and labor_pool > 0 and active_shares:
        share_sum = sum(s[2] for s in active_shares) or 1.0
        for i, (stage, label, share) in enumerate(active_shares):
            if i == len(active_shares) - 1:
                amt = round(labor_pool - used, 2)
            else:
                amt = round(labor_pool * (share / share_sum), 2)
                used += amt
            labor_by_stage[stage] = (label, round(amt * factor, 2))

    preferred = [s[0] for s in shares]
    final_order = [s for s in preferred if s in by_stage]
    for st in ordered:
        if st not in final_order:
            final_order.append(st)

    blocks = []
    for st in final_order:
        lines = by_stage.get(st, [])
        lines_total = round(sum(float(ln.line_total or 0) * factor for ln in lines), 2)
        labor_label, labor_amt = labor_by_stage.get(st, (None, 0))
        blocks.append({
            'stage': st,
            'lines': [
                {
                    'name': ln.name,
                    'qty': ln.qty,
                    'unit_price': round(float(ln.unit_price or 0) * factor, 2),
                    'line_total': round(float(ln.line_total or 0) * factor, 2),
                }
                for ln in lines
            ],
            'labor_label': labor_label if is_new else None,
            'labor_amount': labor_amt if is_new else 0,
            'total': round(lines_total + (labor_amt if is_new else 0), 2),
        })
    return blocks, labor_sell


def _projects_by_lead_id(leads):
    """خريطة lead_id → مشروع بدون علاقة one-to-one (تتجنب MultipleResultsFound)."""
    ids = [l.id for l in leads if l and l.id]
    if not ids:
        return {}
    rows = (
        tenant_query(InstallProject)
        .filter(InstallProject.lead_id.in_(ids))
        .order_by(InstallProject.id.asc())
        .all()
    )
    out = {}
    for p in rows:
        if p.lead_id not in out:
            out[p.lead_id] = p
    return out


@install_bp.route('/leads')
def leads_list():
    try:
        leads = tenant_query(InstallLead).order_by(InstallLead.created_at.desc()).all()
        customers = _active_customers()
        project_by_lead = _projects_by_lead_id(leads)
        return render_template(
            'installation/leads.html',
            leads=leads,
            project_by_lead=project_by_lead,
            customers=customers,
            customers_js=[_customer_to_js(c) for c in customers],
            statuses=LEAD_STATUSES,
            sources=LEAD_SOURCES,
            next_lead_code=_next_code(InstallLead, 'LD-', 4),
            page_title='فرص البيع — تركيب',
        )
    except Exception as exc:
        db.session.rollback()
        import logging
        logging.getLogger('liftcore').exception('installation leads_list failed')
        flash(f'تعذّر فتح فرص البيع: {exc}', 'error')
        return redirect(url_for('installation.index'))


@install_bp.route('/leads/add', methods=['POST'])
def leads_add():
    customer_id = request.form.get('customer_id', type=int)
    if not customer_id:
        flash('اختر عميلاً مسجّلاً من جدول العملاء أولاً', 'error')
        return redirect(url_for('installation.leads_list'))
    customer = tenant_query(Customer).filter_by(id=customer_id).first()
    if not customer:
        flash('العميل غير موجود — أضفه من صفحة العملاء', 'error')
        return redirect(url_for('installation.leads_list'))
    try:
        snapshot = _customer_snapshot(customer)
        lead = InstallLead(
            code=_next_code(InstallLead, 'LD-', 4),
            inquiry_date=_parse_date(request.form.get('inquiry_date')) or datetime.utcnow().date(),
            customer_id=customer.id,
            client_name=snapshot['client_name'],
            phone=snapshot['client_phone'],
            email=(customer.email or '').strip(),
            city=(customer.city or '').strip(),
            district=(customer.district or '').strip(),
            address=snapshot['client_address'],
            source=(request.form.get('source') or '').strip(),
            building_type=(request.form.get('building_type') or '').strip(),
            notes=(request.form.get('notes') or '').strip(),
            status=(request.form.get('status') or 'جديد').strip(),
        )
        if lead.status not in LEAD_STATUSES:
            lead.status = 'جديد'
        assign_organization(lead)
        db.session.add(lead)
        db.session.commit()
        flash(f'تم إنشاء الفرصة {lead.code}', 'success')
    except Exception as exc:
        db.session.rollback()
        import logging
        logging.getLogger('liftcore').exception('installation leads_add failed')
        orig = getattr(exc, 'orig', None)
        detail = str(orig or exc).strip()
        if len(detail) > 280:
            detail = detail[:277] + '…'
        flash(f'فشل حفظ الفرصة: {detail}', 'error')
    return redirect(url_for('installation.leads_list'))


@install_bp.route('/leads/<int:lead_id>/status', methods=['POST'])
def leads_status(lead_id):
    lead = tenant_get_or_404(InstallLead, lead_id)
    status = (request.form.get('status') or '').strip()
    if status in LEAD_STATUSES:
        lead.status = status
        db.session.commit()
    return redirect(url_for('installation.leads_list'))


@install_bp.route('/leads/<int:lead_id>/cancel', methods=['POST'])
def leads_cancel(lead_id):
    lead = tenant_get_or_404(InstallLead, lead_id)
    if lead.status == 'ملغي':
        flash('هذه الفرصة ملغاة مسبقاً', 'error')
        return redirect(url_for('installation.leads_list'))
    linked = _projects_by_lead_id([lead]).get(lead.id)
    if lead.status == 'تم تحويله لمشروع' or linked:
        flash('لا يمكن إلغاء فرصة مُحوّلة لمشروع', 'error')
        return redirect(url_for('installation.leads_list'))
    lead.status = 'ملغي'
    db.session.commit()
    flash(f'تم إلغاء الفرصة {lead.code}', 'success')
    return redirect(url_for('installation.leads_list'))


@install_bp.route('/leads/<int:lead_id>/convert', methods=['POST'])
def leads_convert(lead_id):
    lead = tenant_get_or_404(InstallLead, lead_id)
    linked = _projects_by_lead_id([lead]).get(lead.id)
    if lead.status == 'تم تحويله لمشروع' and linked:
        flash('هذه الفرصة مُحوّلة مسبقاً', 'error')
        return redirect(url_for('installation.project_detail', project_id=linked.id))
    project = InstallProject(
        code=_next_code(InstallProject, 'PRJ-', 4),
        title=lead.client_display,
        status='استفسار',
        lead_id=lead.id,
        customer_id=lead.customer_id,
        notes=lead.notes,
    )
    assign_organization(project)
    db.session.add(project)
    lead.status = 'تم تحويله لمشروع'
    db.session.commit()
    flash(f'تم إنشاء المشروع {project.code} — العميل مربوط ويمكنك البدء بالتسعير', 'success')
    return redirect(url_for('installation.project_detail', project_id=project.id))
