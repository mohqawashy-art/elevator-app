"""بيانات تجريبية شاملة لمستأجر demo — معزولة بـ organization_id (لا تمس jama)."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from models import (
    Contract,
    Customer,
    Elevator,
    ElevatorEstimate,
    ElevatorEstimateLine,
    Expense,
    Fault,
    InventoryItem,
    Invoice,
    MaintenanceVisit,
    Organization,
    PartsBilling,
    PurchaseOrder,
    PurchaseOrderLine,
    Revenue,
    StockMovement,
    Technician,
    db,
)

DEMO_OPS_MARKER = 'بيانات تجريبية — مكة'
ALLOWED_SEED_SLUGS = frozenset({'demo'})

INVENTORY_ROWS = [
    ('DEM-001', 'حبل فولاذ 8مم', 'ميكانيكا', 'قطعة', 25, 10, 120, 180),
    ('DEM-002', 'لوحة تحكم Otis', 'كهرباء', 'قطعة', 3, 5, 2800, 4200),
    ('DEM-003', 'باب مصعد ستانلس', 'أبواب', 'قطعة', 1, 3, 4500, 6500),
    ('DEM-004', 'زيت تشحيم 20L', 'تشحيم', 'عبوة', 8, 15, 350, 500),
    ('DEM-005', 'مستشعر مستوى', 'كهرباء', 'قطعة', 2, 8, 180, 280),
    ('DEM-006', 'سلك طوارئ', 'كهرباء', 'قطعة', 12, 10, 95, 150),
    ('DEM-007', 'بكرة باب علوية', 'ميكانيكا', 'قطعة', 0, 4, 620, 950),
    ('DEM-008', 'فلتر هواء', 'ميكانيكا', 'قطعة', 4, 10, 45, 75),
    ('DEM-009', 'مفتاح أمان', 'كهرباء', 'قطعة', 6, 12, 55, 90),
    ('DEM-010', 'كابل طوارئ 4×16', 'كهرباء', 'قطعة', 1, 5, 220, 340),
]

TECHNICIANS = [
    ('Tech-D01', 'أحمد الزهراني', '0552001001', 'فني أول', 'مصاعد ركاب', 'متاح', 'صيانة'),
    ('Tech-D02', 'خالد العمري', '0552001002', 'فني أول', 'كهرباء', 'متاح', 'أعطال'),
    ('Tech-D03', 'سعد القحطاني', '0552001003', 'فني ثانٍ', 'ميكانيكا', 'متاح', 'صيانة'),
    ('Tech-D04', 'فهد المالكي', '0552001004', 'فني أول', 'مصاعد ركاب', 'مشغول', 'أعطال'),
    ('Tech-D05', 'عمر الدوسري', '0552001005', 'فني ثانٍ', 'ميكانيكا', 'متاح', 'صيانة'),
    ('Tech-D06', 'محمد الشهري', '0552001006', 'مشرف', 'مصاعد ركاب', 'إجازة', 'صيانة'),
]


def assert_safe_demo_slug(slug: str) -> None:
    s = (slug or '').strip().lower()
    if s not in ALLOWED_SEED_SLUGS:
        raise ValueError(
            f'slug={s!r} غير مسموح — استخدم demo فقط حتى لا تمس jama.'
        )


def assert_demo_isolated_from_jama(org: Organization) -> None:
    jama = Organization.query.filter_by(slug='jama').first()
    if jama and jama.id == org.id:
        raise RuntimeError('demo و jama يتشاركان organization_id — أوقف التنفيذ')


def bind_tenant(slug: str) -> Organization:
    from flask import g

    assert_safe_demo_slug(slug)
    org = Organization.query.filter_by(slug=slug.strip().lower()).first()
    if not org:
        raise RuntimeError(f'لا توجد مؤسسة slug={slug!r}')
    assert_demo_isolated_from_jama(org)
    g.organization = org
    g.organization_id = org.id
    return org


def _d(days_offset: int = 0) -> date:
    return date.today() + timedelta(days=days_offset)


def _dt(days_offset: int = 0, hour: int = 10, minute: int = 0) -> datetime:
    return datetime.combine(
        _d(days_offset),
        datetime.min.time().replace(hour=hour, minute=minute),
    )


def _latest_contract_by_customer(contracts: list[Contract]) -> dict[int, Contract]:
    out: dict[int, Contract] = {}
    for c in contracts:
        prev = out.get(c.customer_id)
        if not prev or c.end_date > prev.end_date:
            out[c.customer_id] = c
    return out


def import_makkah_base_pack(
    org: Organization,
    data_dir: str,
    *,
    dry_run: bool = False,
) -> dict:
    """استيراد 01–03 من demo_makkah + المخزن — tenant demo فقط."""
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parent / 'scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))

    from import_jama_tenant_bundle import (
        import_contracts,
        import_customers,
        import_elevators,
    )

    base = Path(data_dir)
    files = {
        'clients': base / '01-clients.xlsx',
        'elevators': base / '02-elevators.xlsx',
        'contracts': base / '03-contracts.xlsx',
    }
    for label, path in files.items():
        if not path.is_file():
            raise FileNotFoundError(f'{label} missing: {path}')

    bind_tenant(org.slug)
    stats = {
        'customers': import_customers(str(files['clients']), dry_run=dry_run),
        'elevators': import_elevators(str(files['elevators']), dry_run=dry_run),
        'contracts': import_contracts(str(files['contracts']), dry_run=dry_run),
        'inventory': seed_inventory_if_empty(org.id, dry_run=dry_run),
    }
    return stats


def seed_inventory_if_empty(
    organization_id: int,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    oid = int(organization_id)
    existing = (
        InventoryItem.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .count()
    )
    if existing >= len(INVENTORY_ROWS):
        return {'existing': existing, 'added': 0}

    added = 0
    known = {
        (i.code or '').upper()
        for i in InventoryItem.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .all()
        if i.code
    }
    for code, name, cat, unit, qty, minq, buy, sell in INVENTORY_ROWS:
        if code.upper() in known:
            continue
        if dry_run:
            added += 1
            continue
        db.session.add(InventoryItem(
            organization_id=oid,
            code=code,
            name=name,
            category=cat,
            unit=unit,
            current_qty=qty,
            min_qty=minq,
            buy_price=buy,
            sell_price=sell,
            storage_location='مستودع مكة — العزيزية',
            supplier='مورد المصاعد المتحدة',
            notes=DEMO_OPS_MARKER,
        ))
        added += 1
    if not dry_run and added:
        db.session.flush()
    return {'existing': existing, 'added': added}


def seed_full_demo_operations(
    organization_id: int,
    *,
    password_hasher=None,
    dry_run: bool = False,
) -> dict:
    """طبقة تشغيلية: فنيون، زيارات، أعطال، مالية، مخزن — idempotent."""
    oid = int(organization_id)
    today = date.today()
    year = today.year
    stats: dict[str, int | str] = {}

    customers = (
        Customer.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .order_by(Customer.id)
        .all()
    )
    elevators = (
        Elevator.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .order_by(Elevator.id)
        .all()
    )
    contracts = (
        Contract.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .order_by(Contract.id)
        .all()
    )
    active_contracts = [c for c in contracts if (c.status or '') != 'منتهي']

    if len(customers) < 2 or len(elevators) < 2:
        stats['skipped'] = 'need customers and elevators first'
        return stats

    latest_by_client = _latest_contract_by_customer(contracts)

    # ── فنيون ──
    tech_added = 0
    for code, name, phone, title, spec, status, team in TECHNICIANS:
        exists = (
            Technician.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid, code=code)
            .first()
        )
        if exists:
            continue
        if dry_run:
            tech_added += 1
            continue
        db.session.add(Technician(
            organization_id=oid,
            code=code,
            name=name,
            phone=phone,
            job_title=title,
            specialization=spec,
            city='مكة المكرمة',
            status=status,
            team=team,
            notes=DEMO_OPS_MARKER,
        ))
        tech_added += 1
    stats['technicians_added'] = tech_added

    if not dry_run and tech_added:
        db.session.flush()

    techs = (
        Technician.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .order_by(Technician.id)
        .all()
    )
    active_techs = [t for t in techs if (t.status or '') in ('متاح', 'مشغول', 'نشط')]

    # PIN ميداني للعرض
    if password_hasher and active_techs and not dry_run:
        demo_pin = password_hasher('123456')
        demo_ids = ('1012345678', '1023456789', '1034567890', '1045678901')
        for idx, tech in enumerate(active_techs[:4]):
            if not tech.sign_pin_hash:
                tech.sign_pin_hash = demo_pin
            if not tech.national_id and idx < len(demo_ids):
                tech.national_id = demo_ids[idx]
        stats['field_pin'] = '123456'

    inv_stats = seed_inventory_if_empty(oid, dry_run=dry_run)
    stats['inventory_added'] = inv_stats.get('added', 0)
    items = (
        InventoryItem.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .order_by(InventoryItem.id)
        .all()
    )

    # ── زيارات اليوم ──
    today_visits = (
        MaintenanceVisit.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid, visit_date=today)
        .count()
    )
    visit_added = 0
    if today_visits < 6 and active_techs:
        slots = [
            ('صيانة دورية', '08:00', 'مكتملة'),
            ('فحص دوري', '09:30', 'جارٍ'),
            ('صيانة طارئة', '10:00', 'مجدولة'),
            ('فحص أمان', '11:00', 'جارٍ'),
            ('صيانة دورية', '13:00', 'مكتملة'),
            ('فحص دوري', '15:30', 'مجدولة'),
            ('صيانة دورية', '16:00', 'مكتملة'),
        ]
        for i, (vtype, vtime, status) in enumerate(slots):
            code = f'VI-D{str(i + 1).zfill(4)}'
            exists = (
                MaintenanceVisit.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid, code=code)
                .first()
            )
            if exists:
                continue
            ei = i % len(elevators)
            ci = min(i, len(active_contracts) - 1) if active_contracts else 0
            contract = active_contracts[ci] if active_contracts else None
            tech = active_techs[i % len(active_techs)]
            if dry_run:
                visit_added += 1
                continue
            db.session.add(MaintenanceVisit(
                organization_id=oid,
                code=code,
                contract_id=contract.id if contract else None,
                elevator_id=elevators[ei].id,
                technician_id=tech.id,
                visit_type=vtype,
                visit_date=today,
                visit_time=vtime,
                priority='عادية',
                status=status,
                works_done='فحص شامل — تجريبي' if status == 'مكتملة' else '',
                notes=DEMO_OPS_MARKER,
            ))
            visit_added += 1
    stats['visits_today_added'] = visit_added

    # زيارات تاريخية (6 أشهر)
    hist_added = 0
    if (
        MaintenanceVisit.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .filter(MaintenanceVisit.visit_date < today)
        .count() < 12
        and active_techs
    ):
        for m in range(1, 7):
            code = f'VI-DH{m:02d}'
            exists = (
                MaintenanceVisit.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid, code=code)
                .first()
            )
            if exists:
                continue
            vdate = date(year, m, min(15, 28))
            if dry_run:
                hist_added += 1
                continue
            db.session.add(MaintenanceVisit(
                organization_id=oid,
                code=code,
                elevator_id=elevators[m % len(elevators)].id,
                technician_id=active_techs[m % len(active_techs)].id,
                visit_type='صيانة دورية',
                visit_date=vdate,
                status='مكتملة',
                works_done='صيانة دورية — تجريبي',
                notes=DEMO_OPS_MARKER,
            ))
            hist_added += 1
    stats['visits_history_added'] = hist_added

    # ── أعطال ──
    fault_specs = [
        ('FA-D001', 0, 'توقف مفاجئ', 'حرجة', 'مفتوح'),
        ('FA-D002', 1, 'صوت غير طبيعي', 'عالية', 'قيد المعالجة'),
        ('FA-D003', 2, 'باب لا يغلق', 'عالية', 'مفتوح'),
        ('FA-D004', 3, 'إضاءة لوحة معطلة', 'منخفضة', 'قيد المعالجة'),
        ('FA-D005', 4, 'اهتزاز أثناء الحركة', 'متوسطة', 'قيد المعالجة'),
        ('FA-D010', 5, 'صيانة وقائية', 'عادية', 'محلول'),
    ]
    fault_added = 0
    for code, ei, ftype, priority, status in fault_specs:
        exists = (
            Fault.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=oid, code=code)
            .first()
        )
        if exists:
            continue
        tech = active_techs[fault_added % len(active_techs)] if active_techs else None
        if dry_run:
            fault_added += 1
            continue
        db.session.add(Fault(
            organization_id=oid,
            code=code,
            elevator_id=elevators[min(ei, len(elevators) - 1)].id,
            technician_id=tech.id if tech else None,
            fault_type=ftype,
            description=ftype,
            priority=priority,
            status=status,
            reported_at=_dt(-(fault_added + 1), 9 + fault_added),
            notes=DEMO_OPS_MARKER,
        ))
        fault_added += 1
    stats['faults_added'] = fault_added

    # ── فواتير ──
    inv_count = (
        Invoice.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .count()
    )
    invoice_added = 0
    if inv_count < 8:
        plan = [
            ('INV-D001', 0, 28500, 'مدفوعة', -60, -30),
            ('INV-D002', 1, 22000, 'مدفوعة', -45, -15),
            ('INV-D003', 2, 35000, 'مدفوعة', -30, -5),
            ('INV-D004', 3, 42000, 'مدفوعة', -20, 10),
            ('INV-D005', 4, 18500, 'غير مدفوعة', -40, -10),
            ('INV-D006', 5, 12000, 'غير مدفوعة', -25, -5),
            ('INV-D007', 6, 8500, 'غير مدفوعة', -15, 5),
            ('INV-D008', 7, 6200, 'غير مدفوعة', -50, -20),
        ]
        for code, ci, amount, status, inv_off, due_off in plan:
            if ci >= len(customers):
                continue
            exists = (
                Invoice.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid, code=code)
                .first()
            )
            if exists:
                continue
            cust = customers[ci]
            contract = latest_by_client.get(cust.id)
            tax = round(amount * 0.15, 2)
            if dry_run:
                invoice_added += 1
                continue
            db.session.add(Invoice(
                organization_id=oid,
                code=code,
                invoice_type='فاتورة',
                customer_id=cust.id,
                contract_id=contract.id if contract else None,
                invoice_date=_d(inv_off),
                due_date=_d(due_off),
                description='فاتورة صيانة دورية — تجريبي',
                amount=amount,
                tax_amount=tax,
                total=amount + tax,
                payment_method='تحويل',
                status=status,
            ))
            invoice_added += 1
    stats['invoices_added'] = invoice_added

    # ── إيرادات / مصروفات شهرية ──
    rev_count = (
        Revenue.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .count()
    )
    revenue_added = 0
    if rev_count < 12:
        monthly = [8500, 9200, 11000, 9800, 12500, 14200, 10800, 13500, 11900, 15200, 13800, 16100]
        for m, amt in enumerate(monthly, 1):
            code = f'REV-D{m:03d}'
            exists = (
                Revenue.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid, code=code)
                .first()
            )
            if exists:
                continue
            cust = customers[m % len(customers)]
            contract = latest_by_client.get(cust.id)
            tax = round(amt * 0.15, 2)
            if dry_run:
                revenue_added += 1
                continue
            db.session.add(Revenue(
                organization_id=oid,
                code=code,
                customer_id=cust.id,
                contract_id=contract.id if contract else None,
                revenue_date=date(year, m, 15),
                revenue_type='عقد صيانة',
                payment_method='تحويل',
                amount=amt,
                tax_amount=tax,
                total=amt + tax,
                status='محصّل',
                notes=DEMO_OPS_MARKER,
            ))
            revenue_added += 1
    stats['revenues_added'] = revenue_added

    exp_count = (
        Expense.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .count()
    )
    expense_added = 0
    if exp_count < 12:
        monthly = [3200, 4100, 3800, 4500, 5200, 4800, 3900, 5500, 4700, 5100, 4300, 4900]
        for m, amt in enumerate(monthly, 1):
            code = f'EXP-D{m:03d}'
            exists = (
                Expense.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid, code=code)
                .first()
            )
            if exists:
                continue
            if dry_run:
                expense_added += 1
                continue
            db.session.add(Expense(
                organization_id=oid,
                code=code,
                expense_date=date(year, m, 20),
                expense_type='قطع غيار' if m % 2 else 'رواتب',
                description='مصروف تشغيلي شهري — تجريبي',
                responsible='الإدارة المالية',
                payment_method='تحويل',
                amount=amt,
                notes=DEMO_OPS_MARKER,
            ))
            expense_added += 1
    stats['expenses_added'] = expense_added

    # ── قطع غيار ──
    pb_count = (
        PartsBilling.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .count()
    )
    parts_added = 0
    if pb_count < 5 and active_techs:
        rows = [(0, 0, 1200, 2100), (1, 2, 2800, 4200), (2, 5, 450, 750), (3, 3, 1800, 2900), (4, 1, 620, 950)]
        for i, (ci, ei, cost, sell) in enumerate(rows):
            code = f'PB-D{str(i + 1).zfill(3)}'
            if ci >= len(customers) or ei >= len(elevators):
                continue
            exists = (
                PartsBilling.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid, code=code)
                .first()
            )
            if exists:
                continue
            cust = customers[ci]
            contract = latest_by_client.get(cust.id)
            if dry_run:
                parts_added += 1
                continue
            db.session.add(PartsBilling(
                organization_id=oid,
                code=code,
                customer_id=cust.id,
                contract_id=contract.id if contract else None,
                elevator_id=elevators[ei].id,
                technician_id=active_techs[i % len(active_techs)].id,
                billing_date=_d(-(i + 3)),
                part_name='قطعة غيار — تجريبي',
                quantity=1,
                unit_cost=cost,
                unit_price=sell,
                total_cost=cost,
                total_price=sell,
                status='مفوتر',
                notes=DEMO_OPS_MARKER,
            ))
            parts_added += 1
    stats['parts_billing_added'] = parts_added

    # ── حركات مخزن ──
    mv_count = (
        StockMovement.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .count()
    )
    movement_added = 0
    if mv_count < 2 and items and active_techs:
        specs = [
            ('MV-D001', 0, 'وارد', 'شراء', -10, 30),
            ('MV-D002', min(6, len(items) - 1), 'صادر', 'استخدام في صيانة', -3, 2),
        ]
        for code, item_idx, direction, mtype, day_off, qty in specs:
            exists = (
                StockMovement.query.execution_options(skip_tenant=True)
                .filter_by(organization_id=oid, code=code)
                .first()
            )
            if exists:
                continue
            item = items[item_idx]
            price = item.buy_price or 0
            if dry_run:
                movement_added += 1
                continue
            db.session.add(StockMovement(
                organization_id=oid,
                code=code,
                item_id=item.id,
                movement_date=_d(day_off),
                direction=direction,
                movement_type=mtype,
                quantity=qty,
                unit_price=price,
                total_value=qty * price,
                technician_id=active_techs[0].id if direction == 'صادر' else None,
                elevator_id=elevators[0].id if direction == 'صادر' else None,
                notes=DEMO_OPS_MARKER,
            ))
            movement_added += 1
    stats['stock_movements_added'] = movement_added

    # ── طلب شراء + تقدير (تركيب) ──
    po_count = (
        PurchaseOrder.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .count()
    )
    if po_count == 0 and items and not dry_run:
        po = PurchaseOrder(
            organization_id=oid,
            code='PO-D001',
            supplier='مورد المصاعد المتحدة',
            supplier_phone='0501234567',
            order_date=_d(-5),
            status='معتمد',
            total_amount=(items[0].buy_price or 0) * 4,
            notes='طلب تجريبي — قطع غيار',
        )
        db.session.add(po)
        db.session.flush()
        db.session.add(PurchaseOrderLine(
            organization_id=oid,
            order_id=po.id,
            item_id=items[0].id,
            quantity=4,
            unit_price=items[0].buy_price or 0,
            line_total=4 * (items[0].buy_price or 0),
        ))
        stats['purchase_orders_added'] = 1

    est_count = (
        ElevatorEstimate.query.execution_options(skip_tenant=True)
        .filter_by(organization_id=oid)
        .count()
    )
    if est_count == 0 and len(customers) > 9 and not dry_run:
        client = customers[9]
        est = ElevatorEstimate(
            organization_id=oid,
            code='ES-D001',
            customer_id=client.id,
            project_name='توسعة فندق — تجريبي',
            city='مكة المكرمة',
            machine_type='MR',
            elev_type='مصعد ركاب',
            floors=14,
            stops=14,
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
            notes=DEMO_OPS_MARKER,
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
        stats['estimates_added'] = 1

    return stats


def tenant_summary(org: Organization) -> dict[str, int]:
    oid = org.id
    from models import MaintenanceVisit, Fault

    return {
        'customers': Customer.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'elevators': Elevator.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'contracts': Contract.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'technicians': Technician.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'visits': MaintenanceVisit.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'faults': Fault.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'inventory': InventoryItem.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'revenues': Revenue.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'expenses': Expense.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'invoices': Invoice.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
        'parts_billing': PartsBilling.query.execution_options(skip_tenant=True).filter_by(organization_id=oid).count(),
    }
