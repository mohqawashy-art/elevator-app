"""اختبارات فحص موقع عروض الصيانة."""
from __future__ import annotations

from datetime import date

from app import next_code
from models import (
    Customer,
    MaintenanceQuote,
    MaintenanceQuoteSurvey,
    MaintenanceQuoteSurveyUnit,
    Technician,
    db,
)
from sales.maint_survey import (
    complete_survey,
    create_survey_request,
    save_survey_units,
)
from sales.service import apply_total_including_tax, recalc_quote_totals
from tenant_scope import assign_organization

from tests.conftest import ensure_test_organization, login_as


def _sample_quote(*, customer_id: int) -> MaintenanceQuote:
    quote = MaintenanceQuote(
        code='MQ-SURV1',
        customer_id=customer_id,
        status='مسودة',
        duration_months=12,
        maint_frequency='شهري',
        visits_per_month=1,
        start_date=date.today(),
        city='مكة المكرمة',
        notes='باقة الخدمة: قياسي',
    )
    assign_organization(quote)
    apply_total_including_tax(quote, 2300)
    return quote


def test_create_survey_request(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-SV1', name='عميل فحص', status='نشط')
        db.session.add(cust)
        db.session.flush()
        tech = Technician(organization_id=oid, code='T-SV1', name='فني فحص', status='متاح')
        db.session.add(tech)
        db.session.flush()
        quote = _sample_quote(customer_id=cust.id)
        db.session.add(quote)
        db.session.commit()
        qid, tid = quote.id, tech.id

        survey = create_survey_request(
            db.session.get(MaintenanceQuote, qid),
            technician_id=tid,
            request_notes='زيارة غداً',
            next_code_fn=next_code,
        )
        db.session.commit()
        assert survey.code.startswith('MQS-')
        assert survey.status == 'مُرسَل'
        assert survey.technician_id == tid


def test_field_survey_save_and_complete(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-SV2', name='عميل فحص 2', status='نشط')
        db.session.add(cust)
        db.session.flush()
        tech = Technician(organization_id=oid, code='T-SV2', name='فني فحص 2', status='متاح')
        db.session.add(tech)
        db.session.flush()
        quote = _sample_quote(customer_id=cust.id)
        db.session.add(quote)
        db.session.commit()
        qid, tid = quote.id, tech.id

        survey = create_survey_request(
            db.session.get(MaintenanceQuote, qid),
            technician_id=tid,
            request_notes=None,
            next_code_fn=next_code,
        )
        db.session.commit()
        sid = survey.id

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tid

    r = client.get(f'/field/maint-quote-survey/{sid}')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'MQS-' in html

    units = [{
        'unit_label': 'مصعد 1',
        'building_name': 'برج أ',
        'elev_type': 'ركاب',
        'brand': 'KONE',
        'capacity_kg': 630,
        'floors': 8,
        'technical_opinion': 'مصعد بحالة جيدة — يصلح لعقد صيانة',
        'needs_repair': True,
        'repair_scope': 'استبدال حبال',
        'separate_quote_notes': 'عرض إصلاح منفصل',
    }]
    r2 = client.post(
        f'/api/field/maint-quote-survey/{sid}',
        json={'units': units},
    )
    assert r2.status_code == 200
    assert r2.get_json()['ok'] is True

    r3 = client.post(
        f'/api/field/maint-quote-survey/{sid}/complete',
        json={'units': units},
    )
    assert r3.status_code == 200
    assert r3.get_json()['ok'] is True

    with client.application.app_context():
        survey = db.session.get(MaintenanceQuoteSurvey, sid)
        assert survey.status == 'مكتمل'
        assert len(survey.units) == 1
        assert survey.units[0].elevator_id


def test_approve_quote_requires_completed_survey(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-SV3', name='عميل موافقة', status='نشط')
        db.session.add(cust)
        db.session.flush()
        tech = Technician(organization_id=oid, code='T-SV3', name='فني', status='متاح')
        db.session.add(tech)
        db.session.flush()
        quote = MaintenanceQuote(
            code='MQ-SV3',
            customer_id=cust.id,
            status='مُرسل',
            duration_months=12,
            maint_frequency='شهري',
            visits_per_month=1,
            start_date=date.today(),
        )
        assign_organization(quote)
        quote.value = 2000
        quote.tax_pct = 15
        recalc_quote_totals(quote)
        db.session.add(quote)
        db.session.commit()
        qid, tid = quote.id, tech.id

    r = client.post(f'/sales/maintenance-quotes/{qid}/approve', follow_redirects=False)
    assert r.status_code in (302, 303)

    with client.application.app_context():
        q = db.session.get(MaintenanceQuote, qid)
        assert q.status != 'مقبول'

    with client.application.app_context():
        quote = db.session.get(MaintenanceQuote, qid)
        survey = create_survey_request(
            quote,
            technician_id=tid,
            request_notes=None,
            next_code_fn=next_code,
        )
        db.session.flush()
        save_survey_units(
            survey.id,
            tech_id=tid,
            units=[{
                'elev_type': 'ركاب',
                'capacity_kg': 630,
                'floors': 5,
                'technical_opinion': 'جيد',
            }],
        )
        complete_survey(survey.id, tech_id=tid, next_elevator_code_fn=next_code)
        db.session.commit()

    r2 = client.post(f'/sales/maintenance-quotes/{qid}/approve', follow_redirects=True)
    assert r2.status_code == 200
    with client.application.app_context():
        q = db.session.get(MaintenanceQuote, qid)
        assert q.status == 'مقبول'
        assert q.result_contract_id


def test_print_shows_survey_units(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-SV4', name='عميل طباعة', status='نشط')
        db.session.add(cust)
        db.session.flush()
        tech = Technician(organization_id=oid, code='T-SV4', name='فني', status='متاح')
        db.session.add(tech)
        db.session.flush()
        quote = _sample_quote(customer_id=cust.id)
        db.session.add(quote)
        db.session.flush()
        survey = MaintenanceQuoteSurvey(
            quote_id=quote.id,
            code='MQS-90001',
            status='مكتمل',
            technician_id=tech.id,
        )
        assign_organization(survey)
        db.session.add(survey)
        db.session.flush()
        unit = MaintenanceQuoteSurveyUnit(
            survey_id=survey.id,
            unit_label='مصعد 1',
            elev_type='ركاب',
            capacity_kg=630,
            floors=6,
            technical_opinion='جاهز للصيانة',
            needs_repair=True,
            repair_scope='تبديل باب',
        )
        assign_organization(unit)
        db.session.add(unit)
        db.session.commit()
        qid = quote.id

    r = client.get(f'/sales/maintenance-quotes/{qid}/print')
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'المصاعد المفحوصة' in html
    assert 'الرأي الفني' in html
    assert 'عرض منفصل' in html


def test_request_survey_route_without_total_validation(client):
    """طلب الفحص لا يمرّ عبر حفظ العرض (لا يطلب الإجمالي)."""
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-SV5', name='عميل طلب', status='نشط')
        db.session.add(cust)
        db.session.flush()
        tech = Technician(organization_id=oid, code='T-SV5', name='فني', status='متاح')
        db.session.add(tech)
        db.session.flush()
        quote = MaintenanceQuote(
            code='MQ-SV5',
            customer_id=cust.id,
            status='مسودة',
            duration_months=12,
            value=0,
            total=0,
        )
        assign_organization(quote)
        db.session.add(quote)
        db.session.commit()
        qid, tid = quote.id, tech.id

    r = client.post(
        f'/sales/maintenance-quotes/{qid}/request-survey',
        data={'technician_id': str(tid), 'survey_notes': 'اختبار'},
        follow_redirects=True,
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'أدخل الإجمالي شامل الضريبة' not in html
    assert 'تم إرسال طلب فحص' in html or 'MQS-' in html


def test_complete_survey_requires_units_in_request(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-SV6', name='عميل إكمال', status='نشط')
        db.session.add(cust)
        db.session.flush()
        tech = Technician(organization_id=oid, code='T-SV6', name='فني', status='متاح')
        db.session.add(tech)
        db.session.flush()
        quote = _sample_quote(customer_id=cust.id)
        db.session.add(quote)
        db.session.flush()
        survey = create_survey_request(
            quote,
            technician_id=tech.id,
            request_notes=None,
            next_code_fn=next_code,
        )
        db.session.commit()
        sid, tid = survey.id, tech.id

    with client.session_transaction() as sess:
        sess['field_tech_id'] = tid

    r = client.post(f'/api/field/maint-quote-survey/{sid}/complete', json={})
    assert r.status_code == 400
    assert r.get_json()['ok'] is False


def test_field_payload_includes_maint_surveys(client):
    with client.application.app_context():
        oid = ensure_test_organization()
        tech = Technician(organization_id=oid, code='T-MQS', name='فني فحص', status='متاح')
        db.session.add(tech)
        db.session.flush()
        cust = Customer(organization_id=oid, code='C-MQS', name='عميل', status='نشط')
        db.session.add(cust)
        db.session.flush()
        quote = MaintenanceQuote(
            code='MQ-MQS1',
            customer_id=cust.id,
            status='مسودة',
            duration_months=12,
        )
        assign_organization(quote)
        apply_total_including_tax(quote, 1000)
        db.session.add(quote)
        db.session.flush()
        survey = MaintenanceQuoteSurvey(
            quote_id=quote.id,
            code='MQS-MQS1',
            status='مُرسَل',
            technician_id=tech.id,
        )
        assign_organization(survey)
        db.session.add(survey)
        db.session.commit()

        from operations import field_technician_payload

        payload = field_technician_payload(tech.id, portal_kind='both')
        assert payload.get('maint_surveys')
        assert any(s['code'] == 'MQS-MQS1' for s in payload['maint_surveys'])


def test_save_and_send_survey_new_quote(client):
    login_as(client, 'admin')
    with client.application.app_context():
        oid = ensure_test_organization()
        cust = Customer(organization_id=oid, code='C-SV7', name='عميل حفظ وإرسال', status='نشط')
        db.session.add(cust)
        db.session.flush()
        tech = Technician(organization_id=oid, code='T-SV7', name='فني معاينة', status='متاح')
        db.session.add(tech)
        db.session.commit()
        cid, tid = cust.id, tech.id

    r = client.post(
        '/sales/maintenance-quotes/new',
        data={
            'customer_id': str(cid),
            'technician_id': str(tid),
            'survey_notes': 'معاينة غداً',
            'action': 'save_send_survey',
            'city': 'مكة المكرمة',
            'duration_months': '12',
            'maint_frequency': 'شهري',
            'visits_per_month': '1',
            'total_incl_tax': '0',
            'tax_pct': '15',
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'تم حفظ العرض' in html
    assert 'إرسال طلب فحص' in html or 'للمعاينة' in html

    with client.application.app_context():
        survey = MaintenanceQuoteSurvey.query.order_by(MaintenanceQuoteSurvey.id.desc()).first()
        assert survey is not None
        assert survey.status == 'مُرسَل'
        assert survey.technician_id == tid
