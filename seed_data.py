"""
LiftCore — بيانات تجريبية شاملة للوحة التحكم
seed_data.py

الاستخدام:
    python seed_data.py           # يضيف البيانات إذا كانت القاعدة فارغة
    python seed_data.py --reset   # يمسح البيانات التشغيلية ويعيد الإدراج

لنسخ قاعدة البيانات الحالية كاملة (للعمل من جهاز آخر):
    python tools/db_snapshot.py export
    python tools/db_snapshot.py restore
"""

import json
import os
import sys
from datetime import date, datetime, timedelta

from flask import g

from app import app, db, hash_password
from models import (
    Customer, Elevator, Contract, ContractElevator, Technician,
    MaintenanceVisit, Fault, Revenue, Expense, Invoice,
    InventoryItem, StockMovement, PartsBilling, User, Settings,
    VisitTechnician, FaultTechnician, PurchaseOrder, PurchaseOrderLine,
    ElevatorEstimate, ElevatorEstimateLine, TechnicianDocument, Signatory,
    MaintenanceTeam, WhatsAppInbox, MaintenanceQuote, MaintenanceQuoteElevator,
    MaintenanceQuoteSurvey, MaintenanceQuoteSurveyUnit,
)


CITY = 'مكة المكرمة'


def _d(days_offset=0):
    return date.today() + timedelta(days=days_offset)


def _dt(days_offset=0, hour=10, minute=0):
    return datetime.combine(_d(days_offset), datetime.min.time().replace(hour=hour, minute=minute))


def _maps(lat, lng):
    return f'https://www.google.com/maps?q={lat},{lng}'


def _bind_demo_org():
    """يربط جلسة السيد بمؤسسة جما إن وُجدت، وإلا default."""
    from models import Organization

    slug = (os.environ.get('LIFTCORE_DEMO_ORG') or '').strip().lower()
    org = Organization.query.filter_by(slug=slug).first() if slug else None
    if not org:
        org = Organization.query.filter_by(slug='jama').first()
    if not org:
        org = Organization.query.filter_by(slug='default').first()
    if not org:
        org = Organization(
            slug='default',
            name='LiftCore Demo',
            status='active',
            plan='pro',
        )
        db.session.add(org)
        db.session.flush()
    g.organization = org
    g.organization_id = org.id
    return org.id


def _oid():
    return int(g.organization_id)


def _scoped(model):
    q = model.query.execution_options(skip_tenant=True)
    oid = getattr(g, 'organization_id', None)
    if oid:
        q = q.filter_by(organization_id=oid)
    return q


def clear_business_data():
    """مسح البيانات التشغيلية مع الإبقاء على المستخدمين والإعدادات."""
    _scoped(MaintenanceVisit).filter(MaintenanceVisit.fault_id.isnot(None)).update(
        {MaintenanceVisit.fault_id: None}, synchronize_session=False
    )
    _scoped(Fault).filter(Fault.visit_id.isnot(None)).update(
        {Fault.visit_id: None}, synchronize_session=False
    )
    if hasattr(Invoice, 'revenue_id'):
        _scoped(Invoice).update(
            {Invoice.revenue_id: None, Invoice.parent_invoice_id: None, Invoice.parts_billing_id: None},
            synchronize_session=False,
        )
    if hasattr(Revenue, 'invoice_id'):
        _scoped(Revenue).update(
            {Revenue.invoice_id: None, Revenue.parts_billing_id: None},
            synchronize_session=False,
        )
    db.session.commit()

    try:
        import installation.models as im
        if hasattr(im, 'InstallProject'):
            _scoped(im.InstallProject).update(
                {
                    im.InstallProject.accepted_quotation_id: None,
                    im.InstallProject.lead_id: None,
                    im.InstallProject.contract_id: None,
                },
                synchronize_session=False,
            )
            db.session.commit()
        install_models = [
            getattr(im, 'InstallContractDocument', None),
            getattr(im, 'InstallContractInstallment', None),
            getattr(im, 'InstallProjectDocument', None),
            getattr(im, 'InstallProjectReceipt', None),
            getattr(im, 'InstallProjectCostItem', None),
            getattr(im, 'InstallTimelineStep', None),
            getattr(im, 'InstallQuotationLine', None),
            getattr(im, 'InstallContract', None),
            getattr(im, 'InstallQuotation', None),
            getattr(im, 'InstallProject', None),
            getattr(im, 'InstallLead', None),
        ]
        for model in install_models:
            if model is not None:
                _scoped(model).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()

    for model in (
        VisitTechnician, FaultTechnician,
        MaintenanceQuoteSurveyUnit, MaintenanceQuoteSurvey,
        MaintenanceQuoteElevator, MaintenanceQuote,
        WhatsAppInbox,
        StockMovement, PartsBilling,
        PurchaseOrderLine, PurchaseOrder,
        ElevatorEstimateLine, ElevatorEstimate,
        Revenue, Expense, Invoice,
        MaintenanceVisit, Fault,
        ContractElevator, Contract,
        Elevator,
        TechnicianDocument, Signatory,
        MaintenanceTeam,
        Technician, InventoryItem, Customer,
    ):
        _scoped(model).delete()
    db.session.commit()


def _ensure_jama_settings() -> None:
    oid = _oid()
    s = _scoped(Settings).first()
    if not s:
        s = Settings(
            organization_id=oid,
            company_name='شركة جما تقنية للمصاعد',
            company_name_en='Jama Elevator Technology Co.',
            phone='0500000000',
            email='info@jama.liftcore.sa',
            city=CITY,
            tax_pct=15,
            currency='ر.س',
            language='ar',
            default_sign_method='both',
        )
        db.session.add(s)
    else:
        s.company_name = s.company_name or 'شركة جما تقنية للمصاعد'
        s.company_name_en = s.company_name_en or 'Jama Elevator Technology Co.'
        s.city = CITY
        s.default_sign_method = s.default_sign_method or 'both'


def _ensure_admin_user() -> None:
    oid = _oid()
    admin = User.query.execution_options(skip_tenant=True).filter_by(
        username='admin', organization_id=oid
    ).first()
    if not admin:
        db.session.add(
            User(
                organization_id=oid,
                username='admin',
                password_hash=hash_password('admin123'),
                full_name='مدير جما (تجريبي)',
                email='admin@jama.liftcore.sa',
                role='admin',
                is_active=True,
            )
        )
    else:
        admin.password_hash = hash_password('admin123')
        admin.is_active = True


def _sample_checklist_json() -> str:
    from checklist_templates import empty_report_data

    data = empty_report_data()
    data['meta']['overall_status'] = 'جيدة'
    data['meta']['visit_date'] = _d().isoformat()
    data['meta']['arrival_time'] = '09:00'
    data['meta']['end_time'] = '10:15'
    data['meta']['tech_notes'] = 'فحص دوري — لا ملاحظات حرجة'
    for item_id in ('1_0', '1_1', '2_0', '3_0', '4_0'):
        if item_id in data['items']:
            data['items'][item_id] = {'status': 'ok', 'note': ''}
    return json.dumps(data, ensure_ascii=False)


def _sample_fault_report_json(*, solved: bool = False) -> str:
    from fault_report import empty_report

    data = empty_report()
    data['meta']['visit_date'] = _d().isoformat()
    data['meta']['arrival_time'] = '11:00'
    data['meta']['end_time'] = '12:30'
    data['meta']['diagnosis'] = 'خلل في حساس الباب — يحتاج ضبط'
    data['meta']['action_taken'] = 'ضبط المستشعر واختبار 5 دورات'
    data['meta']['visit_outcome'] = 'solved' if solved else 'partial'
    return json.dumps(data, ensure_ascii=False)


def _seed_demo_extras() -> None:
    """بيانات إضافية لتجربة كل وحدات البرنامج."""
    from technician_assignments import sync_visit_technicians, sync_fault_technicians

    oid = _oid()
    techs = _scoped(Technician).order_by(Technician.id).all()
    if not techs:
        return

    demo_pin = hash_password('123456')
    demo_ids = (
        '1012345678', '1023456789', '1034567890', '1045678901',
        '1056789012', '1067890123', '1078901234',
    )
    active_statuses = frozenset({'نشط', 'متاح', 'مشغول'})
    pin_idx = 0
    for tech in techs:
        if (tech.status or 'متاح') not in active_statuses:
            continue
        tech.sign_pin_hash = demo_pin
        if pin_idx < len(demo_ids):
            tech.national_id = demo_ids[pin_idx]
            pin_idx += 1

    today_visits = (
        _scoped(MaintenanceVisit)
        .filter_by(visit_date=_d())
        .order_by(MaintenanceVisit.id)
        .limit(5)
        .all()
    )
    for v in today_visits:
        if len(techs) >= 2:
            sync_visit_technicians(v, [techs[0].id, techs[1].id])
        if v.status == 'مكتملة' and not v.checklist_json:
            v.checklist_json = _sample_checklist_json()
            v.completed_at = v.completed_at or _dt(0, 10, 30)

    completed = (
        _scoped(MaintenanceVisit)
        .filter_by(status='مكتملة')
        .filter(MaintenanceVisit.checklist_json.is_(None))
        .limit(6)
        .all()
    )
    for v in completed:
        v.checklist_json = _sample_checklist_json()

    open_fault = _scoped(Fault).filter_by(code='FA-02041').first()
    if open_fault and len(techs) >= 3:
        sync_fault_technicians(open_fault, [techs[0].id, techs[2].id])
        if not open_fault.report_json:
            open_fault.report_json = _sample_fault_report_json(solved=False)

    solved_fault = _scoped(Fault).filter_by(code='FA-02010').first()
    if solved_fault and not solved_fault.report_json:
        solved_fault.report_json = _sample_fault_report_json(solved=True)

    items = _scoped(InventoryItem).order_by(InventoryItem.id).limit(6).all()
    if items:
        po = PurchaseOrder(
            organization_id=oid,
            code='PO-00001',
            supplier='مورد المصاعد المتحدة',
            supplier_phone='0501234567',
            order_date=_d(-5),
            status='معتمد',
            total_amount=sum(i.buy_price or 0 for i in items[:2]) * 2,
            notes='طلب تجريبي — قطع غيار عاجلة',
        )
        db.session.add(po)
        db.session.flush()
        for item in items[:2]:
            qty = 2
            price = item.buy_price or 0
            db.session.add(PurchaseOrderLine(
                organization_id=oid,
                order_id=po.id,
                item_id=item.id,
                quantity=qty,
                unit_price=price,
                line_total=qty * price,
            ))

        po2 = PurchaseOrder(
            organization_id=oid,
            code='PO-00002',
            supplier='شركة الحبال الفولاذية',
            order_date=_d(-1),
            status='مسودة',
            total_amount=(items[2].buy_price or 0) * 5,
        )
        db.session.add(po2)
        db.session.flush()
        db.session.add(PurchaseOrderLine(
            organization_id=oid,
            order_id=po2.id,
            item_id=items[2].id,
            quantity=5,
            unit_price=items[2].buy_price or 0,
            line_total=5 * (items[2].buy_price or 0),
        ))

        if len(items) >= 5:
            po3 = PurchaseOrder(
                organization_id=oid,
                code='PO-00003',
                supplier='البيت الفني للكهرباء',
                supplier_phone='0507654321',
                order_date=_d(-12),
                status='مستلم',
                total_amount=(items[4].buy_price or 0) * 8,
                notes='مستشعرات وأبواب — تم الاستلام',
            )
            db.session.add(po3)
            db.session.flush()
            db.session.add(PurchaseOrderLine(
                organization_id=oid,
                order_id=po3.id,
                item_id=items[4].id,
                quantity=8,
                unit_price=items[4].buy_price or 0,
                line_total=8 * (items[4].buy_price or 0),
            ))

        if len(items) >= 6:
            po4 = PurchaseOrder(
                organization_id=oid,
                code='PO-00004',
                supplier='مورد المصاعد المتحدة',
                order_date=_d(-2),
                status='مرسل',
                total_amount=(items[5].buy_price or 0) * 10,
            )
            db.session.add(po4)
            db.session.flush()
            db.session.add(PurchaseOrderLine(
                organization_id=oid,
                order_id=po4.id,
                item_id=items[5].id,
                quantity=10,
                unit_price=items[5].buy_price or 0,
                line_total=10 * (items[5].buy_price or 0),
            ))

    client = _scoped(Customer).filter_by(code='C-0010').first()
    if client:
        est = ElevatorEstimate(
            organization_id=oid,
            code='ES-0001',
            customer_id=client.id,
            project_name='توسعة فندق مكة كلوك',
            city=CITY,
            machine_type='MR',
            elev_type='مصعد ركاب',
            floors=16,
            stops=16,
            capacity_kg=1000,
            margin_pct=12,
            vat_pct=15,
            cost_subtotal=185000,
            margin_amount=22200,
            subtotal=207200,
            vat_amount=31080,
            total=238280,
            status='مسودة',
            estimate_date=_d(-7),
            notes='تقدير تجريبي لعميل فندق',
        )
        db.session.add(est)
        db.session.flush()
        for desc, amt in (
            ('محرك رئيسي + بكرة', 95000),
            ('كابينة + أبواب', 62000),
            ('تركيب وتشغيل', 28000),
        ):
            db.session.add(ElevatorEstimateLine(
                organization_id=oid,
                estimate_id=est.id,
                description=desc,
                quantity=1,
                unit_price=amt,
                line_total=amt,
            ))

    client2 = _scoped(Customer).filter_by(code='C-0014').first()
    if client2:
        est2 = ElevatorEstimate(
            organization_id=oid,
            code='ES-0002',
            customer_id=client2.id,
            project_name='برج الصفا — مصعد بضائع',
            city=CITY,
            machine_type='MR',
            elev_type='مصعد بضائع',
            floors=8,
            stops=8,
            capacity_kg=1600,
            margin_pct=15,
            vat_pct=15,
            cost_subtotal=142000,
            margin_amount=21300,
            subtotal=163300,
            vat_amount=24495,
            total=187795,
            status='مُرسل',
            estimate_date=_d(-14),
            notes='تقدير تركيب مصعد خدمة',
        )
        db.session.add(est2)
        db.session.flush()
        for desc, amt in (
            ('ماكينة وشاسيه', 78000),
            ('سكك وأبواب', 41000),
            ('عمالة وتركيب', 23000),
        ):
            db.session.add(ElevatorEstimateLine(
                organization_id=oid,
                estimate_id=est2.id,
                description=desc,
                quantity=1,
                unit_price=amt,
                line_total=amt,
            ))

    client3 = _scoped(Customer).filter_by(code='C-0018').first()
    if client3:
        est3 = ElevatorEstimate(
            organization_id=oid,
            code='ES-0003',
            customer_id=client3.id,
            project_name='مجمع الجامعة — تحديث مجموعة',
            city=CITY,
            machine_type='MRL',
            elev_type='مصعد ركاب',
            floors=12,
            stops=12,
            capacity_kg=800,
            margin_pct=10,
            vat_pct=15,
            cost_subtotal=98000,
            margin_amount=9800,
            subtotal=107800,
            vat_amount=16170,
            total=123970,
            status='مقبول',
            estimate_date=_d(-21),
        )
        db.session.add(est3)
        db.session.flush()
        db.session.add(ElevatorEstimateLine(
            organization_id=oid,
            estimate_id=est3.id,
            description='تحديث كنترول VVVF',
            quantity=1,
            unit_price=98000,
            line_total=98000,
        ))

    _seed_sales_and_field_extras(techs)
    _seed_installation_demo()


def _seed_sales_and_field_extras(techs) -> None:
    oid = _oid()
    clients = {c.code: c for c in _scoped(Customer).all()}
    elevators = _scoped(Elevator).order_by(Elevator.id).all()
    if len(techs) >= 4:
        db.session.add_all([
            MaintenanceTeam(
                organization_id=oid, code='MT-001', name='فريق العزيزية',
                leader_id=techs[0].id, assistant_id=techs[2].id, active=True, sort_order=1,
            ),
            MaintenanceTeam(
                organization_id=oid, code='MT-002', name='فريق الشوقية',
                leader_id=techs[1].id, assistant_id=techs[4].id if len(techs) > 4 else techs[3].id,
                active=True, sort_order=2,
            ),
            MaintenanceTeam(
                organization_id=oid, code='MT-003', name='فريق الطوارئ',
                leader_id=techs[3].id, assistant_id=None, active=True, sort_order=3,
                notes='استجابة أعطال حرجة داخل مكة',
            ),
        ])

    c1 = clients.get('C-0009')
    c2 = clients.get('C-0015')
    if c1 and elevators:
        q1 = MaintenanceQuote(
            organization_id=oid, code='MQ-0001', customer_id=c1.id,
            status='مُرسل', duration_months=12, maint_frequency='شهري',
            visits_per_month=1, value=36000, tax_pct=15, tax_amount=5400, total=41400,
            payment_terms='ربع سنوي', start_date=_d(10), end_date=_d(375),
            city=CITY, district=c1.district, address=c1.address,
            notes='عرض تجديد عقد مجمع الروضة',
            sent_at=_dt(-3, 11),
        )
        db.session.add(q1)
        db.session.flush()
        db.session.add(MaintenanceQuoteElevator(
            organization_id=oid, quote_id=q1.id, elevator_id=elevators[min(10, len(elevators) - 1)].id
        ))
    if c2 and elevators:
        q2 = MaintenanceQuote(
            organization_id=oid, code='MQ-0002', customer_id=c2.id,
            status='مسودة', duration_months=12, maint_frequency='شهري',
            visits_per_month=2, value=54000, tax_pct=15, tax_amount=8100, total=62100,
            payment_terms='نصف سنوي', city=CITY, district=c2.district,
        )
        db.session.add(q2)
        db.session.flush()
        db.session.add(MaintenanceQuoteElevator(
            organization_id=oid, quote_id=q2.id, elevator_id=elevators[min(16, len(elevators) - 1)].id
        ))
    c3 = clients.get('C-0012')
    if c3 and elevators:
        q3 = MaintenanceQuote(
            organization_id=oid, code='MQ-0003', customer_id=c3.id,
            status='مقبول', duration_months=12, maint_frequency='شهري',
            visits_per_month=1, value=28000, tax_pct=15, tax_amount=4200, total=32200,
            payment_terms='ربع سنوي', city=CITY, district=c3.district,
            approved_at=_dt(-1, 16),
        )
        db.session.add(q3)

    wa_rows = [
        ('WA-00001', '0501111004', 'مستشفى السلام', 'المصعد الرئيسي واقف في الدور الثالث', 'جديد', clients.get('C-0004')),
        ('WA-00002', '0501111001', 'برج الياسمين', 'في صوت غريب من الماكينة', 'مربوط', clients.get('C-0001')),
        ('WA-00003', '0501111006', 'مجمع التجارة', 'الباب ما يقفل كامل', 'تم إنشاء عطل', clients.get('C-0006')),
        ('WA-00004', '0501111019', 'أبراج البيت', 'طلب صيانة دورية إضافية هذا الأسبوع', 'مغلق', clients.get('C-0019')),
    ]
    for code, phone, name, body, status, cust in wa_rows:
        db.session.add(WhatsAppInbox(
            organization_id=oid, code=code, direction='inbound',
            from_phone=phone, from_name=name, body=body, status=status,
            receive_target='office',
            customer_id=cust.id if cust else None,
            received_at=_dt(-1 if status != 'جديد' else 0, 8, 40),
        ))


def _seed_installation_demo() -> None:
    try:
        from installation.models import (
            InstallLead, InstallProject, InstallQuotation, InstallQuotationLine,
            InstallTimelineStep, InstallProjectCostItem, InstallProjectReceipt,
        )
    except Exception:
        return

    oid = _oid()
    clients = {c.code: c for c in _scoped(Customer).all()}
    hotel = clients.get('C-0010')
    safa = clients.get('C-0014')
    uni = clients.get('C-0018')
    clock = clients.get('C-0019')

    leads_spec = [
        ('LD-0001', hotel, 'فندق مكة كلوك', '0501111010', 'واتساب', 'فندق', 'تم تحويله لمشروع', 'العوالي'),
        ('LD-0002', safa, 'برج الصفا التجاري', '0501111014', 'اتصال', 'برج مكتبي', 'موعد معاينة', 'الشوقية'),
        ('LD-0003', uni, 'إسكان جامعة أم القرى', '0501111018', 'مندوب', 'سكني', 'جاري التواصل', 'العابدية'),
        ('LD-0004', None, 'عميل جديد — العزيزية', '0501111099', 'موقع إلكتروني', 'سكني', 'جديد', 'العزيزية'),
    ]
    leads = []
    for code, cust, name, phone, source, btype, status, district in leads_spec:
        lead = InstallLead(
            organization_id=oid, code=code,
            inquiry_date=_d(-18 if 'مشروع' in status else -4),
            customer_id=cust.id if cust else None,
            client_name=name, phone=phone, city=CITY, district=district,
            source=source, building_type=btype, status=status,
            notes='فرصة تركيب داخل مكة المكرمة',
        )
        leads.append(lead)
    db.session.add_all(leads)
    db.session.flush()

    if not hotel:
        return

    p1 = InstallProject(
        organization_id=oid, code='PRJ-0001',
        title='تركيب مصعد ركاب — فندق مكة كلوك',
        status='تركيب', customer_id=hotel.id, lead_id=leads[0].id,
        contract_value=238280, notes='مشروع قيد التنفيذ داخل مكة',
        execution_started_at=_dt(-20, 8),
    )
    db.session.add(p1)
    db.session.flush()

    q = InstallQuotation(
        organization_id=oid, code='QT-0001', project_id=p1.id,
        customer_id=hotel.id, quote_type='new', status='مقبول',
        client_name=hotel.name, client_phone=hotel.phone,
        client_address=hotel.address, valid_days=30,
        labor=28000, transport=2000, other_costs=0, profit_pct=12,
        materials_total=157000, cost_total=187000, profit_amount=22200,
        before_tax=207200, vat_amount=31080, grand_total=238280,
        pay_advance_pct=50, pay_supply_pct=40, pay_final_pct=10,
        approved_at=_dt(-25, 12),
    )
    db.session.add(q)
    db.session.flush()
    p1.accepted_quotation_id = q.id
    for i, (name, qty, price) in enumerate((
        ('محرك رئيسي', 1, 95000),
        ('كابينة ستانلس', 1, 42000),
        ('أبواب أوتوماتيك', 2, 10000),
    ), start=1):
        db.session.add(InstallQuotationLine(
            organization_id=oid, quotation_id=q.id, stage='توريد',
            name=name, unit='قطعة', qty=qty, unit_price=price, sort_order=i,
        ))
    for i, (key, title, group, status, amount) in enumerate((
        ('survey', 'معاينة الموقع', 'هندسة', 'مكتمل', 0),
        ('advance', 'دفعة التعاقد', 'عقد', 'مكتمل', 119140),
        ('supply', 'توريد المعدة', 'توريد', 'مكتمل', 95200),
        ('install', 'التركيب في الموقع', 'تركيب', 'جاري', 0),
        ('handover', 'التسليم والتشغيل', 'تسليم', 'قادم', 23940),
    ), start=1):
        db.session.add(InstallTimelineStep(
            organization_id=oid, project_id=p1.id, step_key=key, title=title,
            phase_group=group, sort_order=i, status=status, has_amount=amount > 0,
            amount=amount, planned_date=_d(-30 + i * 7),
        ))
    db.session.add(InstallProjectCostItem(
        organization_id=oid, project_id=p1.id, category='الماكينة والشاسيه',
        title='دفعة الماكينة', amount=78000, cost_date=_d(-12), payment_status='مدفوعة',
    ))
    db.session.add(InstallProjectReceipt(
        organization_id=oid, project_id=p1.id, installment_no=1,
        label='دفعة مقدمة', amount=119140, received_date=_d(-22),
        payment_method='تحويل', status='مستلمة',
    ))

    if safa:
        p2 = InstallProject(
            organization_id=oid, code='PRJ-0002',
            title='تحديث مصعد خدمة — برج الصفا',
            status='عرض سعر', customer_id=safa.id, lead_id=leads[1].id,
            notes='بانتظار اعتماد العميل',
        )
        db.session.add(p2)
        db.session.flush()
        db.session.add(InstallQuotation(
            organization_id=oid, code='QT-0002', project_id=p2.id,
            customer_id=safa.id, quote_type='upgrade', status='مُرسل',
            client_name=safa.name, labor=18000, materials_total=90000,
            cost_total=110000, profit_amount=16500, before_tax=126500,
            vat_amount=18975, grand_total=145475,
        ))

    if uni:
        db.session.add(InstallProject(
            organization_id=oid, code='PRJ-0003',
            title='معاينة إسكان الجامعة',
            status='معاينة', customer_id=uni.id, lead_id=leads[2].id,
        ))

    if clock:
        db.session.add(InstallProject(
            organization_id=oid, code='PRJ-0004',
            title='استفسار أبراج البيت — مجموعة ركاب',
            status='استفسار', customer_id=clock.id,
        ))


def seed_all(*, force: bool = False):
  with app.app_context():
    db.create_all()
    oid = _bind_demo_org()

    if not force and _scoped(Customer).count() > 0:
        print("[!] Database already has data. Use --reset or reset_jama_demo().")
        return False

    today = date.today()
    year = today.year

    # إحداثيات أحياء مكة فقط (حرم + أحياء المدينة — بعيداً عن جدة)
    clients_data = [
        dict(code='C-0001', name='برج الياسمين', name_en='Alyasmeen Tower', district='العزيزية',
             address='شارع إبراهيم الخليل، برج الياسمين', phone='0501111001',
             lat='21.4038', lng='39.8765', contact_person='مشرف المبنى'),
        dict(code='C-0002', name='مجمع النخيل', name_en='Al Nakheel Complex', district='الرصيفة',
             address='طريق الملك عبدالعزيز، مجمع النخيل', phone='0501111002',
             lat='21.4368', lng='39.8085', contact_person='مدير العقار'),
        dict(code='C-0003', name='فندق الأندلس', name_en='Al Andalus Hotel', district='العابدية',
             address='حي العابدية، شارع إبراهيم الخليل', phone='0501111003',
             lat='21.3889', lng='39.8217', contact_person='مهندس الصيانة'),
        dict(code='C-0004', name='مستشفى السلام', name_en='Al Salam Hospital', district='النزهة',
             address='شارع النزهة، مستشفى السلام الطبي', phone='0501111004',
             lat='21.4256', lng='39.8522', contact_person='مدير الخدمات'),
        dict(code='C-0005', name='برج المملكة', name_en='Al Mamlaka Tower', district='الروضة',
             address='حي الروضة، برج المملكة التجاري', phone='0501111005',
             lat='21.3925', lng='39.8843', contact_person='مسؤول العقود'),
        dict(code='C-0006', name='مجمع التجارة', name_en='Tijara Mall', district='أجياد',
             address='أجياد، مجمع التجارة، المدخل الشرقي', phone='0501111006',
             lat='21.4188', lng='39.8274', contact_person='مشرف الأمن'),
        dict(code='C-0007', name='مركز الملك عبدالله الطبي', name_en='KAMC Makkah', district='العوالي',
             address='العوالي، مركز الملك عبدالله الطبي', phone='0501111007',
             lat='21.3688', lng='39.8680', contact_person='رئيس الصيانة'),
        dict(code='C-0008', name='برج الفيصلية', name_en='Al Faisaliah Tower', district='الزاهر',
             address='حي الزاهر، برج الفيصلية', phone='0501111008',
             lat='21.4442', lng='39.8228', contact_person='مدير البرج'),
        dict(code='C-0009', name='مجمع الروضة', name_en='Al Rawdah Residences', district='الروضة',
             address='حي الروضة، مجمع الروضة السكني', phone='0501111009',
             lat='21.3974', lng='39.8725', contact_person='حارس المجمع'),
        dict(code='C-0010', name='فندق مكة كلوك', name_en='Makkah Clock Hotel', district='أجياد',
             address='أجياد، فندق مكة ساعة، بجوار الحرم', phone='0501111010',
             lat='21.4186', lng='39.8255', contact_person='مدير الهندسة'),
        dict(code='C-0011', name='أبراج الصفا', name_en='Safa Towers', district='الشوقية',
             address='حي الشوقية، أبراج الصفا', phone='0501111011',
             lat='21.3654', lng='39.8248', contact_person='مشرف المبنى'),
        dict(code='C-0012', name='مجمع الكعكية', name_en='Al Kakiyyah Plaza', district='الكعكية',
             address='الكعكية، طريق الليث', phone='0501111012',
             lat='21.3782', lng='39.7968', contact_person='مدير الأملاك'),
        dict(code='C-0013', name='مستشفى النور', name_en='Al Noor Specialist', district='الشهداء',
             address='حي الشهداء، مستشفى النور التخصصي', phone='0501111013',
             lat='21.4528', lng='39.8465', contact_person='مهندس الأجهزة'),
        dict(code='C-0014', name='برج الصفا التجاري', name_en='Safa Business Tower', district='الشوقية',
             address='الشوقية، برج الصفا التجاري', phone='0501111014',
             lat='21.3712', lng='39.8310', contact_person='مدير التشغيل'),
        dict(code='C-0015', name='إسكان العتيبية', name_en='Otaybiyah Housing', district='العتيبية',
             address='العتيبية، مجمع الإسكان', phone='0501111015',
             lat='21.4386', lng='39.7988', contact_person='مشرف الإسكان'),
        dict(code='C-0016', name='فندق جرول بلازا', name_en='Jarwal Plaza', district='جرول',
             address='جرول، فندق جرول بلازا', phone='0501111016',
             lat='21.4308', lng='39.8142', contact_person='مدير الفندق'),
        dict(code='C-0017', name='مجمع الهنداوية', name_en='Hindawiyah Complex', district='الهنداوية',
             address='الهنداوية، شارع المنصور', phone='0501111017',
             lat='21.4235', lng='39.8048', contact_person='مسؤول الصيانة'),
        dict(code='C-0018', name='إسكان جامعة أم القرى', name_en='UQU Housing', district='العابدية',
             address='العابدية، إسكان الجامعة', phone='0501111018',
             lat='21.3298', lng='39.9522', contact_person='إدارة الإسكان'),
        dict(code='C-0019', name='أبراج البيت — إقامة', name_en='Abraj Al Bait', district='أجياد',
             address='أجياد، أبراج البيت', phone='0501111019',
             lat='21.4197', lng='39.8262', contact_person='مهندس المصاعد'),
        dict(code='C-0020', name='مجمع التنعيم', name_en='Tanym Residences', district='التنعيم',
             address='التنعيم، طريق المدينة', phone='0501111020',
             lat='21.4846', lng='39.8018', contact_person='حارس المجمع'),
        dict(code='C-0021', name='برج ولي العهد', name_en='Wali Al Ahd Tower', district='ولي العهد',
             address='حي ولي العهد، البرج السكني', phone='0501111021',
             lat='21.3724', lng='39.8496', contact_person='مشرف البرج'),
        dict(code='C-0022', name='مجمع العدل', name_en='Al Adl Complex', district='العدل',
             address='حي العدل، مجمع العدل التجاري', phone='0501111022',
             lat='21.4418', lng='39.8784', contact_person='مدير المجمع'),
    ]
    clients = []
    for row in clients_data:
        lat, lng = row['lat'], row['lng']
        clients.append(Customer(
            organization_id=oid,
            code=row['code'],
            name=row['name'],
            name_en=row.get('name_en') or '',
            city=CITY,
            district=row['district'],
            address=row['address'],
            phone=row['phone'],
            contact_person=row.get('contact_person') or '',
            status='نشط',
            entity_type='شركة',
            lat=lat,
            lng=lng,
            maps_url=_maps(lat, lng),
            notes='عميل تجريبي للعرض — مكة المكرمة',
        ))
    db.session.add_all(clients)
    db.session.flush()

    districts_json = json.dumps(
        ['العزيزية', 'الشوقية', 'أجياد', 'الزاهر', 'العوالي', 'الرصيفة'],
        ensure_ascii=False,
    )
    techs_data = [
        dict(code='Tech-001', name='أحمد الزهراني',  phone='0552001001', job_title='فني أول',   specialization='مصاعد ركاب', status='متاح', emergency=True, team='صيانة'),
        dict(code='Tech-002', name='خالد العمري',    phone='0552001002', job_title='فني أول',   specialization='كهرباء',      status='متاح', emergency=True, team='أعطال'),
        dict(code='Tech-003', name='سعد القحطاني',   phone='0552001003', job_title='فني ثانٍ', specialization='ميكانيكا',    status='متاح', team='صيانة'),
        dict(code='Tech-004', name='فهد المالكي',    phone='0552001004', job_title='فني أول',   specialization='مصاعد ركاب', status='مشغول', team='أعطال'),
        dict(code='Tech-005', name='عمر الدوسري',    phone='0552001005', job_title='فني ثانٍ', specialization='ميكانيكا',    status='متاح', team='صيانة'),
        dict(code='Tech-006', name='محمد الشهري',    phone='0552001006', job_title='مشرف',     specialization='مصاعد ركاب', status='إجازة', team='عام'),
        dict(code='Tech-007', name='يوسف الغامدي',   phone='0552001007', job_title='فني أول',   specialization='كهرباء',      status='غير نشط', team='أعطال'),
        dict(code='Tech-008', name='بندر الحربي',    phone='0552001008', job_title='فني أول',   specialization='مصاعد ركاب', status='متاح', emergency=True, team='صيانة'),
    ]
    techs = [Technician(
        organization_id=oid, city=CITY, districts_json=districts_json, **t
    ) for t in techs_data]
    db.session.add_all(techs)
    db.session.flush()

    elev_specs = [
        (0, 'EL-0124', 'برج الياسمين — ركاب 1',  'مصعد ركاب', 'Otis',    1000, 15),
        (0, 'EL-0125', 'برج الياسمين — خدمة',    'مصعد بضائع','Schindler',2000, 8),
        (1, 'EL-0087', 'مجمع النخيل A',          'مصعد ركاب', 'Kone',    800,  10),
        (1, 'EL-0088', 'مجمع النخيل B',          'مصعد ركاب', 'Otis',    800,  10),
        (2, 'EL-0201', 'فندق الأندلس — ركاب',    'مصعد ركاب', 'Mitsubishi',630, 12),
        (3, 'EL-0033', 'مستشفى السلام — طبي',    'مصعد مستشفى','Otis',   1600, 8),
        (3, 'EL-0034', 'مستشفى السلام — ركاب',   'مصعد ركاب', 'Otis',    1000, 8),
        (4, 'EL-0156', 'برج المملكة',            'مصعد ركاب', 'Kone',    1000, 20),
        (5, 'EL-0091', 'مجمع التجارة',           'مصعد ركاب', 'Schindler',1000, 6),
        (6, 'EL-0044', 'الملك عبدالله — ركاب',   'مصعد ركاب', 'Otis',    630,  7),
        (6, 'EL-0045', 'الملك عبدالله — طبي',    'مصعد مستشفى','Kone',   1600, 10),
        (7, 'EL-0178', 'برج الفيصلية',           'مصعد ركاب', 'Kone',    1000, 18),
        (8, 'EL-0220', 'مجمع الروضة',            'مصعد ركاب', 'Otis',    800,  9),
        (9, 'EL-0305', 'مكة كلوك — ركاب 1',      'مصعد ركاب', 'Mitsubishi',1000,14),
        (9, 'EL-0306', 'مكة كلوك — ركاب 2',      'مصعد ركاب', 'Mitsubishi',1000,14),
        (10,'EL-0310', 'أبراج الصفا A',          'مصعد ركاب', 'Schindler',800, 11),
        (11,'EL-0314', 'مجمع الكعكية',           'مصعد ركاب', 'Otis',    630,  7),
        (12,'EL-0318', 'مستشفى النور',           'مصعد مستشفى','Kone',   1600, 9),
        (13,'EL-0322', 'برج الصفا — خدمة',       'مصعد بضائع','Otis',    2000, 8),
        (14,'EL-0326', 'إسكان العتيبية 1',       'مصعد ركاب', 'Kone',    630,  6),
        (14,'EL-0327', 'إسكان العتيبية 2',       'مصعد ركاب', 'Kone',    630,  6),
        (15,'EL-0330', 'جرول بلازا',             'مصعد ركاب', 'Mitsubishi',800, 10),
        (16,'EL-0334', 'مجمع الهنداوية',         'مصعد ركاب', 'Schindler',800, 8),
        (17,'EL-0338', 'إسكان الجامعة',          'مصعد ركاب', 'Otis',    1000, 12),
        (18,'EL-0342', 'أبراج البيت — ركاب',     'مصعد ركاب', 'Kone',    1600, 18),
        (19,'EL-0346', 'مجمع التنعيم',           'مصعد ركاب', 'Otis',    630,  5),
        (20,'EL-0350', 'برج ولي العهد',          'مصعد ركاب', 'Schindler',800, 14),
        (21,'EL-0354', 'مجمع العدل',             'مصعد ركاب', 'Mitsubishi',1000, 9),
    ]
    elevators = []
    for ci, code, building, etype, brand, cap, floors in elev_specs:
        cust = clients[ci]
        e = Elevator(
            organization_id=oid,
            code=code, customer_id=cust.id,
            building_name=building, city=CITY, district=cust.district,
            address=cust.address, elev_type=etype, brand=brand,
            capacity_kg=cap, floors=floors, stops=floors,
            install_date=_d(-365 * 3), status='نشط',
            last_maintenance=_d(-18), next_maintenance=_d(12),
            maint_frequency='شهري', machine_type='MR',
            notes='مصعد تجريبي — مكة المكرمة',
        )
        elevators.append(e)
    db.session.add_all(elevators)
    db.session.flush()

    def _contract(code, ci, start, end, value, status='نشط', ctype='عقد صيانة'):
        cust = clients[ci]
        tax = round(value * 0.15, 2)
        return Contract(
            organization_id=oid,
            code=code, customer_id=cust.id,
            contract_type=ctype, start_date=start, end_date=end,
            duration_months=12, maint_frequency='شهري', visits_per_month=1,
            value=value, tax_pct=15, tax_amount=tax, total=value + tax,
            payment_terms='ربع سنوي',
            invoice_status='مدفوع' if status == 'نشط' else 'غير مدفوع',
            status=status, city=CITY, district=cust.district, address=cust.address,
            lat=cust.lat, lng=cust.lng, maps_url=cust.maps_url,
        )

    contracts = [
        _contract('CN-00001', 0, _d(-300), _d(65),  48000),
        _contract('CN-00002', 1, _d(-200), _d(165), 36000),
        _contract('CN-00003', 2, _d(-400), _d(330), 72000),
        _contract('CN-00004', 3, _d(-150), _d(215), 96000),
        _contract('CN-00005', 4, _d(-100), _d(265), 54000),
        _contract('CN-00006', 0, _d(-335), _d(7),   42000),
        _contract('CN-00007', 1, _d(-358), _d(12),  38000),
        _contract('CN-00008', 2, _d(-340), _d(18),  55000),
        _contract('CN-00009', 3, _d(-345), _d(22),  88000),
        _contract('CN-00010', 4, _d(-350), _d(25),  46000),
        _contract('CN-00011', 5, _d(-360), _d(28),  32000),
        _contract('CN-00012', 6, _d(-355), _d(15),  41000),
        _contract('CN-00013', 7, _d(-348), _d(20),  67000),
        _contract('CN-00014', 8,  _d(-500), _d(-30), 28000, 'منتهي'),
        _contract('CN-00015', 9,  _d(-480), _d(-60), 35000, 'منتهي'),
        _contract('CN-00016', 5,  _d(-450), _d(-90), 22000, 'منتهي'),
        _contract('CN-00017', 6,  _d(-420), _d(-45), 31000, 'منتهي'),
        _contract('CN-00018', 7,  _d(-400), _d(-120), 44000, 'منتهي'),
        _contract('CN-00019', 8,  _d(-380), _d(-15),  26000, 'منتهي'),
        _contract('CN-00020', 10, _d(-80),  _d(285), 44000),
        _contract('CN-00021', 11, _d(-40),  _d(325), 30000),
        _contract('CN-00022', 12, _d(-120), _d(245), 78000),
        _contract('CN-00023', 13, _d(-90),  _d(275), 52000),
        _contract('CN-00024', 18, _d(-60),  _d(305), 125000),
        _contract('CN-00025', 19, _d(-200), _d(20),  24000),
        _contract('CN-00026', 21, _d(-15),  _d(350), 36000),
        _contract('CI-00001', 9,  _d(-30),  _d(335), 238280, 'نشط', 'عقد تركيب'),
    ]

    db.session.add_all(contracts)
    db.session.flush()

    latest_contract_by_client = {}
    for c in contracts:
        if (c.contract_type or '') == 'عقد تركيب':
            continue
        prev = latest_contract_by_client.get(c.customer_id)
        if not prev or c.end_date > prev.end_date:
            latest_contract_by_client[c.customer_id] = c

    for i, elev in enumerate(elevators):
        c = latest_contract_by_client.get(elev.customer_id) or contracts[i % 13]
        db.session.add(ContractElevator(
            organization_id=oid, contract_id=c.id, elevator_id=elev.id
        ))

    visits_today = [
        (0, 0, 'صيانة دورية', '08:00', 'مكتملة',         techs[0]),
        (1, 1, 'زيارة فحص',   '09:00', 'جاري التنفيذ',   techs[1]),
        (2, 2, 'زيارة طارئة',  '09:30', 'مجدولة',         techs[2]),
        (3, 3, 'صيانة دورية', '10:00', 'جاري التنفيذ',   techs[3]),
        (5, 3, 'زيارة فحص',   '10:30', 'مجدولة',         techs[7]),
        (7, 4, 'صيانة دورية', '11:00', 'مجدولة',         techs[4]),
        (8, 5, 'صيانة دورية', '11:30', 'مكتملة',         techs[0]),
        (9, 6, 'زيارة فحص',   '12:00', 'مجدولة',         techs[7]),
        (11,7, 'صيانة دورية', '13:00', 'مجدولة',         techs[1]),
        (13,9, 'صيانة دورية', '13:30', 'مكتملة',         techs[2]),
        (15,10,'زيارة متابعة','14:00', 'مجدولة',         techs[4]),
        (18,12,'صيانة دورية', '15:00', 'متأخرة',         techs[3]),
        (24,18,'زيارة فحص',   '15:30', 'مجدولة',         techs[0]),
        (25,18,'صيانة دورية', '16:00', 'مجدولة',         techs[7]),
    ]
    for i, (ei, ci, vtype, vtime, status, tech) in enumerate(visits_today):
        db.session.add(MaintenanceVisit(
            organization_id=oid,
            code=f'VI-{str(i+1).zfill(5)}',
            contract_id=contracts[ci].id if ci < len(contracts) else None,
            elevator_id=elevators[ei].id,
            technician_id=tech.id,
            visit_type=vtype, visit_date=today, visit_time=vtime,
            priority='عادية' if status != 'متأخرة' else 'عاجلة',
            status=status,
            works_done='فحص شامل وتشحيم' if status == 'مكتملة' else '',
            plan_month=today.strftime('%Y-%m'),
            route_order=i + 1,
        ))

    upcoming = [
        (16, 1, 'صيانة دورية', 1, '09:00'),
        (19, 2, 'زيارة فحص',   1, '11:00'),
        (20, 4, 'صيانة دورية', 2, '08:30'),
        (21, 5, 'صيانة دورية', 2, '10:00'),
        (22, 7, 'زيارة متابعة', 3, '09:00'),
        (23, 0, 'صيانة دورية', 3, '13:00'),
        (26, 11,'صيانة دورية', 4, '10:30'),
        (27, 21,'زيارة فحص',   5, '12:00'),
        (4,  2, 'صيانة دورية', 6, '08:00'),
        (12, 12,'زيارة طارئة', 6, '15:00'),
    ]
    for i, (ei, ti, vtype, days, vtime) in enumerate(upcoming):
        db.session.add(MaintenanceVisit(
            organization_id=oid,
            code=f'VI-U{str(i+1).zfill(3)}',
            elevator_id=elevators[ei % len(elevators)].id,
            technician_id=techs[ti % len(techs)].id,
            visit_type=vtype, visit_date=_d(days), visit_time=vtime,
            priority='عادية', status='مجدولة',
            plan_month=_d(days).strftime('%Y-%m'),
        ))

    hist_n = 0
    for m in range(1, 7):
        for d in (4, 11, 18, 25):
            hist_n += 1
            db.session.add(MaintenanceVisit(
                organization_id=oid,
                code=f'VI-H{str(hist_n).zfill(3)}',
                elevator_id=elevators[hist_n % len(elevators)].id,
                technician_id=techs[hist_n % 5].id,
                visit_type='صيانة دورية',
                visit_date=date(year - 1 if m > today.month else year, m, min(d, 28)),
                visit_time='10:00',
                status='مكتملة',
                works_done='صيانة دورية مكتملة',
            ))

    faults_data = [
        ('FA-02041', 5, techs[0], 'توقف مفاجئ',       'حرجة', 'مفتوح', True),
        ('FA-02038', 0, techs[1], 'صوت غير طبيعي',    'عالية', 'قيد المعالجة', False),
        ('FA-02035', 8, None,     'باب لا يغلق',       'عالية', 'مفتوح', True),
        ('FA-02031', 2, techs[2], 'إضاءة لوحة معطلة', 'منخفضة', 'قيد المعالجة', False),
        ('FA-02028', 9, techs[4], 'اهتزاز أثناء الحركة','متوسطة', 'قيد المعالجة', False),
        ('FA-02025', 1, techs[3], 'خلل في المستشعر',  'عالية', 'مفتوح', True),
        ('FA-02050', 6, techs[7], 'عطل فرامل',        'حرجة', 'انتظار قطع', True),
        ('FA-02051', 13,techs[1], 'كنترول لا يقلع',   'عاجلة', 'قيد المعالجة', True),
        ('FA-02052', 18,techs[0], 'باب لا يفتح',      'عالية', 'مفتوح', False),
        ('FA-02053', 24,techs[3], 'توقف بين الأدوار', 'حرجة', 'قيد المعالجة', False),
        ('FA-02054', 15,None,     'أزرار الكابينة',    'عادية', 'مفتوح', False),
        ('FA-02055', 20,techs[4], 'تسريب زيت',        'متوسطة', 'انتظار قطع', True),
    ]
    for code, ei, tech, ftype, priority, status, needs_parts in faults_data:
        db.session.add(Fault(
            organization_id=oid,
            code=code, elevator_id=elevators[ei].id,
            technician_id=tech.id if tech else None,
            fault_type=ftype, description=ftype,
            client_report=f'بلاغ العميل: {ftype}',
            reporter_name=elevators[ei].customer.contact_person if elevators[ei].customer else '',
            reporter_phone=elevators[ei].customer.phone if elevators[ei].customer else '',
            priority=priority, status=status, needs_parts=needs_parts,
            reported_at=_dt(-2 if 'مفتوح' in status else -1, 9),
        ))

    for i, (code, ei, days) in enumerate((
        ('FA-02010', 7, -30),
        ('FA-02011', 14, -12),
        ('FA-02012', 22, -8),
        ('FA-02013', 3, -45),
    )):
        db.session.add(Fault(
            organization_id=oid,
            code=code, elevator_id=elevators[ei].id,
            technician_id=techs[i % 5].id, fault_type='صيانة وقائية',
            description='عطل محلول — سجل تاريخي',
            priority='عادية', status='محلول', reported_at=_dt(days),
            resolved_at=_dt(days + 1, 14),
        ))

    inventory_data = [
        ('#001', 'حبل فولاذ 8مم',       'ميكانيكا', 25,  10, 120,  180),
        ('#002', 'لوحة تحكم Otis',      'كهرباء',    3,   5,  2800, 4200),
        ('#003', 'باب مصعد ستانلس',     'أبواب',     1,   3,  4500, 6500),
        ('#004', 'زيت تشحيم 20L',       'تشحيم',     8,   15, 350,  500),
        ('#005', 'مستشعر مستوى',        'كهرباء',    2,   8,  180,  280),
        ('#006', 'سلك طوارئ',           'كهرباء',    12,  10, 95,   150),
        ('#007', 'بكرة باب علوية',      'ميكانيكا',  0,   4,  620,  950),
        ('#008', 'فلتر هواء',           'ميكانيكا',  4,   10, 45,   75),
        ('#009', 'مفتاح أمان',          'كهرباء',    6,   12, 55,   90),
        ('#010', 'كابل طوارئ 4×16',     'كهرباء',    1,   5,  220,  340),
        ('#011', 'حذاء باب',            'أبواب',     14,  6,  85,   140),
        ('#012', 'رولمان بلي محرك',     'ميكانيكا',  5,   4,  340,  520),
        ('#013', 'إنفرتر VVVF',         'كهرباء',    2,   2,  5200, 7800),
        ('#014', 'بطارية طوارئ',        'كهرباء',    9,   6,  210,  340),
        ('#015', 'قفل باب كابينة',      'أبواب',     3,   5,  160,  250),
        ('#016', 'زيت هيدروليك 20L',    'تشحيم',     7,   8,  280,  420),
    ]
    items = []
    for code, name, cat, qty, minq, buy, sell in inventory_data:
        items.append(InventoryItem(
            organization_id=oid,
            code=code, name=name, category=cat,
            unit='قطعة', current_qty=qty, min_qty=minq,
            buy_price=buy, sell_price=sell, supplier='مورد المصاعد المتحدة',
            location='مستودع مكة — العزيزية',
        ))
    db.session.add_all(items)
    db.session.flush()

    movements = [
        ('MV-001', 0, -10, 'وارد', 'شراء', 30, 120),
        ('MV-002', 6, -3,  'صادر', 'استخدام في صيانة', 2, 620),
        ('MV-003', 4, -6,  'وارد', 'شراء', 10, 180),
        ('MV-004', 1, -2,  'صادر', 'تركيب لدى عميل', 1, 2800),
        ('MV-005', 11,-8,  'وارد', 'شراء', 20, 85),
        ('MV-006', 7, -1,  'صادر', 'استخدام في صيانة', 3, 45),
        ('MV-007', 13,-4,  'وارد', 'شراء', 12, 210),
        ('MV-008', 14,-1,  'صادر', 'استخدام في صيانة', 2, 160),
    ]
    for code, ii, days, direction, mtype, qty, price in movements:
        db.session.add(StockMovement(
            organization_id=oid,
            code=code, item_id=items[ii].id,
            movement_date=_d(days), direction=direction,
            movement_type=mtype, quantity=qty, unit_price=price,
            total_value=qty * price,
            technician_id=techs[0].id if direction == 'صادر' else None,
            elevator_id=elevators[3].id if direction == 'صادر' else None,
        ))

    invoices_plan = [
        ('INV-0001', 0, 28500, 'مدفوعة',     _d(-60), _d(-30)),
        ('INV-0002', 1, 22000, 'مدفوعة',     _d(-45), _d(-15)),
        ('INV-0003', 2, 35000, 'مدفوعة',     _d(-30), _d(-5)),
        ('INV-0004', 3, 42000, 'مدفوعة',     _d(-20), _d(10)),
        ('INV-0005', 4, 18500, 'غير مدفوعة',  _d(-40), _d(-10)),
        ('INV-0006', 5, 12000, 'غير مدفوعة',  _d(-25), _d(-5)),
        ('INV-0007', 6,  8500, 'غير مدفوعة',  _d(-15), _d(5)),
        ('INV-0008', 7,  6200, 'غير مدفوعة',  _d(-50), _d(-20)),
        ('INV-0009', 8,  4800, 'غير مدفوعة',  _d(-35), _d(-8)),
        ('INV-0010', 9,  5500, 'مدفوع جزئياً',_d(-10), _d(20)),
        ('INV-0011', 10, 11000,'مدفوعة',     _d(-18), _d(5)),
        ('INV-0012', 12, 19500,'غير مدفوعة',  _d(-8),  _d(12)),
        ('INV-0013', 18, 31000,'مدفوعة',     _d(-12), _d(18)),
        ('INV-0014', 13,  8700,'مدفوع جزئياً',_d(-6),  _d(24)),
        ('INV-0015', 21,  6400,'غير مدفوعة',  _d(-3),  _d(27)),
        ('INV-0016', 19,  4200,'مدفوعة',     _d(-22), _d(-2)),
    ]
    for code, ci, amount, status, inv_date, due_date in invoices_plan:
        tax = round(amount * 0.15, 2)
        cust = clients[ci]
        contract = latest_contract_by_client.get(cust.id)
        db.session.add(Invoice(
            organization_id=oid,
            code=code, invoice_type='فاتورة',
            customer_id=cust.id,
            contract_id=contract.id if contract else None,
            invoice_date=inv_date, due_date=due_date,
            description='فاتورة صيانة دورية — مكة المكرمة',
            amount=amount, tax_amount=tax, total=amount + tax,
            paid_amount=amount + tax if status == 'مدفوعة' else (amount * 0.4 if 'جزئي' in status else 0),
            payment_method='تحويل', status=status,
        ))

    monthly_amounts = [8500, 9200, 11000, 9800, 12500, 14200,
                       10800, 13500, 11900, 15200, 13800, 16100]
    for m, amt in enumerate(monthly_amounts, 1):
        tax = round(amt * 0.15, 2)
        cust = clients[m % len(clients)]
        contract = latest_contract_by_client.get(cust.id)
        db.session.add(Revenue(
            organization_id=oid,
            code=f'REV-{str(m).zfill(3)}',
            customer_id=cust.id,
            contract_id=contract.id if contract else None,
            revenue_date=date(year, m, 15) if m <= 12 else today,
            revenue_type='عقد صيانة',
            payment_method='تحويل',
            amount=amt, tax_amount=tax, total=amt + tax,
            status='محصّل',
            title=f'تحصيل صيانة — {cust.name}',
        ))

    expense_amounts = [3200, 4100, 3800, 4500, 5200, 4800,
                       3900, 5500, 4700, 5100, 4300, 4900]
    types = ('قطع غيار', 'رواتب', 'محروقات', 'إيجار مستودع')
    for m, amt in enumerate(expense_amounts, 1):
        db.session.add(Expense(
            organization_id=oid,
            code=f'EXP-{str(m).zfill(3)}',
            expense_date=date(year, m, 20) if m <= 12 else today,
            expense_type=types[m % len(types)],
            description='مصروف تشغيلي شهري — فرع مكة',
            responsible='الإدارة المالية',
            payment_method='تحويل',
            amount=amt,
        ))

    parts_data = [
        (0, 0, 1200, 2100, 'محصل'),
        (1, 2, 2800, 4200, 'محصل'),
        (2, 5,  450,  750, 'غير محصل'),
        (3, 6, 1800, 2900, 'محصل'),
        (4, 1,  620,  950, 'غير محصل'),
        (9, 13, 950, 1600, 'محصل'),
        (12,18, 2100, 3400,'غير محصل'),
        (18,24, 780, 1250, 'محصل'),
    ]
    for i, (ci, ei, cost, sell, st) in enumerate(parts_data):
        cust = clients[ci]
        contract = latest_contract_by_client.get(cust.id)
        db.session.add(PartsBilling(
            organization_id=oid,
            code=f'PB-{str(i+1).zfill(3)}',
            customer_id=cust.id,
            contract_id=contract.id if contract else None,
            elevator_id=elevators[ei].id,
            technician_id=techs[i % 5].id,
            billing_date=_d(-i * 4),
            description='تركيب قطع غيار في موقع مكة',
            cost_price=cost, sell_price=sell, profit=sell - cost,
            payment_method='تحويل', status=st,
        ))

    _ensure_admin_user()
    _ensure_jama_settings()

    db.session.commit()
    _seed_demo_extras()
    db.session.commit()

    from app import get_dashboard_stats
    stats, alerts = get_dashboard_stats()
    print("Seed data inserted successfully.")
    print(f"  Org:                {getattr(g.organization, 'slug', oid)}")
    print(f"  Clients:            {stats['customers']}")
    print(f"  Elevators:          {stats['elevators']}")
    print(f"  Active contracts:   {stats['contracts']}")
    print(f"  Expiring (30 days): {alerts['expiring_contracts_count']}")
    print(f"  Expired contracts:  {stats['expired_contracts']}")
    print(f"  Today visits:       {stats['visits_today']}")
    print(f"  Open faults:        {stats['faults_open']}")
    print(f"  Low stock items:    {alerts['low_stock_count']}")
    print(f"  Unpaid invoices:    {stats['unpaid_invoices']}")
    print(f"  Technicians:        {stats['technicians']}")
    return True


def reset_jama_demo() -> bool:
    """مسح بيانات المؤسسة التجريبية وتحميل سيناريو مكة الكامل."""
    with app.app_context():
        db.create_all()
        _bind_demo_org()
        print('[1/4] مسح البيانات التشغيلية...')
        clear_business_data()
        print('[2/4] تحميل عملاء مكة + عقود + زيارات + أعطال + مالية + مخزن...')
        if not seed_all(force=True):
            return False
        print('[3/4] إضافة طلبات شراء + تقديرات + تركيب + فريق فني + محاضر...')
        print('[4/4] تم')
        _print_jama_credentials()
        return True


def _print_jama_credentials() -> None:
    from app import get_dashboard_stats

    stats, alerts = get_dashboard_stats()
    print('')
    print('=== بيئة جما التجريبية جاهزة ===')
    print('  المكتب:  admin / admin123')
    print('  الفني:   Tech-001 أو 0552001001 / 123456')
    print('  الخريطة: كل المواقع داخل مكة المكرمة')
    print('  السيناريو: docs/SCENARIO_10_CLIENTS.md')
    print('')
    print(f"  عملاء: {stats['customers']} | مصاعد: {stats['elevators']} | عقود: {stats['contracts']}")
    print(f"  زيارات اليوم: {stats['visits_today']} | أعطال مفتوحة: {stats['faults_open']}")
    print(f"  فواتير غير مدفوعة: {stats['unpaid_invoices']} | مخزون منخفض: {alerts['low_stock_count']}")


if __name__ == '__main__':
    reset = '--reset' in sys.argv or '--jama' in sys.argv
    with app.app_context():
        db.create_all()
        if reset:
            if '--jama' in sys.argv:
                reset_jama_demo()
            else:
                print('Clearing business data...')
                _bind_demo_org()
                clear_business_data()
                seed_all(force=True)
        else:
            seed_all()
