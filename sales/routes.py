"""مسارات قسم المبيعات."""
from __future__ import annotations

from datetime import date, datetime

from flask import flash, g, redirect, render_template, request, url_for

from models import Customer, MaintenanceQuote, MaintenanceQuoteSurvey, Technician, db
from sales import sales_bp
from sales.maint_survey import (
    SURVEY_DONE,
    active_survey_for_quote,
    create_survey_request,
    latest_survey_for_quote,
    quote_survey_units_for_display,
    survey_units_payload,
)
from sales.service import (
    apply_total_including_tax,
    clear_maintenance_quotes,
    create_contract_from_maintenance_quote,
    create_install_project_and_quote_from_estimate,
    delete_maintenance_quote,
    money_round,
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
    tax_pct = money_round(form.get('tax_pct') if form.get('tax_pct') not in (None, '') else 15)
    total_incl = money_round(form.get('total_incl_tax'))
    if total_incl <= 0:
        total_incl = money_round(form.get('value'))
        if total_incl > 0:
            from sales.service import recalc_quote_totals

            quote.value = total_incl
            quote.tax_pct = tax_pct
            recalc_quote_totals(quote)
        else:
            apply_total_including_tax(quote, 0, tax_pct=tax_pct)
    else:
        apply_total_including_tax(quote, total_incl, tax_pct=tax_pct)
    quote.payment_terms = (form.get('payment_terms') or '').strip() or None
    quote.start_date = _parse_date(form.get('start_date') or '')
    quote.end_date = _parse_date(form.get('end_date') or '')
    quote.city = (form.get('city') or '').strip() or None
    quote.district = (form.get('district') or '').strip() or None
    quote.address = (form.get('address') or '').strip() or None
    quote.notes = _compose_maint_notes(form) or None
    if quote.start_date and quote.duration_months and not quote.end_date:
        from sales.service import add_months
        quote.end_date = add_months(quote.start_date, quote.duration_months)


def _customer_map_row(c) -> dict:
    from app import _annotate_contract_renewals, contract_display_status

    active_states = ('نشط', 'على وشك الانتهاء')
    contracts = list(c.contracts or [])
    renewed = _annotate_contract_renewals(contracts) if contracts else set()
    sites = []
    lat = (c.lat or '').strip()
    lng = (c.lng or '').strip()
    active_status = ''
    for ct in contracts:
        st = contract_display_status(ct, renewed_ids=renewed)
        if st not in active_states:
            continue
        if not active_status:
            active_status = st
        sites.append({
            'city': (ct.city or '').strip(),
            'district': (ct.district or '').strip(),
        })
        if (not lat or not lng) and (ct.lat or '').strip() and (ct.lng or '').strip():
            lat = (ct.lat or '').strip()
            lng = (ct.lng or '').strip()
    return {
        'id': c.id,
        'code': c.code or '',
        'name': c.name or '',
        'city': c.city or '',
        'district': c.district or '',
        'address': c.address or '',
        'lat': lat,
        'lng': lng,
        'status': c.status or '',
        'has_contract': bool(active_status),
        'contract_status': active_status or 'بدون عقد',
        'sites': sites,
    }


def _maint_form_context(quote=None, *, selected_elevator_ids=None):
    from models import Technician
    from sqlalchemy.orm import selectinload

    customers = (
        tenant_query(Customer)
        .options(selectinload(Customer.contracts))
        .order_by(Customer.name)
        .all()
    )
    package, scope, notes_body = _split_maint_notes(quote.notes if quote else None)
    total_incl_tax = money_round(quote.total if quote else 0)
    survey = latest_survey_for_quote(quote.id) if quote else None
    technicians = (
        tenant_query(Technician)
        .filter(Technician.status.in_(['نشط', 'متاح', 'مشغول', '']))
        .order_by(Technician.name)
        .all()
    )
    survey_units = survey_units_payload(survey) if survey and survey.status == SURVEY_DONE else []
    customers_map_js = [_customer_map_row(c) for c in customers]
    return dict(
        customers=customers,
        customers_map_js=customers_map_js,
        today=date.today().isoformat(),
        package=package,
        scope_items=scope,
        notes_body=notes_body,
        total_incl_tax=total_incl_tax,
        maint_survey=survey,
        survey_units=survey_units,
        technicians=technicians,
    )


def _send_survey_from_form(quote: MaintenanceQuote, form) -> MaintenanceQuoteSurvey:
    from app import next_code

    tech_id = form.get('technician_id', type=int)
    if not tech_id:
        raise ValueError('اختر الفني لإرسال طلب المعاينة')
    notes = (form.get('survey_notes') or '').strip()
    return create_survey_request(
        quote,
        technician_id=tech_id,
        request_notes=notes,
        next_code_fn=next_code,
    )


def _maint_quote_action(form) -> str:
    return (form.get('action') or 'save').strip()


def _validate_maint_quote_total(quote: MaintenanceQuote, *, require_total: bool) -> None:
    if require_total and money_round(quote.total) <= 0:
        raise ValueError('أدخل الإجمالي شامل الضريبة')


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


@sales_bp.route('/install/quotes/upgrade')
def install_quote_upgrade_redirect():
    return redirect(url_for('sales.install_quote_new', quote_kind='upgrade'))


@sales_bp.route('/install/quotes/extend')
def install_quote_extend_redirect():
    return redirect(url_for('sales.install_quote_new', quote_kind='extend'))


@sales_bp.route('/install/quotes/new', methods=['GET', 'POST'])
def install_quote_new():
    """بدء عرض تركيب من المبيعات — ينشئ مشروعاً فقط بعد تأكيد POST."""
    from installation.config import install_module_enabled
    from installation.models import InstallProject
    from installation.routes import _next_code

    if not install_module_enabled():
        flash('وحدة التركيب غير مفعّلة', 'error')
        return redirect(url_for('sales.hub'))

    if request.method == 'GET':
        return render_template(
            'sales/install_quote_start.html',
            page_title='عرض تركيب جديد',
            quote_kind=(request.args.get('quote_kind') or '').strip(),
        )

    title = (request.form.get('title') or '').strip()
    quote_kind = (request.form.get('quote_kind') or 'new').strip()
    kind_labels = {
        'new': 'تركيب مصعد جديد',
        'upgrade': 'تحديث مصعد قائم',
        'extend': 'إضافة أدوار',
    }
    if quote_kind not in kind_labels:
        quote_kind = 'new'
    if not title:
        title = kind_labels[quote_kind]

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
    from document_share import document_share_url
    oid = int(getattr(q, 'organization_id', None) or getattr(g, 'organization_id', None) or 0)
    print_url = document_share_url('iq', q.id, oid, request.url_root)
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
    from document_share import document_share_url
    oid = int(getattr(quote, 'organization_id', None) or getattr(g, 'organization_id', None) or 0)
    print_url = document_share_url('mq', quote.id, oid, request.url_root)
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

    if est.result_project_id:
        flash('تم تحويل هذا التقدير مسبقاً', 'success')
        if est.result_quotation_id:
            return redirect(url_for(
                'installation.project_quote',
                project_id=est.result_project_id,
                quotation_id=est.result_quotation_id,
            ))
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
            elif kind in ('install', 'تركيب', 'تركيبات'):
                iq = iq.filter(InstallQuotation.status.notin_(('مقبول',)))
            install = iq.limit(200).all()
    except Exception:
        install = []

    rows = []
    for q in maint:
        contract_url = (
            url_for('contract_print_page', contract_id=q.result_contract_id)
            if q.result_contract_id else None
        )
        rows.append({
            'kind': 'maintenance',
            'kind_ar': 'صيانة',
            'id': q.id,
            'code': q.code,
            'status': q.status,
            'total': q.total or 0,
            'customer': q.customer.name if q.customer else '—',
            'created_at': q.created_at,
            'url': contract_url or url_for('sales.maintenance_quote_edit', quote_id=q.id),
            'print_url': url_for('sales.maintenance_quote_print', quote_id=q.id),
            'contract_id': q.result_contract_id,
            'contract_url': contract_url,
            'approve_url': url_for('sales.maintenance_quote_approve', quote_id=q.id),
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
            ) if q.project_id else '#',
            'print_url': url_for('installation.quote_print', quotation_id=q.id),
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
        action = _maint_quote_action(request.form)
        send_survey = action == 'save_send_survey'
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
        try:
            _validate_maint_quote_total(quote, require_total=not send_survey)
            db.session.add(quote)
            db.session.flush()
            survey = None
            if send_survey:
                survey = _send_survey_from_form(quote, request.form)
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('sales.maintenance_quote_new'))
        if send_survey and survey:
            flash(f'تم حفظ العرض {quote.code} وإرسال طلب فحص {survey.code} للفني للمعاينة', 'success')
        else:
            flash(f'تم إنشاء عرض {quote.code}', 'success')
        if action == 'save_print':
            return redirect(url_for('sales.maintenance_quote_print', quote_id=quote.id))
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
        action = _maint_quote_action(request.form)
        send_survey = action == 'save_send_survey'
        _apply_maint_quote_form(quote, request.form)
        try:
            _validate_maint_quote_total(quote, require_total=not send_survey)
            quote.updated_at = datetime.utcnow()
            survey = None
            if send_survey:
                survey = _send_survey_from_form(quote, request.form)
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'error')
            return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
        if send_survey and survey:
            flash(f'تم حفظ العرض وإرسال طلب فحص {survey.code} للفني للمعاينة', 'success')
        else:
            flash('تم حفظ العرض', 'success')
        if action == 'save_print':
            return redirect(url_for('sales.maintenance_quote_print', quote_id=quote.id))
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))

    return render_template(
        'sales/maintenance_quote_form.html',
        page_title=f'عرض صيانة {quote.code}',
        quote=quote,
        **_maint_form_context(quote),
    )


@sales_bp.route('/maintenance-quotes/<int:quote_id>/request-survey', methods=['POST'])
def maintenance_quote_request_survey(quote_id):
    from app import next_code

    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    if quote.status == 'مقبول':
        flash('العرض مقبول ولا يمكن إرسال فحص', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    tech_id = request.form.get('technician_id', type=int)
    if not tech_id:
        flash('اختر الفني', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    notes = (request.form.get('survey_notes') or '').strip()
    try:
        survey = create_survey_request(
            quote,
            technician_id=tech_id,
            request_notes=notes,
            next_code_fn=next_code,
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    flash(f'تم إرسال طلب فحص {survey.code} للفني', 'success')
    return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))


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
        return redirect(url_for('contract_print_page', contract_id=quote.result_contract_id))
    if not quote.customer_id:
        flash('العرض بدون عميل', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    elev_count = len(quote_survey_units_for_display(quote))
    survey = active_survey_for_quote(quote.id)
    if elev_count < 1 or not survey or survey.status != SURVEY_DONE:
        flash('أكمل فحص المصاعد من الفني قبل الموافقة', 'error')
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
    return redirect(url_for('contract_print_page', contract_id=contract.id))


@sales_bp.route('/maintenance-quotes/<int:quote_id>/reject', methods=['POST'])
def maintenance_quote_reject(quote_id):
    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    if quote.status == 'مقبول':
        flash('لا يمكن رفض عرض مقبول', 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    quote.status = 'مرفوض'
    from sales.maint_survey import cancel_open_surveys_for_quote

    cancel_open_surveys_for_quote(quote.id)
    db.session.commit()
    flash('تم رفض العرض', 'success')
    return redirect(url_for('sales.maintenance_quotes_list'))


@sales_bp.route('/maintenance-quotes/<int:quote_id>/delete', methods=['POST'])
def maintenance_quote_delete(quote_id):
    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    code = quote.code
    try:
        delete_maintenance_quote(quote)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'error')
        return redirect(url_for('sales.maintenance_quote_edit', quote_id=quote.id))
    flash(f'تم حذف عرض {code}', 'success')
    return redirect(url_for('sales.maintenance_quotes_list'))


@sales_bp.route('/maintenance-quotes/clear-all', methods=['POST'])
def maintenance_quotes_clear_all():
    confirm = (request.form.get('confirm') or '').strip()
    if confirm != 'CLEAR_MQ':
        flash('لتصفير العروض اكتب CLEAR_MQ في خانة التأكيد', 'error')
        return redirect(url_for('sales.maintenance_quotes_list'))
    include_contracts = (request.form.get('include_contracts') or '').strip() == '1'
    try:
        n = clear_maintenance_quotes(include_with_contract=include_contracts)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('تعذّر تصفير العروض', 'error')
        return redirect(url_for('sales.maintenance_quotes_list'))
    flash(f'تم تصفير عروض الصيانة ({n})', 'success')
    return redirect(url_for('sales.maintenance_quotes_list'))


@sales_bp.route('/maintenance-quotes/<int:quote_id>/print')
def maintenance_quote_print(quote_id):
    quote = tenant_get_or_404(MaintenanceQuote, quote_id)
    survey_units = quote_survey_units_for_display(quote)
    package, scope, notes_body = _split_maint_notes(quote.notes if quote else None)
    survey = latest_survey_for_quote(quote.id)
    return render_template(
        'sales/maintenance_quote_print.html',
        quote=quote,
        survey=survey if survey and survey.status == SURVEY_DONE else None,
        survey_units=survey_units,
        package=package,
        scope_items=scope,
        notes_body=notes_body,
        page_title=f'طباعة {quote.code}',
    )
