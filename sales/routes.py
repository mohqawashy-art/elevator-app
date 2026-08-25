"""مسارات قسم المبيعات."""
from __future__ import annotations

from datetime import date, datetime

from flask import flash, redirect, render_template, request, url_for

from models import Customer, Elevator, MaintenanceQuote, MaintenanceQuoteElevator, db
from sales import sales_bp
from sales.service import (
    create_contract_from_maintenance_quote,
    money_round,
    recalc_quote_totals,
    sync_quote_elevators,
)
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query


def _parse_date(raw: str):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _apply_maint_quote_form(quote: MaintenanceQuote, form) -> None:
    quote.customer_id = int(form.get('customer_id') or 0)
    quote.duration_months = int(form.get('duration_months') or 12)
    quote.maint_frequency = (form.get('maint_frequency') or '').strip() or None
    quote.visits_per_month = int(form.get('visits_per_month') or 1)
    quote.value = money_round(form.get('value'))
    quote.tax_pct = money_round(form.get('tax_pct') if form.get('tax_pct') not in (None, '') else 15)
    quote.payment_terms = (form.get('payment_terms') or '').strip() or None
    quote.start_date = _parse_date(form.get('start_date') or '')
    quote.end_date = _parse_date(form.get('end_date') or '')
    quote.city = (form.get('city') or '').strip() or None
    quote.district = (form.get('district') or '').strip() or None
    quote.address = (form.get('address') or '').strip() or None
    quote.notes = (form.get('notes') or '').strip() or None
    recalc_quote_totals(quote)
    if quote.start_date and quote.duration_months and not quote.end_date:
        from sales.service import add_months
        quote.end_date = add_months(quote.start_date, quote.duration_months)


@sales_bp.route('/')
def hub():
    from installation.config import install_module_enabled

    maint_open = (
        tenant_query(MaintenanceQuote)
        .filter(MaintenanceQuote.status.in_(['مسودة', 'مُرسل']))
        .count()
    )
    install_open = 0
    module_on = False
    try:
        module_on = bool(install_module_enabled())
        if module_on:
            from installation.models import InstallQuotation
            install_open = (
                tenant_query(InstallQuotation)
                .filter(InstallQuotation.status.in_(['مسودة', 'مُرسل', 'تفاوض']))
                .count()
            )
    except Exception:
        install_open = 0
        module_on = False
    return render_template(
        'sales/hub.html',
        page_title='المبيعات',
        maint_open=maint_open,
        install_open=install_open,
        install_module_on=module_on,
    )


@sales_bp.route('/quotes')
def quotes_inbox():
    status = (request.args.get('status') or '').strip()
    maint_q = tenant_query(MaintenanceQuote).order_by(MaintenanceQuote.id.desc())
    if status:
        maint_q = maint_q.filter_by(status=status)
    maint = maint_q.limit(200).all()

    install = []
    try:
        from installation.config import install_module_enabled
        from installation.models import InstallQuotation
        if install_module_enabled():
            iq = tenant_query(InstallQuotation).order_by(InstallQuotation.id.desc())
            if status:
                iq = iq.filter_by(status=status)
            install = iq.limit(200).all()
    except Exception:
        install = []

    rows = []
    for q in maint:
        rows.append({
            'kind': 'maintenance',
            'kind_ar': 'صيانة',
            'id': q.id,
            'code': q.code,
            'status': q.status,
            'total': q.total or 0,
            'customer': q.customer.name if q.customer else '—',
            'created_at': q.created_at,
            'url': url_for('sales.maintenance_quote_edit', quote_id=q.id),
            'print_url': url_for('sales.maintenance_quote_print', quote_id=q.id),
            'contract_id': q.result_contract_id,
        })
    for q in install:
        cust_name = '—'
        try:
            if getattr(q, 'customer', None):
                cust_name = q.customer.name
        except Exception:
            pass
        rows.append({
            'kind': 'install',
            'kind_ar': 'تركيب',
            'id': q.id,
            'code': q.code,
            'status': q.status,
            'total': getattr(q, 'grand_total', None) or 0,
            'customer': cust_name,
            'created_at': getattr(q, 'created_at', None),
            'url': url_for('installation.project_detail', project_id=q.project_id) if q.project_id else '#',
            'print_url': url_for('installation.quote_print', quotation_id=q.id),
            'contract_id': None,
        })
    rows.sort(key=lambda r: r['created_at'] or datetime.min, reverse=True)
    return render_template(
        'sales/quotes.html',
        page_title='عروض السعر',
        rows=rows,
        status=status,
    )


@sales_bp.route('/maintenance-quotes')
def maintenance_quotes_list():
    quotes = tenant_query(MaintenanceQuote).order_by(MaintenanceQuote.id.desc()).limit(300).all()
    return render_template(
        'sales/maintenance_quotes.html',
        page_title='تسعير عقود الصيانة',
        quotes=quotes,
    )


@sales_bp.route('/maintenance-quotes/new', methods=['GET', 'POST'])
def maintenance_quote_new():
    from app import next_code

    customers = tenant_query(Customer).order_by(Customer.name).all()
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)
        if not customer_id:
            flash('اختر العميل', 'error')
            return redirect(url_for('sales.maintenance_quote_new'))
        quote = MaintenanceQuote(code=next_code(MaintenanceQuote, 'MQ-', digits=5))
        assign_organization(quote)
        _apply_maint_quote_form(quote, request.form)
        if not quote.customer_id:
            flash('اختر العميل', 'error')
            return redirect(url_for('sales.maintenance_quote_new'))
        db.session.add(quote)
        db.session.flush()
        sync_quote_elevators(quote.id, request.form.getlist('elevator_ids'))
        db.session.commit()
        flash(f'تم إنشاء عرض {quote.code}', 'success')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))

    elevators = tenant_query(Elevator).order_by(Elevator.code).limit(500).all()
    return render_template(
        'sales/maintenance_quote_form.html',
        page_title='عرض سعر صيانة جديد',
        quote=None,
        customers=customers,
        elevators=elevators,
        selected_elevator_ids=set(),
        today=date.today().isoformat(),
    )


@sales_bp.route('/maintenance-quotes/<int:quote_id>', methods=['GET', 'POST'])
def maintenance_quote_edit(quote_id):
    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    if quote.status == 'مقبول' and request.method == 'POST':
        flash('العرض مقبول ولا يمكن تعديله', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))

    if request.method == 'POST':
        _apply_maint_quote_form(quote, request.form)
        sync_quote_elevators(quote.id, request.form.getlist('elevator_ids'))
        quote.updated_at = datetime.utcnow()
        db.session.commit()
        flash('تم حفظ العرض', 'success')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))

    customers = tenant_query(Customer).order_by(Customer.name).all()
    elevators = tenant_query(Elevator).order_by(Elevator.code).limit(500).all()
    selected = {
        row.elevator_id
        for row in tenant_query(MaintenanceQuoteElevator).filter_by(quote_id=quote.id).all()
    }
    return render_template(
        'sales/maintenance_quote_form.html',
        page_title=f'عرض صيانة {quote.code}',
        quote=quote,
        customers=customers,
        elevators=elevators,
        selected_elevator_ids=selected,
        today=date.today().isoformat(),
    )


@sales_bp.route('/maintenance-quotes/<int:quote_id>/send', methods=['POST'])
def maintenance_quote_send(quote_id):
    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    if quote.status == 'مقبول':
        flash('العرض مقبول مسبقاً', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    quote.status = 'مُرسل'
    quote.sent_at = datetime.utcnow()
    db.session.commit()
    flash('تم تعليم العرض كمُرسل للعميل', 'success')
    return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))


@sales_bp.route('/maintenance-quotes/<int:quote_id>/approve', methods=['POST'])
def maintenance_quote_approve(quote_id):
    from app import next_code

    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    if quote.status == 'مقبول' and quote.result_contract_id:
        flash('تم تحويل العرض مسبقاً', 'success')
        return redirect(url_for('contracts'))
    if not quote.customer_id:
        flash('العرض بدون عميل', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    try:
        contract = create_contract_from_maintenance_quote(quote, next_code_fn=next_code)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('تعذّر تحويل العرض لعقد', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    flash(f'تمت موافقة العميل — أُنشئ عقد الصيانة {contract.code}', 'success')
    return redirect(url_for('contracts'))


@sales_bp.route('/maintenance-quotes/<int:quote_id>/reject', methods=['POST'])
def maintenance_quote_reject(quote_id):
    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    if quote.status == 'مقبول':
        flash('لا يمكن رفض عرض مقبول', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    quote.status = 'مرفوض'
    db.session.commit()
    flash('تم رفض العرض', 'success')
    return redirect(url_for('sales.maintenance_quotes_list'))


@sales_bp.route('/maintenance-quotes/<int:quote_id>/print')
def maintenance_quote_print(quote_id):
    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    elev_ids = [
        r.elevator_id
        for r in tenant_query(MaintenanceQuoteElevator).filter_by(quote_id=quote.id).all()
    ]
    elevators = []
    if elev_ids:
        elevators = tenant_query(Elevator).filter(Elevator.id.in_(elev_ids)).all()
    return render_template(
        'sales/maintenance_quote_print.html',
        quote=quote,
        elevators=elevators,
        page_title=f'طباعة {quote.code}',
    )
