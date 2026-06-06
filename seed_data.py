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

import sys
from datetime import date, datetime, timedelta

from app import app, db
from models import (
    Customer, Elevator, Contract, ContractElevator, Technician,
    MaintenanceVisit, Fault, Revenue, Expense, Invoice,
    InventoryItem, StockMovement, PartsBilling, User, Settings,
)


def _d(days_offset=0):
    return date.today() + timedelta(days=days_offset)


def _dt(days_offset=0, hour=10, minute=0):
    return datetime.combine(_d(days_offset), datetime.min.time().replace(hour=hour, minute=minute))


def clear_business_data():
    """مسح البيانات التشغيلية مع الإبقاء على المستخدمين والإعدادات."""
    for model in (
        StockMovement, PartsBilling, Fault, MaintenanceVisit,
        ContractElevator, Invoice, Revenue, Expense, Contract,
        Elevator, Technician, InventoryItem, Customer,
    ):
        model.query.delete()
    db.session.commit()


def seed_all():
  with app.app_context():
    db.create_all()

    if Customer.query.count() > 0:
        print("[!] Database already has data. Use --reset to reseed.")
        return False

    today = date.today()
    year = today.year

    # ── العملاء ──────────────────────────────────────────────
    clients_data = [
        dict(code='C-0001', name='برج الياسمين',      city='مكة', district='العزيزية',        address='شارع الأمير سلطان، برج الياسمين، الطابق 1', phone='0501111001', status='نشط', lat='21.4012', lng='39.8541'),
        dict(code='C-0002', name='مجمع النخيل',        city='مكة', district='طريق مكة المدينة', address='طريق مكة المدينة، بجوار محطة الوقود',           phone='0501111002', status='نشط', lat='21.4268', lng='39.7935'),
        dict(code='C-0003', name='فندق الأندلس',       city='مكة', district='العبدية',         address='حي العبدية، شارع إبراهيم الخليل',                phone='0501111003', status='نشط', lat='21.3889', lng='39.8217'),
        dict(code='C-0004', name='مستشفى السلام',      city='مكة', district='النزهة',          address='شارع النزهة، مستشفى السلام الطبي',               phone='0501111004', status='نشط', lat='21.4156', lng='39.8672'),
        dict(code='C-0005', name='برج المملكة',        city='مكة', district='الروضة',          address='حي الروضة، برج المملكة التجاري',                 phone='0501111005', status='نشط', lat='21.3925', lng='39.8843'),
        dict(code='C-0006', name='مجمع التجارة',       city='مكة', district='أجياد',           address='أجياد، مجمع التجارة، المدخل الشرقي',            phone='0501111006', status='نشط', lat='21.4188', lng='39.8124'),
        dict(code='C-0007', name='مركز الملك عبدالله', city='مكة', district='الشوقية',         address='حي الشوقية، مركز الملك عبدالله الطبي',           phone='0501111007', status='نشط', lat='21.3791', lng='39.8419'),
        dict(code='C-0008', name='برج الفيصلية',       city='مكة', district='الزاهر',           address='حي الزاهر، برج الفيصلية، البوابة الرئيسية',     phone='0501111008', status='نشط', lat='21.4312', lng='39.8368'),
        dict(code='C-0009', name='مجمع الروضة',         city='مكة', district='الروضة',          address='حي الروضة، مجمع الروضة السكني',                  phone='0501111009', status='نشط', lat='21.3974', lng='39.8725'),
        dict(code='C-0010', name='فندق مكة كلوك',       city='مكة', district='المسفلة',         address='حي المسفلة، فندق مكة كلوك تاور',                 phone='0501111010', status='نشط', lat='21.4103', lng='39.7988'),
    ]
    clients = [Customer(**c) for c in clients_data]
    db.session.add_all(clients)
    db.session.flush()

    # ── الفنيون ──────────────────────────────────────────────
    techs_data = [
        dict(code='Tech-001', name='أحمد الزهراني',  phone='0552001001', job_title='فني أول',   specialization='مصاعد ركاب', city='مكة', status='متاح', emergency=True),
        dict(code='Tech-002', name='خالد العمري',    phone='0552001002', job_title='فني أول',   specialization='كهرباء',      city='مكة', status='متاح', emergency=True),
        dict(code='Tech-003', name='سعد القحطاني',   phone='0552001003', job_title='فني ثانٍ', specialization='ميكانيكا',    city='مكة', status='متاح'),
        dict(code='Tech-004', name='فهد المالكي',    phone='0552001004', job_title='فني أول',   specialization='مصاعد ركاب', city='مكة', status='مشغول'),
        dict(code='Tech-005', name='عمر الدوسري',    phone='0552001005', job_title='فني ثانٍ', specialization='ميكانيكا',    city='مكة', status='متاح'),
        dict(code='Tech-006', name='محمد الشهري',    phone='0552001006', job_title='مشرف',     specialization='مصاعد ركاب', city='مكة', status='إجازة'),
        dict(code='Tech-007', name='يوسف الغامدي',   phone='0552001007', job_title='فني أول',   specialization='كهرباء',      city='مكة', status='غير نشط'),
    ]
    techs = [Technician(**t) for t in techs_data]
    db.session.add_all(techs)
    db.session.flush()

    # ── المصاعد ──────────────────────────────────────────────
    elev_specs = [
        (0, 'EL-0124', 'برج الياسمين الرئيسي',  'مصعد ركاب', 'Otis',    1000, 15),
        (0, 'EL-0125', 'برج الياسمين الخدمي',   'مصعد بضائع','Schindler',2000, 8),
        (1, 'EL-0087', 'مجمع النخيل A',         'مصعد ركاب', 'Kone',    800,  10),
        (1, 'EL-0088', 'مجمع النخيل B',         'مصعد ركاب', 'Otis',    800,  10),
        (2, 'EL-0201', 'فندق الأندلس',          'مصعد ركاب', 'Mitsubishi',630, 12),
        (3, 'EL-0033', 'مستشفى السلام',         'مصعد مستشفى','Otis',   1600, 8),
        (4, 'EL-0156', 'برج المملكة',           'مصعد ركاب', 'Kone',    1000, 20),
        (5, 'EL-0091', 'مجمع التجارة',          'مصعد ركاب', 'Schindler',1000, 6),
        (6, 'EL-0044', 'مركز الملك عبدالله',    'مصعد ركاب', 'Otis',    630,  7),
        (7, 'EL-0178', 'برج الفيصلية',          'مصعد ركاب', 'Kone',    1000, 18),
        (8, 'EL-0220', 'مجمع الروضة',           'مصعد ركاب', 'Otis',    800,  9),
        (9, 'EL-0305', 'فندق مكة كلوك',         'مصعد ركاب', 'Mitsubishi',1000,14),
    ]
    elevators = []
    for ci, code, building, etype, brand, cap, floors in elev_specs:
        e = Elevator(
            code=code, customer_id=clients[ci].id,
            building_name=building, city='مكة', district=clients[ci].district,
            elev_type=etype, brand=brand, capacity_kg=cap, floors=floors,
            install_date=_d(-365 * 3), status='نشط',
        )
        elevators.append(e)
    db.session.add_all(elevators)
    db.session.flush()

    # ── العقود ──────────────────────────────────────────────
    def _contract(code, ci, start, end, value, status='نشط'):
        tax = round(value * 0.15, 2)
        return Contract(
            code=code, customer_id=clients[ci].id,
            contract_type='عقد صيانة', start_date=start, end_date=end,
            maint_frequency='شهري', visits_per_month=1,
            value=value, tax_pct=15, tax_amount=tax, total=value + tax,
            payment_terms='ربع سنوي', invoice_status='مدفوع' if status == 'نشط' else 'غير مدفوع',
            status=status,
        )

    contracts = [
        # عقود نشطة طويلة الأمد
        _contract('CN-00001', 0, _d(-300), _d(65),  48000),
        _contract('CN-00002', 1, _d(-200), _d(165), 36000),
        _contract('CN-00003', 2, _d(-400), _d(330), 72000),
        _contract('CN-00004', 3, _d(-150), _d(215), 96000),
        _contract('CN-00005', 4, _d(-100), _d(265), 54000),
        # عقود تنتهي خلال 30 يوم (تنبيه)
        _contract('CN-00006', 0, _d(-335), _d(7),   42000),
        _contract('CN-00007', 1, _d(-358), _d(12),  38000),
        _contract('CN-00008', 2, _d(-340), _d(18),  55000),
        _contract('CN-00009', 3, _d(-345), _d(22),  88000),
        _contract('CN-00010', 4, _d(-350), _d(25),  46000),
        _contract('CN-00011', 5, _d(-360), _d(28),  32000),
        _contract('CN-00012', 6, _d(-355), _d(15),  41000),
        _contract('CN-00013', 7, _d(-348), _d(20),  67000),
        # عقود منتهية
        _contract('CN-00014', 8,  _d(-500), _d(-30), 28000, 'منتهي'),
        _contract('CN-00015', 9,  _d(-480), _d(-60), 35000, 'منتهي'),
        _contract('CN-00016', 5,  _d(-450), _d(-90), 22000, 'منتهي'),
        _contract('CN-00017', 6,  _d(-420), _d(-45), 31000, 'منتهي'),
        _contract('CN-00018', 7,  _d(-400), _d(-120), 44000, 'منتهي'),
        _contract('CN-00019', 8,  _d(-380), _d(-15),  26000, 'منتهي'),
    ]

    db.session.add_all(contracts)
    db.session.flush()

    # أحدث عقد لكل عميل (لربط المدفوعات)
    latest_contract_by_client = {}
    for c in contracts:
        prev = latest_contract_by_client.get(c.customer_id)
        if not prev or c.end_date > prev.end_date:
            latest_contract_by_client[c.customer_id] = c

    # ربط العقود بالمصاعد
    for i, c in enumerate(contracts[:13]):
        db.session.add(ContractElevator(contract_id=c.id, elevator_id=elevators[i % len(elevators)].id))

    # ── زيارات اليوم (9 زيارات) ──────────────────────────────
    visits_today = [
        (0, 0, 'صيانة دورية', '08:00', 'مكتملة',   techs[0]),
        (1, 1, 'فحص دوري',    '09:30', 'جارٍ',     techs[1]),
        (2, 2, 'صيانة طارئة', '10:00', 'مجدولة',   techs[2]),
        (3, 3, 'فحص أمان',    '11:00', 'جارٍ',     techs[3]),
        (4, 4, 'صيانة دورية', '12:30', 'مجدولة',   techs[4]),
        (5, 5, 'فحص دوري',    '13:00', 'مكتملة',   techs[0]),
        (6, 6, 'صيانة دورية', '14:00', 'مجدولة',   techs[5]),
        (7, 7, 'فحص أمان',    '15:30', 'مجدولة',   techs[6]),
        (8, 8, 'صيانة دورية', '16:00', 'مكتملة',   techs[1]),
    ]
    for i, (ei, ci, vtype, vtime, status, tech) in enumerate(visits_today):
        db.session.add(MaintenanceVisit(
            code=f'VI-{str(i+1).zfill(5)}',
            contract_id=contracts[ci].id if ci < len(contracts) else None,
            elevator_id=elevators[ei].id,
            technician_id=tech.id,
            visit_type=vtype, visit_date=today, visit_time=vtime,
            priority='عادية', status=status,
            works_done='فحص شامل' if status == 'مكتملة' else '',
        ))

    # زيارات سابقة مكتملة (للإحصائيات — العام الماضي لتجنب تداخلها مع زيارات اليوم)
    for m in range(1, 7):
        for d in (5, 15):
            db.session.add(MaintenanceVisit(
                code=f'VI-P{m}{d}',
                elevator_id=elevators[m % len(elevators)].id,
                technician_id=techs[m % len(techs)].id,
                visit_type='صيانة دورية',
                visit_date=date(year - 1, m, min(d, 28)),
                status='مكتملة',
            ))

    # ── الأعطال المفتوحة ──────────────────────────────────────
    faults_data = [
        ('FA-02041', 3, techs[0], 'توقف مفاجئ',       'حرجة', 'مفتوح'),
        ('FA-02038', 0, techs[1], 'صوت غير طبيعي',    'عالية', 'قيد المعالجة'),
        ('FA-02035', 5, None,     'باب لا يغلق',       'عالية', 'مفتوح'),
        ('FA-02031', 2, techs[2], 'إضاءة لوحة معطلة', 'منخفضة', 'قيد المعالجة'),
        ('FA-02028', 6, techs[4], 'اهتزاز أثناء الحركة','متوسطة', 'قيد المعالجة'),
        ('FA-02025', 1, techs[3], 'خلل في المستشعر',  'عالية', 'مفتوح'),
    ]
    for code, ei, tech, ftype, priority, status in faults_data:
        db.session.add(Fault(
            code=code, elevator_id=elevators[ei].id,
            technician_id=tech.id if tech else None,
            fault_type=ftype, description=ftype,
            priority=priority, status=status,
            reported_at=_dt(-2, 9),
        ))

    # أعطال محلولة (سجل تاريخي)
    db.session.add(Fault(
        code='FA-02010', elevator_id=elevators[4].id,
        technician_id=techs[0].id, fault_type='صيانة وقائية',
        priority='عادية', status='محلول', reported_at=_dt(-30),
    ))

    # ── المخزون ──────────────────────────────────────────────
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
    ]
    items = []
    for code, name, cat, qty, minq, buy, sell in inventory_data:
        item = InventoryItem(
            code=code, name=name, category=cat,
            unit='قطعة', current_qty=qty, min_qty=minq,
            buy_price=buy, sell_price=sell, supplier='مورد المصاعد المتحدة',
        )
        items.append(item)
    db.session.add_all(items)
    db.session.flush()

    # حركات مخزن
    db.session.add(StockMovement(
        code='MV-001', item_id=items[0].id,
        movement_date=_d(-10), direction='وارد',
        movement_type='شراء', quantity=30, unit_price=120, total_value=3600,
    ))
    db.session.add(StockMovement(
        code='MV-002', item_id=items[6].id,
        movement_date=_d(-3), direction='صادر',
        movement_type='استخدام في صيانة', quantity=2, unit_price=620, total_value=1240,
        technician_id=techs[0].id, elevator_id=elevators[3].id,
    ))

    # ── الفواتير (ملخص مالي) ──────────────────────────────────
    invoices_plan = [
        ('INV-0001', 0, 28500, 'مدفوعة',    _d(-60), _d(-30)),
        ('INV-0002', 1, 22000, 'مدفوعة',    _d(-45), _d(-15)),
        ('INV-0003', 2, 35000, 'مدفوعة',    _d(-30), _d(-5)),
        ('INV-0004', 3, 42000, 'مدفوعة',    _d(-20), _d(10)),
        ('INV-0005', 4, 18500, 'غير مدفوعة', _d(-40), _d(-10)),  # متأخرة
        ('INV-0006', 5, 12000, 'غير مدفوعة', _d(-25), _d(-5)),   # متأخرة
        ('INV-0007', 6,  8500, 'غير مدفوعة', _d(-15), _d(5)),
        ('INV-0008', 7,  6200, 'غير مدفوعة', _d(-50), _d(-20)),  # متأخرة
        ('INV-0009', 8,  4800, 'غير مدفوعة', _d(-35), _d(-8)),   # متأخرة
        ('INV-00010',9,  5500, 'مدفوع جزئياً',_d(-10), _d(20)),
    ]
    for code, ci, amount, status, inv_date, due_date in invoices_plan:
        tax = round(amount * 0.15, 2)
        db.session.add(Invoice(
            code=code, invoice_type='فاتورة',
            customer_id=clients[ci].id,
            contract_id=latest_contract_by_client[clients[ci].id].id,
            invoice_date=inv_date, due_date=due_date,
            description='فاتورة صيانة دورية',
            amount=amount, tax_amount=tax, total=amount + tax,
            payment_method='تحويل', status=status,
        ))

    # ── الإيرادات الشهرية (للرسوم البيانية) ──────────────────
    monthly_amounts = [8500, 9200, 11000, 9800, 12500, 14200,
                       10800, 13500, 11900, 15200, 13800, 16100]
    for m, amt in enumerate(monthly_amounts, 1):
        tax = round(amt * 0.15, 2)
        cust = clients[m % len(clients)]
        db.session.add(Revenue(
            code=f'REV-{str(m).zfill(3)}',
            customer_id=cust.id,
            contract_id=latest_contract_by_client[cust.id].id,
            revenue_date=date(year, m, 15),
            revenue_type='عقد صيانة',
            payment_method='تحويل',
            amount=amt, tax_amount=tax, total=amt + tax,
            status='محصّل',
        ))

    # ── المصروفات الشهرية (للرسوم البيانية) ──────────────────
    expense_amounts = [3200, 4100, 3800, 4500, 5200, 4800,
                       3900, 5500, 4700, 5100, 4300, 4900]
    for m, amt in enumerate(expense_amounts, 1):
        db.session.add(Expense(
            code=f'EXP-{str(m).zfill(3)}',
            expense_date=date(year, m, 20),
            expense_type='قطع غيار' if m % 2 else 'رواتب',
            description='مصروف تشغيلي شهري',
            responsible='الإدارة المالية',
            payment_method='تحويل',
            amount=amt,
        ))

    # ── بيان قطع الغيار ──────────────────────────────────────
    parts_data = [
        (0, 0, 1200, 2100),
        (1, 2, 2800, 4200),
        (2, 5,  450,  750),
        (3, 3, 1800, 2900),
        (4, 1,  620,  950),
    ]
    for ci, ei, cost, sell in parts_data:
        db.session.add(PartsBilling(
            code=f'PB-{str(ci+1).zfill(3)}',
            customer_id=clients[ci].id,
            contract_id=latest_contract_by_client[clients[ci].id].id,
            elevator_id=elevators[ei].id,
            technician_id=techs[ci % len(techs)].id,
            billing_date=_d(-ci * 7),
            description='تركيب قطع غيار',
            cost_price=cost, sell_price=sell, profit=sell - cost,
            payment_method='تحويل', status='مكتملة',
        ))

    # ── مستخدم admin + إعدادات (إن لم يوجدا) ────────────────
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(
            username='admin', password_hash='admin123',
            full_name='محمد القواشي', email='admin@liftcore.sa',
            role='admin', is_active=True,
        ))

    if not Settings.query.first():
        db.session.add(Settings(
            company_name='شركة جما تقنية للمصاعد',
            company_name_en='Jama Elevator Technology Co.',
            phone='0500000000', email='info@liftcore.sa',
            city='مكة المكرمة', tax_pct=15, currency='ر.س', language='ar',
        ))

    db.session.commit()

    # ملخص
    from app import get_dashboard_stats
    stats, alerts = get_dashboard_stats()
    print("Seed data inserted successfully.")
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


if __name__ == '__main__':
    reset = '--reset' in sys.argv
    with app.app_context():
        db.create_all()
        if reset:
            print("Clearing business data...")
            clear_business_data()
            seed_all()
        else:
            seed_all()
