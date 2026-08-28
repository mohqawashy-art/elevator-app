"""مسارات قسم المبيعات."""
from __future__ import annotations

from datetime import date, datetime

from flask import flash, redirect, render_template, request, url_for

from models import Customer, Elevator, MaintenanceQuote, MaintenanceQuoteElevator, db
from sales import sales_bp
from sales.service import (
    create_contract_from_maintenance_quote,
    create_install_project_and_quote_from_estimate,
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


def _split_maint_notes(notes: str | None) -> tuple[str, list[str], str]:
    """استخراج الباقة والنطاق من ملاحظات العرض المحفوظة."""
    text = (notes or '').strip()
    package = 'قياسي'
    scope: list[str] = []
    body_lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('باقة الخدمة:'):
            package = s.split(':', 1)[1].strip() or package
        elif s.startswith('نطاق الخدمة:'):
            scope = [p.strip() for p in s.split(':', 1)[1].split('،') if p.strip()]
        else:
            body_lines.append(line)
    return package, scope, '\n'.join(body_lines).strip()


def _compose_maint_notes(form) -> str:
    package = (form.get('service_package') or 'قياسي').strip() or 'قياسي'
    scope = form.getlist('scope_items') if hasattr(form, 'getlist') else []
    body = (form.get('notes_body') or form.get('notes') or '').strip()
    parts = [f'باقة الخدمة: {package}']
    if scope:
        parts.append('نطاق الخدمة: ' + '، '.join(scope))
    if body:
        parts.append(body)
    return '\n'.join(parts)


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
    quote.notes = _compose_maint_notes(form) or None
    recalc_quote_totals(quote)
    if quote.start_date and quote.duration_months and not quote.end_date:
        from sales.service import add_months
        quote.end_date = add_months(quote.start_date, quote.duration_months)


def _maint_form_context(quote=None, *, selected_elevator_ids=None):
    customers = tenant_query(Customer).order_by(Customer.name).all()
    elevators = tenant_query(Elevator).order_by(Elevator.code).limit(800).all()
    package, scope, notes_body = _split_maint_notes(quote.notes if quote else None)
    elev_n = len(selected_elevator_ids or [])
    months = float((quote.duration_months if quote else 12) or 12)
    price_per = 0.0
    if quote and elev_n and months and quote.value:
        # عكس تقريبي: قيمة / مصاعد / (مدة÷12)
        years = months / 12.0
        if years > 0:
            price_per = money_round((quote.value or 0) / elev_n / years)
    return dict(
        customers=customers,
        elevators=elevators,
        selected_elevator_ids=selected_elevator_ids or set(),
        today=date.today().isoformat(),
        package=package,
        scope_items=scope,
        notes_body=notes_body,
        price_per_elevator=price_per,
    )


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


@sales_bp.route('/install')
def install_hub():
    return redirect(url_for('sales.quotes_inbox', kind='install'))


@sales_bp.route('/maintenance')
def maintenance_hub():
    return redirect(url_for('sales.maintenance_quotes_list'))


@sales_bp.route('/install/quotes/new', methods=['GET', 'POST'])
def install_quote_new():
    """عرض تركيب مصعد جديد — صفحة تسعير مستقلة."""
    return _start_install_quote('new')


@sales_bp.route('/install/quotes/upgrade', methods=['GET', 'POST'])
def install_quote_upgrade():
    """عرض سعر تحديث — صفحة تسعير مستقلة."""
    return _start_install_quote('upgrade')


@sales_bp.route('/install/quotes/extend', methods=['GET', 'POST'])
def install_quote_extend():
    """عرض إضافة أدوار — نموذج مستقل."""
    return _start_install_quote('extend')


def _start_install_quote(default_kind: str):
    """بدء عرض تركيب من المبيعات — ينشئ مشروعاً ويفتح فورم التسعير المناسب."""
    from installation.config import install_module_enabled
    from installation.models import InstallProject, QUOTE_FLOW_PAGE_TITLES
    from installation.routes import _next_code

    if not install_module_enabled():
        flash('وحدة التركيب غير مفعّلة', 'error')
        return redirect(url_for('sales.hub'))

    if request.method == 'GET' and not request.args.get('go'):
        return redirect(url_for(
            request.endpoint,
            go=1,
            quote_kind=default_kind,
        ))

    title = (request.form.get('title') or request.args.get('title') or '').strip()
    quote_kind = (
        request.form.get('quote_kind')
        or request.args.get('quote_kind')
        or default_kind
    ).strip()
    kind_labels = {
        'new': 'تركيب مصعد جديد',
        'upgrade': 'عرض سعر تحديث',
        'extend': 'إضافة أدوار',
    }
    if quote_kind not in kind_labels:
        quote_kind = 'new'
    if not title:
        title = QUOTE_FLOW_PAGE_TITLES.get(quote_kind) or kind_labels[quote_kind]

    project = InstallProject(
        code=_next_code(InstallProject, 'PRJ-', 4),
        title=title,
        status='تسعير',
        notes=f'من مبيعات التركيبات — {kind_labels[quote_kind]}',
    )
    assign_organization(project)
    db.session.add(project)
    db.session.commit()
    flash('تم إنشاء العرض — أكمل المواصفات ثم أرسله للعميل من المبيعات', 'success')
    return redirect(url_for(
        'installation.project_quote',
        project_id=project.id,
        new=1,
        quote_type=quote_kind,
        **{'from': 'sales'},
    ))


@sales_bp.route('/install/quotes/<int:quotation_id>/deliver/<channel>')
def install_quote_deliver(quotation_id, channel):
    """فتح واتساب/إيميل لإرسال عرض التركيب وتعليم الحالة كمُرسل."""
    from installation.models import InstallQuotation
    from models import Settings
    from sales.delivery import delivery_links_for_install_quote

    channel = (channel or '').strip().lower()
    if channel not in ('whatsapp', 'email'):
        flash('قناة إرسال غير مدعومة', 'error')
        return redirect(url_for('sales.quotes_inbox', kind='install'))

    q = tenant_get_or_404(InstallQuotation, quotation_id)
    print_url = url_for('installation.quote_print', quotation_id=q.id, _external=True)
    settings = tenant_query(Settings).first()
    links = delivery_links_for_install_quote(q, print_url=print_url, settings=settings)
    target = links['whatsapp_url'] if channel == 'whatsapp' else links['mailto_url']
    if not target:
        missing = 'رقم جوال' if channel == 'whatsapp' else 'بريد إلكتروني'
        flash(f'لا يوجد {missing} للعميل — حدّث بيانات العميل أولاً', 'error')
        return redirect(url_for('installation.project_detail', project_id=q.project_id))

    if q.status not in ('مقبول', 'مرفوض'):
        q.status = 'مُرسل'
        from datetime import datetime as dt
        if hasattr(q, 'sent_at'):
            pass
        project = q.project
        if project and project.status in ('استفسار', 'معاينة', 'هندسة', 'تسعير'):
            project.status = 'عرض سعر'
        db.session.commit()

    return redirect(target)


@sales_bp.route('/maintenance-quotes/<int:quote_id>/deliver/<channel>')
def maintenance_quote_deliver(quote_id, channel):
    from models import Settings
    from sales.delivery import delivery_links_for_maint_quote

    channel = (channel or '').strip().lower()
    if channel not in ('whatsapp', 'email'):
        flash('قناة إرسال غير مدعومة', 'error')
        return redirect(url_for('sales.maintenance_quotes_list'))

    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    print_url = url_for('sales.maintenance_quote_print', quote_id=quote.id, _external=True)
    settings = tenant_query(Settings).first()
    links = delivery_links_for_maint_quote(quote, print_url=print_url, settings=settings)
    target = links['whatsapp_url'] if channel == 'whatsapp' else links['mailto_url']
    if not target:
        missing = 'رقم جوال' if channel == 'whatsapp' else 'بريد إلكتروني'
        flash(f'لا يوجد {missing} للعميل — حدّث بيانات العميل أولاً', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))

    if quote.status not in ('مقبول', 'مرفوض'):
        quote.status = 'مُرسل'
        quote.sent_at = datetime.utcnow()
        db.session.commit()

    return redirect(target)


@sales_bp.route('/install/from-estimate/<int:estimate_id>', methods=['POST'])
def convert_estimate_to_install_quote(estimate_id):
    """تقدير قديم → عرض سعر (للتوافق). المسار الجديد عبر /sales/install/quotes/new."""
    from installation.config import install_module_enabled
    from installation.routes import _next_code
    from models import ElevatorEstimate

    if not install_module_enabled():
        flash('وحدة التركيب غير مفعّلة', 'error')
        return redirect(url_for('sales.install_quote_new'))

    est = tenant_get_or_404(ElevatorEstimate, estimate_id)
    if not est.customer_id:
        flash('اربط التقدير بعميل قبل إصدار عرض السعر', 'error')
        return redirect(f'/elevator-estimates?edit={est.id}')

    if est.result_project_id and est.result_quotation_id:
        flash('تم تحويل هذا التقدير مسبقاً', 'success')
        return redirect(url_for('installation.project_detail', project_id=est.result_project_id))

    try:
        result = create_install_project_and_quote_from_estimate(
            est,
            next_project_code_fn=_next_code,
            next_quote_code_fn=_next_code,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('تعذّر إصدار عرض السعر من التقدير', 'error')
        return redirect(url_for('sales.install_quote_new'))

    flash(
        f'صدر عرض السعر {result["quote_code"]} — راجع وعدّل ثم أرسل للعميل',
        'success',
    )
    return redirect(url_for(
        'installation.project_quote',
        project_id=result['project_id'],
        quotation_id=result['quotation_id'],
    ))


@sales_bp.route('/quotes')
def quotes_inbox():
    status = (request.args.get('status') or '').strip()
    kind = (request.args.get('kind') or '').strip().lower()
    maint_q = tenant_query(MaintenanceQuote).order_by(MaintenanceQuote.id.desc())
    if status:
        maint_q = maint_q.filter_by(status=status)
    maint = maint_q.limit(200).all() if kind in ('', 'maintenance', 'صيانة') else []

    install = []
    try:
        from installation.config import install_module_enabled
        from installation.models import InstallQuotation
        if install_module_enabled() and kind in ('', 'install', 'تركيب', 'تركيبات'):
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
            'url': url_for(
                'installation.project_quote',
                project_id=q.project_id,
                quotation_id=q.id,
                **{'from': 'sales'},
            ) if q.project_id and q.status not in ('مقبول',) else (
                url_for('installation.project_detail', project_id=q.project_id) if q.project_id else '#'
            ),
            'print_url': url_for('installation.quote_print', quotation_id=q.id),
            'project_id': q.project_id,
            'project_url': url_for('installation.project_detail', project_id=q.project_id) if q.project_id else None,
            'deliver_wa': url_for('sales.install_quote_deliver', quotation_id=q.id, channel='whatsapp'),
            'deliver_email': url_for('sales.install_quote_deliver', quotation_id=q.id, channel='email'),
            'approve_url': url_for(
                'installation.quote_approve',
                project_id=q.project_id,
                quotation_id=q.id,
            ) if q.project_id else None,
            'contract_id': None,
        })
    rows.sort(key=lambda r: r['created_at'] or datetime.min, reverse=True)
    title = 'عروض السعر'
    if kind in ('install', 'تركيب', 'تركيبات'):
        title = 'عروض سعر التركيبات'
    elif kind in ('maintenance', 'صيانة'):
        title = 'عروض سعر الصيانة'
    return render_template(
        'sales/quotes.html',
        page_title=title,
        rows=rows,
        status=status,
        kind=kind,
    )


@sales_bp.route('/maintenance-quotes')
def maintenance_quotes_list():
    status = (request.args.get('status') or '').strip()
    q = tenant_query(MaintenanceQuote).order_by(MaintenanceQuote.id.desc())
    if status:
        q = q.filter_by(status=status)
    quotes = q.limit(300).all()
    return render_template(
        'sales/maintenance_quotes.html',
        page_title='عروض سعر الصيانة',
        quotes=quotes,
        status=status,
    )


@sales_bp.route('/maintenance-quotes/new', methods=['GET', 'POST'])
def maintenance_quote_new():
    from app import next_code

    if request.method == 'POST':
        customer_id = request.form.get('customer_id', type=int)
        elev_ids = request.form.getlist('elevator_ids')
        if not customer_id:
            flash('اختر العميل', 'error')
            return redirect(url_for('sales.maintenance_quote_new'))
        if not elev_ids:
            flash('اختر مصعداً واحداً على الأقل مشمولاً في العرض', 'error')
            return redirect(url_for('sales.maintenance_quote_new'))
        quote = MaintenanceQuote(code=next_code(MaintenanceQuote, 'MQ-', digits=5))
        assign_organization(quote)
        _apply_maint_quote_form(quote, request.form)
        if not quote.customer_id:
            flash('اختر العميل', 'error')
            return redirect(url_for('sales.maintenance_quote_new'))
        if money_round(quote.value) <= 0:
            flash('أدخل قيمة العرض أو سعر المصعد', 'error')
            return redirect(url_for('sales.maintenance_quote_new'))
        db.session.add(quote)
        db.session.flush()
        sync_quote_elevators(quote.id, elev_ids)
        db.session.commit()
        flash(f'تم إنشاء عرض {quote.code}', 'success')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))

    return render_template(
        'sales/maintenance_quote_form.html',
        page_title='عرض سعر صيانة جديد',
        quote=None,
        **_maint_form_context(),
    )


@sales_bp.route('/maintenance-quotes/<int:quote_id>', methods=['GET', 'POST'])
def maintenance_quote_edit(quote_id):
    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    if quote.status == 'مقبول' and request.method == 'POST':
        flash('العرض مقبول ولا يمكن تعديله', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))

    if request.method == 'POST':
        elev_ids = request.form.getlist('elevator_ids')
        if not elev_ids:
            flash('اختر مصعداً واحداً على الأقل', 'error')
            return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
        _apply_maint_quote_form(quote, request.form)
        if money_round(quote.value) <= 0:
            flash('قيمة العرض يجب أن تكون أكبر من صفر', 'error')
            return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
        sync_quote_elevators(quote.id, elev_ids)
        quote.updated_at = datetime.utcnow()
        db.session.commit()
        flash('تم حفظ العرض', 'success')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))

    selected = {
        row.elevator_id
        for row in tenant_query(MaintenanceQuoteElevator).filter_by(quote_id=quote.id).all()
    }
    return render_template(
        'sales/maintenance_quote_form.html',
        page_title=f'عرض صيانة {quote.code}',
        quote=quote,
        **_maint_form_context(quote, selected_elevator_ids=selected),
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
    elev_count = tenant_query(MaintenanceQuoteElevator).filter_by(quote_id=quote.id).count()
    if elev_count < 1:
        flash('أضف مصعداً واحداً على الأقل قبل الموافقة', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    if money_round(quote.total) <= 0:
        flash('قيمة العرض غير مكتملة', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    if not quote.start_date:
        flash('حدد تاريخ بداية العقد', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    try:
        contract = create_contract_from_maintenance_quote(quote, next_code_fn=next_code)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('تعذّر تحويل العرض لعقد', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    flash(f'تمت موافقة العميل — أُنشئ عقد الصيانة {contract.code} وتحوّل للعقود', 'success')
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
