"""سير العمل التشغيلي: تخطيط، إرسال، إحصائيات، واتساب."""

from __future__ import annotations

import json
import re
import urllib.parse
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, or_

from models import (
    Contract,
    ContractElevator,
    Customer,
    Elevator,
    Fault,
    InventoryItem,
    MaintenanceVisit,
    PartsBilling,
    Settings,
    Technician,
    db,
)

VISIT_ACTIVE = ('مجدولة', 'مُرسلة للفني', 'جارية')
VISIT_DONE = ('مكتملة', 'ملغاة')


def is_fault_visit_type(visit_type: str | None) -> bool:
    return 'عطل' in (visit_type or '').strip()


def exclude_fault_visits(q):
    """استبعاد زيارات نوعها «عطل» — تُدار من صفحة الأعطال."""
    return q.filter(
        or_(
            MaintenanceVisit.visit_type.is_(None),
            MaintenanceVisit.visit_type == '',
            ~MaintenanceVisit.visit_type.contains('عطل'),
        )
    )
FAULT_OPEN = ('مفتوح', 'قيد المعالجة', 'انتظار قطع')
FAULT_STATUS_FIXED = 'تم الاصلاح'
FAULT_STATUS_FIXED_LEGACY = 'محلول'
FAULT_CLOSED = (FAULT_STATUS_FIXED, FAULT_STATUS_FIXED_LEGACY, 'مغلق')


def next_code(model, prefix, field='code', digits=4):
  import re as _re
  max_num = 0
  pattern = _re.compile(r'^' + _re.escape(prefix) + r'(\d+)$')
  for row in model.query.with_entities(getattr(model, field)).all():
    code = row[0]
    if not code:
      continue
    m = pattern.match(str(code).strip())
    if m:
      max_num = max(max_num, int(m.group(1)))
  return f'{prefix}{str(max_num + 1).zfill(digits)}'


def whatsapp_digits(phone: str) -> str:
    digits = re.sub(r'\D', '', phone or '')
    if not digits:
        return ''
    if digits.startswith('0'):
        return '966' + digits[1:]
    if not digits.startswith('966'):
        return '966' + digits
    return digits


def whatsapp_url(phone: str, message: str) -> str:
    digits = whatsapp_digits(phone)
    if not digits:
        return ''
    return 'https://wa.me/' + digits + '?text=' + urllib.parse.quote(message or '')


def tech_whatsapp_phone(tech: Technician) -> str:
    return (tech.phone2 or tech.phone or '').strip()


def customer_maps_link(customer: Customer) -> str:
    if customer and customer.maps_url:
        return customer.maps_url
    if customer and customer.lat and customer.lng:
        return f'https://www.google.com/maps?q={customer.lat},{customer.lng}'
    if customer and customer.address:
        return 'https://www.google.com/maps/search/?api=1&query=' + urllib.parse.quote(
            f'{customer.address} {customer.district or ""} {customer.city or ""}'.strip()
        )
    return ''


def customer_photo_url(customer: Customer, base: str = '') -> str:
    if not customer or not customer.building_photo_path:
        return ''
    path = customer.building_photo_path.replace('\\', '/')
    if path.startswith('http'):
        return path
    static_path = '/static/' + path.lstrip('/')
    if base:
        return base.rstrip('/') + static_path
    return static_path


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _parse_plan_month(plan_month: str) -> tuple[int, int]:
    y, m = plan_month.strip().split('-')[:2]
    return int(y), int(m)


def _visit_in_plan_month(visit_day: date, plan_month: str) -> bool:
    year, month = _parse_plan_month(plan_month)
    start, end = _month_bounds(year, month)
    return start <= visit_day <= end


def _is_periodic_visit(v: MaintenanceVisit) -> bool:
    vt = (v.visit_type or '').strip()
    return vt in ('دورية', 'صيانة دورية') or 'دور' in vt or 'صيانة' in vt


def _periodic_visit_in_month(elevator_id: int, year: int, month: int) -> MaintenanceVisit | None:
    start, end = _month_bounds(year, month)
    for v in MaintenanceVisit.query.filter(
        MaintenanceVisit.elevator_id == elevator_id,
        MaintenanceVisit.visit_date >= start,
        MaintenanceVisit.visit_date <= end,
        MaintenanceVisit.status != 'ملغية',
    ).all():
        if _is_periodic_visit(v):
            return v
    return None


def _elevator_has_periodic_in_month(elevator_id: int, year: int, month: int) -> bool:
    return _periodic_visit_in_month(elevator_id, year, month) is not None


def _visits_for_plan_month(plan_month: str) -> list[MaintenanceVisit]:
    """زيارات الخطة: مُوسومة بالشهر أو بتاريخها داخل الشهر (بيانات مستوردة)."""
    year, month = _parse_plan_month(plan_month)
    start, end = _month_bounds(year, month)
    return (
        MaintenanceVisit.query.filter(
            MaintenanceVisit.status != 'ملغية',
            or_(
                MaintenanceVisit.plan_month == plan_month,
                and_(
                    or_(
                        MaintenanceVisit.plan_month.is_(None),
                        MaintenanceVisit.plan_month == '',
                    ),
                    MaintenanceVisit.visit_date >= start,
                    MaintenanceVisit.visit_date <= end,
                ),
            ),
        )
        .order_by(MaintenanceVisit.visit_date, MaintenanceVisit.route_order)
        .all()
    )


def _is_maintenance_contract(c: Contract) -> bool:
    ctype = (c.contract_type or '').strip()
    freq = (c.maint_frequency or '').strip()
    ctype_l = ctype.lower()
    freq_l = freq.lower()
    if any(k in ctype for k in ('صيانة', 'ضمان')) or 'maintenance' in ctype_l or 'warranty' in ctype_l:
        return True
    maint_freqs = (
        'شهري', 'monthly', 'ربع سنوي', 'نصف سنوي', 'سنوي',
        'quarterly', 'semi', 'annual', 'yearly',
    )
    return any(f in freq_l or f in freq for f in maint_freqs)


def _elevators_for_contract(contract: Contract) -> list[Elevator]:
    links = ContractElevator.query.filter_by(contract_id=contract.id).all()
    if links:
        ids = [lk.elevator_id for lk in links]
        return Elevator.query.filter(Elevator.id.in_(ids)).all()
    return Elevator.query.filter_by(customer_id=contract.customer_id).all()


def _existing_plan_codes(plan_month: str) -> set[str]:
    rows = MaintenanceVisit.query.filter_by(plan_month=plan_month).all()
    keys = set()
    for v in rows:
        keys.add(f'{v.elevator_id}:{v.visit_date}')
    return keys


def generate_monthly_plan(year: int, month: int, *, replace_draft: bool = False) -> dict:
    """توليد زيارات دورية لشهر محدد من العقود النشطة."""
    start, end = _month_bounds(year, month)
    plan_month = f'{year}-{month:02d}'
    today = date.today()

    if replace_draft:
        MaintenanceVisit.query.filter(
            MaintenanceVisit.plan_month == plan_month,
            MaintenanceVisit.status.in_(('مجدولة', 'مُرسلة للفني')),
        ).delete(synchronize_session=False)

    contracts = Contract.query.filter(
        Contract.start_date <= end,
        Contract.end_date >= start,
        or_(Contract.status == 'نشط', Contract.status.is_(None), Contract.status == ''),
    ).all()

    district_groups: dict[str, list[dict]] = defaultdict(list)
    created = 0
    skipped = 0
    linked = 0
    existing = _existing_plan_codes(plan_month)

    work_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    work_days = [d for d in work_days if d.weekday() != 4]  # استبعاد الجمعة

    for contract in contracts:
        if not _is_maintenance_contract(contract):
            continue
        customer = contract.customer
        for elev in _elevators_for_contract(contract):
            district = _customer_district(customer, elev)
            district_groups[district].append({
                'contract': contract,
                'elevator': elev,
                'customer': customer,
            })

    next_code_num = int(next_code(MaintenanceVisit, 'VI-', digits=5).replace('VI-', ''))
    day_idx = 0
    for district in sorted(district_groups.keys()):
        items = district_groups[district]
        for item in items:
            elev = item['elevator']
            contract = item['contract']
            visit_day = work_days[day_idx % len(work_days)] if work_days else start
            day_idx += 1
            existing_v = _periodic_visit_in_month(elev.id, year, month)
            if existing_v:
                if not existing_v.plan_month:
                    existing_v.plan_month = plan_month
                    linked += 1
                else:
                    skipped += 1
                continue
            key = f'{elev.id}:{visit_day}'
            if key in existing:
                skipped += 1
                continue

            visit_code = f'VI-{str(next_code_num).zfill(5)}'
            next_code_num += 1
            v = MaintenanceVisit(
                code=visit_code,
                contract_id=contract.id,
                elevator_id=elev.id,
                visit_type='دورية',
                visit_date=visit_day,
                priority='عادية',
                status='مجدولة',
                plan_month=plan_month,
                route_order=0,
                observations=f'خطة شهر {plan_month} — {district}',
            )
            db.session.add(v)
            db.session.flush()
            existing.add(key)
            created += 1

    db.session.commit()
    result = get_plan(plan_month)
    payload = {
        **result,
        'created': created,
        'linked': linked,
        'skipped': skipped,
        'districts': len(district_groups),
    }
    if not district_groups:
        payload['hint'] = (
            'لا توجد عقود صيانة نشطة تغطي هذا الشهر — '
            'تأكد من العقود (نوع صيانة/ضمان)، الحالة «نشط»، وربط المصاعد.'
        )
    elif created == 0 and linked == 0 and not result.get('total'):
        payload['hint'] = 'لم يُنشأ شيء — قد تكون الزيارات موجودة مسبقاً أو المصاعد بدون عقد نشط.'
    return payload


def _customer_district(cust: Customer | None, elev: Elevator | None = None) -> str:
    if cust and (cust.district or '').strip():
        return cust.district.strip()
    if elev and (elev.district or '').strip():
        return elev.district.strip()
    if cust and (cust.city or '').strip():
        return cust.city.strip()
    if elev and (elev.city or '').strip():
        return elev.city.strip()
    return 'غير محدد'


def visit_district_name(v: MaintenanceVisit) -> str:
    elev = v.elevator
    cust = elev.customer if elev else None
    return _customer_district(cust, elev)


def list_districts() -> list[str]:
    districts: set[str] = set()
    for c in Customer.query.all():
        d = _customer_district(c, None)
        if d != 'غير محدد':
            districts.add(d)
    for e in Elevator.query.all():
        d = _customer_district(e.customer if e.customer else None, e)
        if d != 'غير محدد':
            districts.add(d)
    return sorted(districts) if districts else ['غير محدد']


def elevators_for_district(district: str) -> list[dict]:
    seen: set[int] = set()
    rows: list[dict] = []
    for e in Elevator.query.join(Customer).order_by(Customer.name).all():
        if e.id in seen:
            continue
        if _customer_district(e.customer, e) != district:
            continue
        seen.add(e.id)
        c = e.customer
        rows.append({
            'elevator_id': e.id,
            'elevator_code': e.code,
            'customer_id': c.id if c else None,
            'customer_name': c.name if c else '—',
            'customer_code': c.code if c else '',
            'district': district,
        })
    return rows


def get_plan(plan_month: str) -> dict:
    visits = _visits_for_plan_month(plan_month)
    rows = [_visit_plan_row(v) for v in visits]
    by_district: dict[str, list] = defaultdict(list)
    for r in rows:
        by_district[r['district'] or 'غير محدد'].append(r)
    tech_groups: dict[int | None, list] = defaultdict(list)
    for r in rows:
        tech_groups[r.get('technician_id')].append(r)
    tech_summary = []
    for tid, items in tech_groups.items():
        dists = sorted({i['district'] for i in items if i.get('district')})
        tech_summary.append({
            'technician_id': tid,
            'technician': items[0]['technician'] if items else '—',
            'count': len(items),
            'districts': dists,
        })
    tech_summary.sort(key=lambda x: (-x['count'], x['technician'] or ''))
    return {
        'plan_month': plan_month,
        'total': len(rows),
        'districts': len(by_district),
        'visits': rows,
        'by_district': {k: len(v) for k, v in by_district.items()},
        'tech_summary': tech_summary,
    }


def _visit_plan_row(v: MaintenanceVisit) -> dict:
    cust = v.elevator.customer if v.elevator else None
    return {
        'id': v.id,
        'code': v.code,
        'visit_date': str(v.visit_date or ''),
        'district': visit_district_name(v),
        'customer': cust.name if cust else '—',
        'customer_code': cust.code if cust else '',
        'elevator': v.elevator.code if v.elevator else '',
        'technician_id': v.technician_id or None,
        'technician': v.technician.name if v.technician else '— بدون فني —',
        'status': v.status,
        'route_order': v.route_order or 0,
    }


def generate_district_plan(year: int, month: int, district: str) -> dict:
    """توليد زيارات شهرية لمنطقة واحدة فقط."""
    start, end = _month_bounds(year, month)
    plan_month = f'{year}-{month:02d}'
    contracts = Contract.query.filter(
        Contract.start_date <= end,
        Contract.end_date >= start,
        or_(Contract.status == 'نشط', Contract.status.is_(None), Contract.status == ''),
    ).all()
    existing = _existing_plan_codes(plan_month)
    work_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    work_days = [d for d in work_days if d.weekday() != 4]
    next_code_num = int(next_code(MaintenanceVisit, 'VI-', digits=5).replace('VI-', ''))
    created = 0
    skipped = 0
    linked = 0
    day_idx = 0
    for contract in contracts:
        if not _is_maintenance_contract(contract):
            continue
        customer = contract.customer
        for elev in _elevators_for_contract(contract):
            if _customer_district(customer, elev) != district:
                continue
            existing_v = _periodic_visit_in_month(elev.id, year, month)
            if existing_v:
                if not existing_v.plan_month:
                    existing_v.plan_month = plan_month
                    linked += 1
                else:
                    skipped += 1
                continue
            visit_day = work_days[day_idx % len(work_days)] if work_days else start
            day_idx += 1
            key = f'{elev.id}:{visit_day}'
            if key in existing:
                skipped += 1
                continue
            visit_code = f'VI-{str(next_code_num).zfill(5)}'
            next_code_num += 1
            v = MaintenanceVisit(
                code=visit_code,
                contract_id=contract.id,
                elevator_id=elev.id,
                visit_type='دورية',
                visit_date=visit_day,
                priority='عادية',
                status='مجدولة',
                plan_month=plan_month,
                route_order=0,
                observations=f'خطة شهر {plan_month} — {district}',
            )
            db.session.add(v)
            db.session.flush()
            existing.add(key)
            created += 1
    db.session.commit()
    return get_plan(plan_month) | {
        'created': created, 'linked': linked, 'skipped': skipped, 'district': district,
    }


def add_manual_plan_visit(plan_month: str, elevator_id: int, visit_date: str) -> dict:
    """إضافة زيارة واحدة للخطة يدوياً — داخل شهر الخطة فقط."""
    elev = Elevator.query.get(int(elevator_id))
    if not elev:
        raise ValueError('المصعد غير موجود')
    cust = elev.customer
    district = _customer_district(cust, elev)
    vdate = datetime.strptime(visit_date[:10], '%Y-%m-%d').date()
    if not _visit_in_plan_month(vdate, plan_month):
        raise ValueError(f'تاريخ الزيارة يجب أن يكون داخل شهر {plan_month}')
    year, month = _parse_plan_month(plan_month)
    if _elevator_has_periodic_in_month(elev.id, year, month):
        raise ValueError('هذا المصعد لديه زيارة دورية في هذا الشهر مسبقاً')
    from entity_links import active_contract_for_elevator

    contract = active_contract_for_elevator(elev.id, vdate)
    v = MaintenanceVisit(
        code=next_code(MaintenanceVisit, 'VI-', digits=5),
        contract_id=contract.id if contract else None,
        elevator_id=elev.id,
        visit_type='دورية',
        visit_date=vdate,
        priority='عادية',
        status='مجدولة',
        plan_month=plan_month,
        route_order=0,
        observations=f'إضافة يدوية — خطة {plan_month} — {district}',
    )
    db.session.add(v)
    db.session.commit()
    return _visit_plan_row(v)


def assign_visits_to_technician(
    visit_ids: list[int], technician_id: int, plan_month: str = ''
) -> int:
    """تعيين زيارات محددة لفني (يدعم عدة فرق في نفس المنطقة)."""
    from technician_assignments import sync_visit_technicians

    updated = 0
    plan_months: set[str] = set()
    for vid in visit_ids:
        v = MaintenanceVisit.query.get(int(vid))
        if not v:
            continue
        v.technician_id = int(technician_id)
        sync_visit_technicians(v, [int(technician_id)])
        if plan_month and not v.plan_month:
            v.plan_month = plan_month
        if v.plan_month:
            plan_months.add(v.plan_month)
        updated += 1
    db.session.commit()
    for pm in plan_months:
        _reorder_routes(pm)
    return updated


def assign_district_technician(
    plan_month: str, district: str, technician_id: int, *, only_unassigned: bool = True
) -> int:
    """تعيين زيارات المنطقة — افتراضياً غير المكلفة فقط."""
    from technician_assignments import sync_visit_technicians

    visits = _visits_for_plan_month(plan_month)
    updated = 0
    for v in visits:
        if visit_district_name(v) != district:
            continue
        if only_unassigned and v.technician_id:
            continue
        v.technician_id = technician_id
        sync_visit_technicians(v, [technician_id])
        updated += 1
    db.session.commit()
    _reorder_routes(plan_month)
    return updated


def assign_visit_technician(visit_id: int, technician_id: int) -> None:
    from technician_assignments import sync_visit_technicians

    v = MaintenanceVisit.query.get_or_404(visit_id)
    v.technician_id = technician_id
    sync_visit_technicians(v, [technician_id])
    db.session.commit()


def _reorder_routes(plan_month: str) -> None:
    visits = sorted(
        _visits_for_plan_month(plan_month),
        key=lambda v: (v.technician_id or 0, v.visit_date or date.min),
    )
    by_tech_day: dict[tuple, list] = defaultdict(list)
    for v in visits:
        by_tech_day[(v.technician_id, v.visit_date)].append(v)
    for group in by_tech_day.values():
        for i, v in enumerate(sorted(group, key=lambda x: x.id), start=1):
            v.route_order = i
    db.session.commit()


def _resolve_dispatch_day(day: str | None = None, on_date: date | None = None) -> date:
    """اليوم أو غداً أو تاريخ محدد YYYY-MM-DD."""
    today = on_date or date.today()
    key = (day or 'today').strip().lower()
    if key in ('today', 'اليوم'):
        return today
    if key in ('tomorrow', 'غدا', 'غداً'):
        return today + timedelta(days=1)
    if key and len(key) >= 10:
        return datetime.strptime(key[:10], '%Y-%m-%d').date()
    return today


def _dispatch_day_label(target: date, on_date: date | None = None) -> str:
    today = on_date or date.today()
    if target == today:
        return f'زيارات اليوم ({target})'
    if target == today + timedelta(days=1):
        return f'زيارات غداً ({target})'
    return f'زيارات {target}'


def dispatch_technician_route(
    technician_id: int,
    base_url: str = '',
    *,
    dispatch_day: str = 'today',
) -> dict:
    """إرسال زيارات يوم واحد فقط للفني — اليوم أو غداً (لا يُرسل الشهر كاملاً)."""
    target = _resolve_dispatch_day(dispatch_day)
    q = MaintenanceVisit.query.filter(
        MaintenanceVisit.technician_id == technician_id,
        MaintenanceVisit.visit_date == target,
        MaintenanceVisit.status.in_(('مجدولة', 'مُرسلة للفني')),
    )
    visits = q.order_by(MaintenanceVisit.route_order, MaintenanceVisit.id).all()
    day_label = _dispatch_day_label(target)
    tech = Technician.query.get(technician_id)
    if not visits:
        return {
            'count': 0,
            'dispatch_day': str(target),
            'day_label': day_label,
            'technician': tech.name if tech else '',
            'whatsapp_url': '',
            'error': f'لا توجد زيارات مجدولة لـ{day_label}',
        }
    now = datetime.utcnow()
    for v in visits:
        v.status = 'مُرسلة للفني'
        v.dispatched_at = now
    db.session.commit()
    return {
        'count': len(visits),
        'dispatch_day': str(target),
        'day_label': day_label,
        'technician': tech.name if tech else '',
        'whatsapp_url': build_route_whatsapp(tech, visits, base_url, day_label=day_label) if tech else '',
    }


def build_route_whatsapp(
    tech: Technician, visits: list[MaintenanceVisit], base_url: str = '', *, day_label: str = ''
) -> str:
    if not tech or not visits:
        return ''
    title = day_label or 'خط سير الصيانة'
    lines = [f'📋 {title} — {tech.name}', '']
    for i, v in enumerate(visits, start=1):
        cust = v.elevator.customer if v.elevator else None
        lines.append(f'{i}. {cust.code if cust else ""} — {cust.name if cust else "—"}')
        lines.append(f'   📍 {(cust.district if cust else "") or "—"} | {v.visit_date}')
        if cust and cust.address:
            lines.append(f'   {cust.address}')
        link = customer_maps_link(cust) if cust else ''
        if link:
            lines.append(f'   🗺 {link}')
        lines.append('')
    if base_url:
        lines.append(f'🔗 مهامك على الجوال:\n{base_url.rstrip("/")}/field/login')
    return whatsapp_url(tech_whatsapp_phone(tech), '\n'.join(lines))


def build_fault_whatsapp(fault: Fault, base_url: str = '') -> str:
    if not fault or not fault.technician:
        return ''
    elev = fault.elevator
    cust = elev.customer if elev else None
    lines = [
        f'🚨 بلاغ عطل جديد {fault.code}',
        f'العميل: {cust.name if cust else "—"} ({cust.code if cust else ""})',
        f'المصعد: {elev.code if elev else "—"}',
        f'المنطقة: {(cust.district if cust else "") or "—"}',
        f'الأولوية: {fault.priority or "عادية"}',
        f'نوع العطل: {fault.fault_type or "—"}',
        '',
        'وصف البلاغ:',
        fault.client_report or fault.description or '—',
        '',
    ]
    if cust and cust.address:
        lines.append(f'العنوان: {cust.address}')
    link = customer_maps_link(cust) if cust else ''
    if link:
        lines.append(f'🗺 {link}')
    if base_url:
        lines.append(f'\n🔗 نفّذ من الجوال:\n{base_url.rstrip("/")}/field/fault/{fault.id}')
    return whatsapp_url(tech_whatsapp_phone(fault.technician), '\n'.join(lines))


def dispatch_fault(fault_id: int, base_url: str = '') -> dict:
    fault = Fault.query.get_or_404(fault_id)
    if not fault.technician_id:
        return {'error': 'لم يُعيَّن فني', 'whatsapp_url': ''}
    fault.dispatched_at = datetime.utcnow()
    if fault.status == 'مفتوح':
        fault.status = 'قيد المعالجة'
    db.session.commit()
    return {
        'whatsapp_url': build_fault_whatsapp(fault, base_url),
        'fault_id': fault.id,
    }


def visit_stats(today: date | None = None) -> dict:
    today = today or date.today()
    month_start = today.replace(day=1)
    month_end = today.replace(day=monthrange(today.year, today.month)[1])
    q = exclude_fault_visits(MaintenanceVisit.query)
    return {
        'today': q.filter(MaintenanceVisit.visit_date == today).count(),
        'in_progress': q.filter(MaintenanceVisit.status.in_(('جارية', 'مُرسلة للفني'))).count(),
        'late': q.filter(
            MaintenanceVisit.visit_date < today,
            ~MaintenanceVisit.status.in_(VISIT_DONE),
        ).count(),
        'done_today': q.filter(
            MaintenanceVisit.status == 'مكتملة',
            or_(
                func.date(MaintenanceVisit.completed_at) == today,
                and_(
                    MaintenanceVisit.completed_at.is_(None),
                    MaintenanceVisit.visit_date == today,
                ),
            ),
        ).count(),
        'month': q.filter(
            MaintenanceVisit.visit_date >= month_start,
            MaintenanceVisit.visit_date <= month_end,
        ).count(),
        'scheduled_tomorrow': q.filter(
            MaintenanceVisit.visit_date == today + timedelta(days=1),
            MaintenanceVisit.status == 'مجدولة',
        ).count(),
    }


def visit_alerts(today: date | None = None) -> list[dict]:
    today = today or date.today()
    alerts = []
    late = exclude_fault_visits(MaintenanceVisit.query).filter(
        MaintenanceVisit.visit_date < today,
        ~MaintenanceVisit.status.in_(VISIT_DONE),
    ).count()
    if late:
        alerts.append({
            'level': 'danger',
            'filter': 'late',
            'text': f'{late} زيارة متأخرة — تجاوزت الموعد المحدد',
        })
    critical = exclude_fault_visits(MaintenanceVisit.query).filter(
        MaintenanceVisit.priority == 'حرجة',
        ~MaintenanceVisit.status.in_(VISIT_DONE),
    ).count()
    if critical:
        alerts.append({
            'level': 'warning',
            'filter': 'critical',
            'text': f'{critical} زيارة حرجة لم تُكتمل بعد',
        })
    tomorrow = exclude_fault_visits(MaintenanceVisit.query).filter(
        MaintenanceVisit.visit_date == today + timedelta(days=1),
        MaintenanceVisit.status == 'مجدولة',
    ).count()
    if tomorrow:
        alerts.append({
            'level': 'info',
            'filter': 'tomorrow',
            'text': f'{tomorrow} زيارة مجدولة غداً',
        })
    return alerts


def fault_stats(today: date | None = None) -> dict:
    today = today or date.today()
    q = Fault.query
    closed_today = q.filter(
        Fault.status.in_(FAULT_CLOSED),
        Fault.resolved_at >= datetime.combine(today, datetime.min.time()),
    ).count()
    waiting_parts = q.filter(Fault.status == 'انتظار قطع').count()
    billable = q.filter(Fault.billed.is_(False), Fault.needs_parts.is_(True)).count()
    return {
        'critical': q.filter(Fault.priority == 'حرجة', Fault.status.in_(FAULT_OPEN)).count(),
        'open': q.filter(Fault.status == 'مفتوح').count(),
        'in_progress': q.filter(Fault.status == 'قيد المعالجة').count(),
        'waiting_parts': waiting_parts,
        'closed_today': closed_today,
        'billable': billable,
        'avg_response': '—',
    }


def fault_alerts() -> list[dict]:
    alerts = []
    critical = Fault.query.filter(
        Fault.priority == 'حرجة',
        Fault.status.in_(FAULT_OPEN),
    ).limit(5).all()
    if critical:
        alerts.append({
            'level': 'critical',
            'text': f'{len(critical)} عطل حرج يحتاج تدخلاً فورياً',
        })
    waiting = Fault.query.filter_by(status='انتظار قطع').count()
    if waiting:
        alerts.append({
            'level': 'warning',
            'text': f'{waiting} عطل بانتظار توفير قطع الغيار',
        })
    old = Fault.query.filter(
        Fault.status.in_(('مفتوح', 'قيد المعالجة')),
        Fault.reported_at < datetime.utcnow() - timedelta(hours=48),
    ).count()
    if old:
        alerts.append({
            'level': 'warning',
            'text': f'{old} عطل تجاوز 48 ساعة بدون إغلاق',
        })
    return alerts


def parts_stats() -> dict:
    parts = PartsBilling.query.all()
    pending_faults = Fault.query.filter_by(status='انتظار قطع').count()
    return {
        'pending_fault_requests': pending_faults,
        'awaiting_client': PartsBilling.query.filter_by(status='بانتظار موافقة العميل').count(),
        'awaiting_supply': PartsBilling.query.filter_by(status='بانتظار التوريد').count(),
    }


def parts_alerts() -> list[dict]:
    alerts = []
    n = Fault.query.filter_by(status='انتظار قطع').count()
    if n:
        alerts.append({
            'level': 'warning',
            'text': f'{n} طلب قطع غيار من الفنيين بانتظار المكتب',
        })
    n2 = PartsBilling.query.filter_by(status='بانتظار موافقة العميل').count()
    if n2:
        alerts.append({
            'level': 'info',
            'text': f'{n2} عرض سعر بانتظار موافقة العميل',
        })
    return alerts


def field_technician_payload(tech_id: int, base_url: str = '', on_date: date | None = None, portal_kind: str = 'both') -> dict:
    """مهام الفني على الجوال: اليوم وغداً فقط — حسب فريق الفني."""
    from technician_assignments import visits_for_technician_filter, faults_for_technician_filter

    tech = Technician.query.get_or_404(tech_id)
    today = on_date or date.today()
    tomorrow = today + timedelta(days=1)
    show_visits = portal_kind in ('maintenance', 'both')
    show_faults = portal_kind in ('faults', 'both')

    today_visits: list = []
    tomorrow_visits: list = []
    visits: list = []
    if show_visits:
        visits = (
            MaintenanceVisit.query.filter(
                visits_for_technician_filter(tech_id),
                MaintenanceVisit.visit_date.in_([today, tomorrow]),
                MaintenanceVisit.status.in_(VISIT_ACTIVE),
            )
            .order_by(MaintenanceVisit.visit_date, MaintenanceVisit.route_order)
            .all()
        )
        today_visits = [v for v in visits if v.visit_date == today]
        tomorrow_visits = [v for v in visits if v.visit_date == tomorrow]

    faults: list = []
    has_assigned_faults = (
        Fault.query.filter(
            faults_for_technician_filter(tech_id),
            Fault.status.in_(FAULT_OPEN),
        ).count()
        > 0
    )
    if show_faults or has_assigned_faults:
        faults = (
            Fault.query.filter(
                faults_for_technician_filter(tech_id),
                Fault.status.in_(FAULT_OPEN),
            )
            .order_by(Fault.reported_at.desc())
            .all()
        )

    return {
        'technician': {
            'id': tech.id,
            'name': tech.name,
            'phone': tech_whatsapp_phone(tech),
            'team': tech.team or 'عام',
            'portal_kind': portal_kind,
        },
        'today': str(today),
        'tomorrow': str(tomorrow),
        'visits_today': [field_visit_summary(v, base_url) for v in today_visits],
        'visits_tomorrow': [field_visit_summary(v, base_url) for v in tomorrow_visits],
        'visits': [field_visit_summary(v, base_url) for v in visits],
        'faults': [field_fault_summary(f, base_url) for f in faults],
        'show_visits': show_visits,
        'show_faults': show_faults or bool(faults),
    }


def field_visit_summary(v: MaintenanceVisit, base_url: str = '') -> dict:
    cust = v.elevator.customer if v.elevator else None
    return {
        'id': v.id,
        'code': v.code,
        'visit_date': str(v.visit_date or ''),
        'visit_type': v.visit_type or '',
        'status': v.status,
        'route_order': v.route_order or 0,
        'customer': cust.name if cust else '—',
        'customer_code': cust.code if cust else '',
        'district': (cust.district if cust else '') or '—',
        'address': cust.address if cust else '',
        'maps_url': customer_maps_link(cust) if cust else '',
        'building_photo': customer_photo_url(cust, base_url),
        'elevator': v.elevator.code if v.elevator else '',
        'url': f'/field/visit/{v.id}',
    }


def field_fault_summary(f: Fault, base_url: str = '') -> dict:
    elev = f.elevator
    cust = elev.customer if elev else None
    return {
        'id': f.id,
        'code': f.code,
        'priority': f.priority or 'عادية',
        'status': f.status,
        'fault_type': f.fault_type or '',
        'client_report': f.client_report or f.description or '',
        'customer': cust.name if cust else '—',
        'customer_code': cust.code if cust else '',
        'district': (cust.district if cust else '') or '—',
        'address': cust.address if cust else '',
        'maps_url': customer_maps_link(cust) if cust else '',
        'building_photo': customer_photo_url(cust, base_url),
        'elevator': elev.code if elev else '',
        'needs_parts': bool(f.needs_parts),
        'url': f'/field/fault/{f.id}',
    }


def field_visit_detail(visit_id: int, tech_id: int | None = None) -> dict:
    from checklist_templates import parse_report_json, report_completion_stats
    from technician_assignments import technician_assigned_to_visit, visit_technicians_label

    v = MaintenanceVisit.query.get_or_404(visit_id)
    if tech_id and not technician_assigned_to_visit(v, tech_id):
        raise PermissionError('الزيارة غير مخصصة لهذا الفني')
    cust = v.elevator.customer if v.elevator else None
    saved = parse_report_json(v.checklist_json)
    stats = report_completion_stats(saved, v.checklist_template_key)
    return {
        'id': v.id,
        'code': v.code,
        'visit_date': str(v.visit_date or ''),
        'visit_type': v.visit_type or '',
        'status': v.status,
        'works_done': v.works_done or '',
        'observations': v.observations or '',
        'has_report': bool(saved and stats.get('filled', 0) > 0),
        'report_stats': stats,
        'customer': cust.name if cust else '—',
        'customer_code': cust.code if cust else '',
        'district': (cust.district if cust else '') or '—',
        'address': cust.address if cust else '',
        'maps_url': customer_maps_link(cust) if cust else '',
        'building_photo': customer_photo_url(cust),
        'elevator': v.elevator.code if v.elevator else '',
        'technician_id': v.technician_id,
        'technician': visit_technicians_label(v),
    }


def field_fault_detail(fault_id: int, tech_id: int | None = None) -> dict:
    from technician_assignments import technician_assigned_to_fault, fault_technicians_label

    f = Fault.query.get_or_404(fault_id)
    if tech_id and not technician_assigned_to_fault(f, tech_id):
        raise PermissionError('العطل غير مخصص لهذا الفني')
    elev = f.elevator
    cust = elev.customer if elev else None
    tech = f.technician
    return {
        'id': f.id,
        'code': f.code,
        'priority': f.priority or 'عادية',
        'status': f.status,
        'fault_type': f.fault_type or '',
        'client_report': f.client_report or f.description or '',
        'tech_notes': f.tech_notes or '',
        'resolution': f.resolution or '',
        'needs_parts': bool(f.needs_parts),
        'customer': cust.name if cust else '—',
        'customer_code': cust.code if cust else '',
        'district': (cust.district if cust else '') or '—',
        'address': cust.address if cust else '',
        'maps_url': customer_maps_link(cust) if cust else '',
        'building_photo': customer_photo_url(cust),
        'elevator': elev.code if elev else '',
        'technician_id': f.technician_id,
        'technician_name': tech.name if tech else '—',
        'report_url': f'/field/fault/{f.id}/report',
        'has_report': bool(f.report_json),
    }


def fault_report_payload(
    fault_id: int,
    *,
    editable: bool = False,
    tech_id: int | None = None,
    base_url: str = '',
    field_times_locked: bool = False,
) -> dict:
    from fault_report import FAULT_TYPE_OPTIONS, merge_fault_report, parse_fault_report_json, report_stats
    from models import InventoryItem
    from technician_assignments import technician_assigned_to_fault

    f = Fault.query.get_or_404(fault_id)
    if tech_id and not technician_assigned_to_fault(f, tech_id):
        raise PermissionError('العطل غير مخصص لهذا الفني')
    elev = f.elevator
    cust = elev.customer if elev else None
    contract = None
    if elev:
        from models import Contract, ContractElevator
        link = ContractElevator.query.filter_by(elevator_id=elev.id).first()
        if link:
            contract = Contract.query.get(link.contract_id)
    tech = f.technician
    saved = parse_fault_report_json(f.report_json)
    report_data = merge_fault_report(saved, f)
    stats = report_stats(report_data)
    reported = f.reported_at.strftime('%Y-%m-%d %H:%M') if f.reported_at else ''

    return {
        'fault_id': f.id,
        'editable': editable,
        'tech_id': tech_id or f.technician_id,
        'field_times_locked': field_times_locked,
        'fault': {
            'code': f.code,
            'fault_type': f.fault_type or '',
            'priority': f.priority or 'عادية',
            'status': f.status or '',
            'reported_at': reported,
            'client_report': f.client_report or f.description or '',
            'reporter_name': f.reporter_name or '',
            'reporter_phone': f.reporter_phone or '',
            'billed': bool(f.billed),
            'report_stats': stats,
        },
        'customer': {
            'name': cust.name if cust else '—',
            'code': cust.code if cust else '',
            'phone': cust.phone if cust else '',
            'city': cust.city if cust else '',
            'district': cust.district if cust else '',
            'address': cust.address if cust else '',
            'building_photo': customer_photo_url(cust, base_url) if cust else '',
        },
        'elevator': {
            'code': elev.code if elev else '',
            'brand': (elev.elev_type if elev else '') or '',
            'building': elev.building_name if elev else '',
        },
        'contract': {
            'code': contract.code if contract else '',
            'type': 'عقد صيانة نشط' if contract else 'بدون عقد',
        },
        'technician': {
            'id': tech.id if tech else None,
            'name': tech.name if tech else '—',
        },
        'fault_type_options': FAULT_TYPE_OPTIONS,
        'fault_type_options_json': json.dumps(FAULT_TYPE_OPTIONS, ensure_ascii=False),
        'report_data': report_data,
        'report_data_json': json.dumps(report_data, ensure_ascii=False),
        'inventory_items_json': json.dumps([
            {
                'id': i.id,
                'code': i.code,
                'name': i.name,
                'unit': i.unit or 'قطعة',
                'buy_price': i.buy_price or 0,
                'sell_price': i.sell_price or 0,
                'current_qty': i.current_qty or 0,
            }
            for i in InventoryItem.query.order_by(InventoryItem.name).all()
        ], ensure_ascii=False),
        'logo_url': _report_brand_logo_url(),
        'company_name': _report_company_name(),
        'company_name_en': _report_company_name_en(),
        'base_url': base_url,
    }


def _report_brand_logo_url() -> str:
    settings = Settings.query.first()
    if settings and settings.logo_path:
        try:
            from app import upload_url
            return upload_url(settings.logo_path)
        except Exception:
            return '/static/' + str(settings.logo_path).replace('\\', '/')
    return '/static/logo.png'


def _report_company_name() -> str:
    settings = Settings.query.first()
    return (settings.company_name if settings and settings.company_name else 'LiftCore')


def _report_company_name_en() -> str:
    settings = Settings.query.first()
    return (settings.company_name_en if settings and settings.company_name_en else '')


def save_fault_report(
    fault_id: int,
    payload: dict,
    *,
    mark_resolved: bool = False,
    status: str | None = None,
) -> dict:
    from fault_report import apply_report_to_fault, merge_fault_report, parse_fault_report_json

    f = Fault.query.get_or_404(fault_id)
    existing = parse_fault_report_json(f.report_json)
    merged = merge_fault_report(existing, f)

    if isinstance(payload, dict):
        meta = payload.get('meta') or {}
        if isinstance(meta, dict):
            for key in merged['meta']:
                if key in meta:
                    merged['meta'][key] = meta.get(key) if meta.get(key) is not None else ''
        if isinstance(payload.get('parts'), list):
            merged['parts'] = payload['parts']
        sig = payload.get('signatures') or {}
        if isinstance(sig, dict):
            merged['signatures']['tech'] = sig.get('tech') or merged['signatures'].get('tech') or ''
            merged['signatures']['client'] = sig.get('client') or merged['signatures'].get('client') or ''
        if isinstance(payload.get('photos'), list):
            merged['photos'] = payload['photos']

    _preserve_field_start_times(merged, existing)

    if mark_resolved:
        merged['meta'] = _apply_field_end_timestamp(merged.get('meta') or {})

    apply_report_to_fault(f, merged, mark_resolved=mark_resolved)
    if status:
        f.status = status
    f.report_json = json.dumps(merged, ensure_ascii=False)
    db.session.commit()
    return merged


def complete_field_visit(
    visit_id: int,
    *,
    works_done: str = '',
    observations: str = '',
    status: str = 'مكتملة',
    report_data: dict | None = None,
) -> None:
    v = MaintenanceVisit.query.get_or_404(visit_id)
    if report_data is not None:
        save_visit_report(visit_id, report_data, mark_complete=True, status=status)
        return
    v.works_done = works_done
    v.observations = observations
    v.status = status or 'مكتملة'
    if status == 'مكتملة':
        v.completed_at = datetime.utcnow()
    db.session.commit()


def _default_checklist_template_key() -> str:
    row = Settings.query.first()
    from checklist_templates import DEFAULT_TEMPLATE_KEY, template_for_settings
    return template_for_settings(row)['key'] if row else DEFAULT_TEMPLATE_KEY


def _field_stamp_now() -> dict:
    """توقيت محلي للميدان (تاريخ + وقت)."""
    now = datetime.now()
    return {
        'date': now.strftime('%Y-%m-%d'),
        'time': now.strftime('%H:%M'),
        'dt': now,
    }


def _apply_field_end_timestamp(meta: dict) -> dict:
    parts = _field_stamp_now()
    meta['end_time'] = parts['time']
    if not (meta.get('visit_date') or '').strip():
        meta['visit_date'] = parts['date']
    return meta


def _preserve_field_start_times(merged: dict, existing: dict | None) -> None:
    """بعد الدمج — لا تسمح بتغيير وقت/تاريخ البدء إذا سُجّلا مسبقاً."""
    em = (existing or {}).get('meta') or {}
    meta = merged.setdefault('meta', {})
    for key in ('visit_date', 'arrival_time'):
        if (em.get(key) or '').strip():
            meta[key] = em[key]


def stamp_field_visit_report_start(visit_id: int, tech_id: int | None = None) -> None:
    """عند فتح الفني لمحضر الصيانة — تسجيل تاريخ ووقت الوصول (مرة واحدة)."""
    from checklist_templates import merge_report_data, parse_report_json
    from technician_assignments import technician_assigned_to_visit

    v = MaintenanceVisit.query.get_or_404(visit_id)
    if tech_id and not technician_assigned_to_visit(v, tech_id):
        raise PermissionError('الزيارة غير مخصصة لهذا الفني')
    template_key = v.checklist_template_key or _default_checklist_template_key()
    saved = parse_report_json(v.checklist_json)
    data = merge_report_data(saved, template_key)
    meta = data.setdefault('meta', {})
    if (meta.get('arrival_time') or '').strip():
        return

    parts = _field_stamp_now()
    meta['visit_date'] = parts['date']
    meta['arrival_time'] = parts['time']
    v.checklist_json = json.dumps(data, ensure_ascii=False)
    if not v.visit_time:
        v.visit_time = parts['time']
    if (v.status or '') in ('', 'مجدولة', 'مُجدولة', 'مجدول'):
        v.status = 'جارية'
    if not v.dispatched_at:
        v.dispatched_at = parts['dt']
    db.session.commit()


def stamp_field_fault_report_start(fault_id: int, tech_id: int | None = None) -> None:
    """عند فتح الفني لتقرير العطل — تسجيل تاريخ ووقت الوصول (مرة واحدة)."""
    from fault_report import merge_fault_report, parse_fault_report_json
    from technician_assignments import technician_assigned_to_fault

    f = Fault.query.get_or_404(fault_id)
    if tech_id and not technician_assigned_to_fault(f, tech_id):
        raise PermissionError('العطل غير مخصص لهذا الفني')
    saved = parse_fault_report_json(f.report_json)
    data = merge_fault_report(saved, f)
    meta = data['meta']
    if (meta.get('arrival_time') or '').strip():
        return

    parts = _field_stamp_now()
    meta['visit_date'] = parts['date']
    meta['arrival_time'] = parts['time']
    f.report_json = json.dumps(data, ensure_ascii=False)
    if not f.responded_at:
        f.responded_at = parts['dt']
    if (f.status or '') in ('', 'مفتوح', 'جديد'):
        f.status = 'قيد المعالجة'
    db.session.commit()


def visit_report_payload(
    visit_id: int,
    *,
    editable: bool = False,
    tech_id: int | None = None,
    base_url: str = '',
    field_times_locked: bool = False,
) -> dict:
    """بيانات محضر الفحص للعرض/الطباعة."""
    from checklist_templates import (
        get_template,
        merge_report_data,
        parse_report_json,
        report_completion_stats,
    )
    from technician_assignments import technician_assigned_to_visit, visit_technicians_label

    v = MaintenanceVisit.query.get_or_404(visit_id)
    if tech_id and not technician_assigned_to_visit(v, tech_id):
        raise PermissionError('الزيارة غير مخصصة لهذا الفني')

    elev = v.elevator
    cust = elev.customer if elev else None
    contract = v.contract
    tech = v.technician
    template_key = v.checklist_template_key or _default_checklist_template_key()
    saved = parse_report_json(v.checklist_json)
    report_data = merge_report_data(saved, template_key)
    stats = report_completion_stats(report_data, template_key)
    template = get_template(template_key)
    meta = report_data.get('meta') or {}
    visit_date_display = (meta.get('visit_date') or '').strip() or str(v.visit_date or '')

    return {
        'visit_id': v.id,
        'editable': editable,
        'tech_id': tech_id or v.technician_id,
        'field_times_locked': field_times_locked,
        'visit_date_display': visit_date_display,
        'visit': {
            'code': v.code,
            'visit_type': v.visit_type or 'صيانة دورية',
            'visit_date': str(v.visit_date or ''),
            'visit_time': v.visit_time or '',
            'priority': v.priority or 'عادية',
            'status': v.status or '',
            'works_done': v.works_done or '',
            'observations': v.observations or '',
            'next_visit_date': str(v.next_visit_date or report_data['meta'].get('next_visit') or ''),
            'completed_at': v.completed_at.isoformat() if v.completed_at else '',
            'has_report': bool(saved and stats['filled'] > 0),
            'report_stats': stats,
        },
        'customer': {
            'name': cust.name if cust else '—',
            'code': cust.code if cust else '',
            'city': cust.city if cust else '',
            'district': cust.district if cust else '',
            'address': cust.address if cust else '',
        },
        'elevator': {
            'code': elev.code if elev else '',
            'type': (elev.elev_type if elev else '') or (elev.building_name if elev else ''),
            'location': elev.building_name if elev else '',
        },
        'contract': {
            'code': contract.code if contract else '',
        },
        'technician': {
            'id': tech.id if tech else None,
            'name': tech.name if tech else '—',
            'national_id': tech.national_id if tech else '',
        },
        'checklist_template': template,
        'report_data': report_data,
        'report_data_json': json.dumps(report_data, ensure_ascii=False),
        'template_json': json.dumps(template, ensure_ascii=False),
        'logo_url': _report_brand_logo_url(),
        'base_url': base_url,
        'sign_config': _visit_sign_config(),
    }


def _visit_sign_config() -> dict:
    from models import Settings

    s = Settings.query.first()
    method = (getattr(s, 'default_sign_method', None) or 'pin').strip() if s else 'pin'
    if method not in ('draw', 'pin', 'both'):
        method = 'both'
    rep_sig = (getattr(s, 'rep_signature_path', None) or '') if s else ''
    return {
        'default_method': method,
        'pin_enabled': True,
        'rep_has_signature': bool(rep_sig),
    }


def save_visit_report(
    visit_id: int,
    payload: dict,
    *,
    mark_complete: bool = False,
    status: str = 'مكتملة',
) -> dict:
    """حفظ محضر الفحص على الزيارة."""
    from checklist_templates import checklist_summary_lines, merge_report_data, parse_report_json

    v = MaintenanceVisit.query.get_or_404(visit_id)
    template_key = (
        (payload.get('template_key') if isinstance(payload, dict) else None)
        or v.checklist_template_key
        or _default_checklist_template_key()
    )
    existing = parse_report_json(v.checklist_json)
    merged = merge_report_data(existing, template_key)

    if isinstance(payload, dict):
        incoming_items = payload.get('items') or {}
        if isinstance(incoming_items, dict):
            for item_id, val in incoming_items.items():
                if item_id in merged['items'] and isinstance(val, dict):
                    merged['items'][item_id] = {
                        'status': val.get('status') or '',
                        'note': val.get('note') or '',
                    }
        meta = payload.get('meta') or {}
        if isinstance(meta, dict):
            for key in merged['meta']:
                if key in meta:
                    merged['meta'][key] = meta.get(key) or ''
        sig = payload.get('signatures') or {}
        if isinstance(sig, dict):
            for key in merged['signatures']:
                if key in sig:
                    merged['signatures'][key] = sig.get(key) or ''
        if isinstance(payload.get('photos'), list):
            merged['photos'] = payload['photos']

    _preserve_field_start_times(merged, existing)

    if mark_complete:
        merged['meta'] = _apply_field_end_timestamp(merged.get('meta') or {})

    merged['template_key'] = template_key
    v.checklist_template_key = template_key
    v.checklist_json = json.dumps(merged, ensure_ascii=False)

    meta = merged.get('meta') or {}
    tech_notes = (meta.get('tech_notes') or '').strip()
    issues = (meta.get('issues_found') or '').strip()
    parts = (meta.get('parts_used') or '').strip()
    summary = checklist_summary_lines(merged, template_key)
    works_parts = [p for p in [tech_notes, '\n'.join(summary)] if p]
    if works_parts:
        v.works_done = '\n\n'.join(works_parts)
    obs_parts = [p for p in [issues, parts] if p]
    if obs_parts:
        v.observations = '\n\n'.join(obs_parts)
    next_v = (meta.get('next_visit') or '').strip()
    if next_v and len(next_v) >= 10:
        try:
            v.next_visit_date = datetime.strptime(next_v[:10], '%Y-%m-%d').date()
        except ValueError:
            pass

    if mark_complete:
        v.status = status or 'مكتملة'
        v.completed_at = datetime.utcnow()

    db.session.commit()
    return merged


def complete_field_fault(
    fault_id: int,
    *,
    tech_notes: str,
    resolution: str,
    status: str = FAULT_STATUS_FIXED,
) -> None:
    f = Fault.query.get_or_404(fault_id)
    f.tech_notes = tech_notes
    f.resolution = resolution
    f.status = status or FAULT_STATUS_FIXED
    f.resolved_at = datetime.utcnow()
    db.session.commit()


PARTS_JSON_PREFIX = 'PARTS_JSON:'


def parts_billing_notes_display(notes: str | None) -> str:
    """عرض ملاحظات المستخدم فقط — إخفاء بيانات PARTS_JSON الداخلية."""
    if not notes or not str(notes).strip():
        return ''
    raw = str(notes).strip()
    if raw.startswith(PARTS_JSON_PREFIX):
        try:
            payload = json.loads(raw[len(PARTS_JSON_PREFIX):])
            if isinstance(payload, dict):
                return str(payload.get('label') or '').strip()
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return ''
    return raw


def parse_fault_parts_lines(raw: str | None) -> list[dict]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    lines = []
    for row in data:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or '').strip()
        item_id = row.get('item_id')
        if item_id not in (None, '', 0, '0'):
            item = InventoryItem.query.get(int(item_id))
            if item and not name:
                name = item.name
        qty = float(row.get('qty') or 1)
        unit_price = float(row.get('unit_price') or 0)
        cost_price = float(row.get('cost_price') or 0)
        if item_id not in (None, '', 0, '0') and not cost_price:
            item = InventoryItem.query.get(int(item_id))
            if item:
                cost_price = float(item.buy_price or 0)
        if not name or qty <= 0:
            continue
        lines.append({
            'item_id': int(item_id) if item_id not in (None, '', 0, '0') else None,
            'name': name,
            'qty': qty,
            'unit_price': unit_price,
            'cost_price': cost_price,
        })
    return lines


def format_fault_parts_description(lines: list[dict]) -> str:
    return '\n'.join(
        f"{ln['qty']}× {ln['name']} — {ln['unit_price']:.2f} \u20C1"
        for ln in lines
    )


def parts_billing_invoice_lines(pb: PartsBilling | None) -> list[dict]:
    """بنود الفاتورة من عملية قطع الغيار (PARTS_JSON أو الوصف)."""
    if not pb:
        return []

    def _row(name: str, qty: float, unit_price: float) -> dict:
        q = float(qty or 1)
        u = float(unit_price or 0)
        return {
            'name': name.strip(),
            'qty': q,
            'unit_price': round(u, 2),
            'total': round(q * u, 2),
        }

    if pb.notes and str(pb.notes).startswith(PARTS_JSON_PREFIX):
        try:
            payload = json.loads(str(pb.notes)[len(PARTS_JSON_PREFIX):])
            rows = []
            for row in payload.get('lines') or []:
                if not isinstance(row, dict):
                    continue
                name = str(row.get('name') or '').strip()
                if not name and row.get('item_id'):
                    item = InventoryItem.query.get(int(row['item_id']))
                    name = item.name if item else ''
                qty = float(row.get('qty') or 1)
                unit_price = float(row.get('unit_price') or 0)
                if name and qty > 0:
                    rows.append(_row(name, qty, unit_price))
            if rows:
                return rows
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    if pb.description:
        parsed = []
        for line in str(pb.description).splitlines():
            text = line.strip()
            if not text:
                continue
            m = re.match(
                r'(\d+(?:\.\d+)?)\s*[×xX]\s*(.+?)\s*[—–\-]\s*([\d.,]+)',
                text,
            )
            if m:
                qty = float(m.group(1).replace(',', ''))
                name = m.group(2).strip()
                unit_price = float(m.group(3).replace(',', ''))
                parsed.append(_row(name, qty, unit_price))
            else:
                parsed.append(_row(text, 1, float(pb.sell_price or 0)))
        if parsed:
            return parsed

    if pb.sell_price or pb.description:
        return [_row(pb.description or 'قطع غيار / خدمة', 1, float(pb.sell_price or 0))]
    return []


def fault_registration_parts_lines(fault_id: int) -> list[dict]:
    pb = (
        PartsBilling.query.filter_by(fault_id=fault_id)
        .order_by(PartsBilling.id.desc())
        .first()
    )
    if not pb or not pb.notes or not pb.notes.startswith(PARTS_JSON_PREFIX):
        return []
    try:
        payload = json.loads(pb.notes[len(PARTS_JSON_PREFIX):])
        return payload.get('lines') or []
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def clear_fault_parts_billing(fault_id: int) -> None:
    PartsBilling.query.filter_by(fault_id=fault_id).delete()


def apply_fault_parts_billing(
    fault: Fault,
    lines: list[dict],
    *,
    technician_id: int | None = None,
) -> PartsBilling | None:
    if not lines:
        return None
    sell = round(sum(ln['qty'] * ln['unit_price'] for ln in lines), 2)
    cost = round(sum(ln['qty'] * ln['cost_price'] for ln in lines), 2)
    elev = fault.elevator
    cust = elev.customer if elev else None
    pb = PartsBilling.query.filter_by(fault_id=fault.id).order_by(PartsBilling.id.desc()).first()
    if not pb:
        pb = PartsBilling(code=next_code(PartsBilling, 'PB-', digits=3), fault_id=fault.id)
        db.session.add(pb)
    pb.customer_id = cust.id if cust else None
    pb.elevator_id = elev.id if elev else None
    pb.technician_id = technician_id or fault.technician_id
    pb.visit_id = fault.visit_id
    pb.billing_date = date.today()
    pb.description = format_fault_parts_description(lines)
    pb.cost_price = cost
    pb.sell_price = sell
    pb.profit = round(sell - cost, 2)
    pb.status = 'غير محصل'
    pb.notes = PARTS_JSON_PREFIX + json.dumps(
        {'lines': lines, 'label': 'جاهز للفوترة'},
        ensure_ascii=False,
    )
    return pb


def request_fault_parts(fault_id: int, *, description: str, sell_price: float = 0) -> PartsBilling:
    """الفني يطلب قطع — يُنبّه المكتب."""
    f = Fault.query.get_or_404(fault_id)
    elev = f.elevator
    cust = elev.customer if elev else None
    f.needs_parts = True
    f.status = 'انتظار قطع'
    f.tech_notes = (f.tech_notes or '') + (
        '\n[طلب قطع] ' + description if description else ''
    )

    part = PartsBilling(
        code=next_code(PartsBilling, 'PB-', digits=3),
        customer_id=cust.id if cust else None,
        contract_id=None,
        elevator_id=elev.id if elev else None,
        technician_id=f.technician_id,
        fault_id=f.id,
        visit_id=f.visit_id,
        billing_date=date.today(),
        description=description or f'قطع غيار للعطل {f.code}',
        cost_price=0,
        sell_price=sell_price,
        profit=0,
        status='بانتظار موافقة العميل',
        notes='طلب من الفني — بانتظار موافقة العميل على السعر',
    )
    db.session.add(part)
    db.session.commit()
    return part
