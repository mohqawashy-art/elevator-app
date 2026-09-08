"""حضور وانصراف — حسابات، فروع، استيراد."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import g
from sqlalchemy import and_

from models import (
    AttendanceBranch,
    AttendanceDay,
    AttendanceEmployee,
    AttendancePunch,
    BiometricDevice,
    Technician,
    db,
)
from tenant_scope import assign_organization, tenant_query

RIYADH = ZoneInfo('Asia/Riyadh')
SHIFT_START = time(8, 0)
SHIFT_END = time(17, 0)
LATE_GRACE_MINUTES = 10
WORK_WEEKDAYS = frozenset({6, 0, 1, 2, 3})  # الأحد–الخميس


def local_date(dt: datetime) -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(RIYADH).date()


def utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def parse_punch_timestamp(raw: str) -> datetime | None:
    text = (raw or '').strip()
    if not text:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            parsed = datetime.strptime(text, fmt)
            return utc_naive(parsed.replace(tzinfo=RIYADH))
        except ValueError:
            continue
    return None


def ensure_default_branch() -> AttendanceBranch:
    branch = tenant_query(AttendanceBranch).filter_by(is_default=True).first()
    if branch:
        return branch
    branch = tenant_query(AttendanceBranch).filter_by(code='BR-001').first()
    if branch:
        if not branch.is_default:
            branch.is_default = True
            db.session.commit()
        return branch
    branch = AttendanceBranch(
        code='BR-001',
        name='المكتب الرئيسي',
        name_en='Main Office',
        is_default=True,
        is_active=True,
    )
    assign_organization(branch)
    db.session.add(branch)
    db.session.commit()
    return branch


def next_biometric_user_id() -> str:
    rows = (
        tenant_query(AttendanceEmployee)
        .with_entities(AttendanceEmployee.biometric_user_id)
        .all()
    )
    max_num = 1000
    for (bio_id,) in rows:
        try:
            max_num = max(max_num, int(str(bio_id).strip()))
        except (TypeError, ValueError):
            continue
    return str(max_num + 1)


def employee_to_js_dict(emp: AttendanceEmployee) -> dict:
    branch_name = emp.branch.name if emp.branch else ''
    return {
        'id': emp.id,
        'code': emp.code or '',
        'name': emp.name or '',
        'name_en': emp.name_en or '',
        'job_title': emp.job_title or '',
        'department': emp.department or '',
        'branch_id': emp.branch_id,
        'branch_name': branch_name,
        'technician_id': emp.technician_id,
        'biometric_user_id': emp.biometric_user_id or '',
        'phone': emp.phone or '',
        'national_id': emp.national_id or '',
        'hire_date': emp.hire_date.isoformat() if emp.hire_date else '',
        'salary': emp.salary,
        'status': emp.status or 'نشط',
        'notes': emp.notes or '',
    }


def device_to_js_dict(device: BiometricDevice) -> dict:
    branch_name = device.branch.name if device.branch else ''
    online = False
    if device.last_seen_at:
        online = (datetime.utcnow() - device.last_seen_at) < timedelta(minutes=10)
    return {
        'id': device.id,
        'serial_number': device.serial_number or '',
        'name': device.name or '',
        'model': device.model or '',
        'branch_id': device.branch_id,
        'branch_name': branch_name,
        'is_active': bool(device.is_active),
        'online': online,
        'last_seen_at': device.last_seen_at.isoformat() if device.last_seen_at else '',
        'last_ip': device.last_ip or '',
        'firmware': device.firmware or '',
    }


def find_device_by_serial(serial_number: str) -> BiometricDevice | None:
    sn = (serial_number or '').strip()
    if not sn:
        return None
    return (
        BiometricDevice.query.execution_options(skip_tenant=True)
        .filter_by(serial_number=sn, is_active=True)
        .first()
    )


def bind_device_tenant(device: BiometricDevice) -> None:
    g.organization_id = device.organization_id
    g.organization = None


def find_employee_by_bio_id(bio_id: str) -> AttendanceEmployee | None:
    return tenant_query(AttendanceEmployee).filter_by(
        biometric_user_id=str(bio_id).strip(),
        status='نشط',
    ).first()


def is_workday(day: date) -> bool:
    return day.weekday() in WORK_WEEKDAYS


def recompute_attendance_day(employee_id: int, work_date: date) -> AttendanceDay | None:
    if not is_workday(work_date):
        return None

    day_start = datetime.combine(work_date, time.min).replace(tzinfo=RIYADH)
    day_end = day_start + timedelta(days=1)
    start_utc = utc_naive(day_start.astimezone(timezone.utc))
    end_utc = utc_naive(day_end.astimezone(timezone.utc))

    punches = (
        tenant_query(AttendancePunch)
        .filter(
            AttendancePunch.employee_id == employee_id,
            AttendancePunch.punched_at >= start_utc,
            AttendancePunch.punched_at < end_utc,
        )
        .order_by(AttendancePunch.punched_at.asc())
        .all()
    )

    day = tenant_query(AttendanceDay).filter_by(
        employee_id=employee_id,
        work_date=work_date,
    ).first()
    if not day:
        day = AttendanceDay(
            employee_id=employee_id,
            work_date=work_date,
            shift_start='08:00',
            shift_end='17:00',
        )
        assign_organization(day)
        db.session.add(day)

    if not punches:
        day.check_in = None
        day.check_out = None
        day.late_minutes = 0
        day.early_leave_minutes = 0
        day.worked_minutes = 0
        day.status = 'غائب' if work_date < local_date(datetime.utcnow()) else 'لم يحضر'
        day.updated_at = datetime.utcnow()
        return day

    check_ins = [p for p in punches if p.status_code in (0, 4)]
    check_outs = [p for p in punches if p.status_code in (1, 5)]
    check_in = check_ins[0].punched_at if check_ins else punches[0].punched_at
    check_out = check_outs[-1].punched_at if check_outs else (
        punches[-1].punched_at if len(punches) > 1 else None
    )

    day.check_in = check_in
    day.check_out = check_out

    shift_start_dt = datetime.combine(work_date, SHIFT_START).replace(tzinfo=RIYADH)
    shift_end_dt = datetime.combine(work_date, SHIFT_END).replace(tzinfo=RIYADH)
    grace_end = shift_start_dt + timedelta(minutes=LATE_GRACE_MINUTES)

    check_in_local = check_in.replace(tzinfo=timezone.utc).astimezone(RIYADH)
    late_minutes = 0
    if check_in_local > grace_end:
        late_minutes = int((check_in_local - shift_start_dt).total_seconds() // 60)
    day.late_minutes = max(0, late_minutes)

    early_leave_minutes = 0
    worked_minutes = 0
    if check_out:
        check_out_local = check_out.replace(tzinfo=timezone.utc).astimezone(RIYADH)
        if check_out_local < shift_end_dt:
            early_leave_minutes = int((shift_end_dt - check_out_local).total_seconds() // 60)
        worked_minutes = max(0, int((check_out - check_in).total_seconds() // 60))
    day.early_leave_minutes = max(0, early_leave_minutes)
    day.worked_minutes = worked_minutes

    if not check_out:
        day.status = 'ناقص'
    elif late_minutes > 0 and early_leave_minutes > 0:
        day.status = 'متأخر + انصراف مبكر'
    elif late_minutes > 0:
        day.status = 'متأخر'
    elif early_leave_minutes > 0:
        day.status = 'انصراف مبكر'
    else:
        day.status = 'حاضر'
    day.updated_at = datetime.utcnow()
    return day


def ingest_attendance_punch(
    *,
    device: BiometricDevice,
    biometric_user_id: str,
    punched_at: datetime,
    status_code: int = 0,
    verify_mode: int = 0,
    work_code: int = 0,
    raw_line: str = '',
) -> AttendancePunch | None:
    bind_device_tenant(device)
    employee = find_employee_by_bio_id(biometric_user_id)
    punched_at = utc_naive(punched_at)

    existing = (
        tenant_query(AttendancePunch)
        .filter_by(
            device_id=device.id,
            biometric_user_id=str(biometric_user_id).strip(),
            punched_at=punched_at,
        )
        .first()
    )
    if existing:
        return existing

    punch = AttendancePunch(
        device_id=device.id,
        employee_id=employee.id if employee else None,
        biometric_user_id=str(biometric_user_id).strip(),
        punched_at=punched_at,
        status_code=status_code,
        verify_mode=verify_mode,
        work_code=work_code,
        raw_line=(raw_line or '')[:300],
    )
    assign_organization(punch)
    db.session.add(punch)

    device.last_seen_at = datetime.utcnow()
    if employee:
        recompute_attendance_day(employee.id, local_date(punched_at))
    db.session.commit()
    return punch


def _next_employee_code() -> str:
    import re

    max_num = 0
    pattern = re.compile(r'^EMP-(\d+)$')
    for (code,) in tenant_query(AttendanceEmployee).with_entities(AttendanceEmployee.code).all():
        m = pattern.match(str(code or '').strip())
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f'EMP-{str(max_num + 1).zfill(3)}'


def import_technicians_as_employees() -> dict[str, int]:
    branch = ensure_default_branch()
    created = 0
    linked = 0
    techs = tenant_query(Technician).order_by(Technician.id.asc()).all()
    for tech in techs:
        existing = tenant_query(AttendanceEmployee).filter_by(technician_id=tech.id).first()
        if existing:
            linked += 1
            continue
        emp = AttendanceEmployee(
            code=_next_employee_code(),
            name=tech.name,
            name_en=tech.name_en,
            job_title=tech.job_title or 'فني',
            department='الصيانة',
            branch_id=branch.id,
            technician_id=tech.id,
            biometric_user_id=next_biometric_user_id(),
            phone=tech.phone,
            national_id=tech.national_id,
            hire_date=tech.hire_date,
            salary=tech.salary,
            status='نشط' if (tech.status or '') != 'غير نشط' else 'غير نشط',
        )
        assign_organization(emp)
        db.session.add(emp)
        created += 1
    db.session.commit()
    return {'created': created, 'linked': linked, 'total_technicians': len(techs)}


def today_summary(work_date: date | None = None) -> dict:
    work_date = work_date or local_date(datetime.utcnow())
    employees = (
        tenant_query(AttendanceEmployee)
        .filter_by(status='نشط')
        .order_by(AttendanceEmployee.name.asc())
        .all()
    )
    days = {
        d.employee_id: d
        for d in tenant_query(AttendanceDay).filter_by(work_date=work_date).all()
    }
    rows = []
    stats = {'total': 0, 'present': 0, 'late': 0, 'absent': 0, 'incomplete': 0, 'off': 0}
    for emp in employees:
        day = days.get(emp.id)
        if not is_workday(work_date):
            status = 'إجازة أسبوعية'
            stats['off'] += 1
        elif not day:
            status = 'لم يحضر' if work_date >= local_date(datetime.utcnow()) else 'غائب'
            if status == 'غائب':
                stats['absent'] += 1
            else:
                stats['incomplete'] += 1
        else:
            status = day.status or 'غائب'
            if status == 'حاضر':
                stats['present'] += 1
            elif status in ('متأخر', 'متأخر + انصراف مبكر'):
                stats['late'] += 1
            elif status in ('غائب', 'لم يحضر'):
                stats['absent'] += 1
            else:
                stats['incomplete'] += 1
        stats['total'] += 1
        rows.append({
            'employee_id': emp.id,
            'code': emp.code,
            'name': emp.name,
            'biometric_user_id': emp.biometric_user_id,
            'branch_name': emp.branch.name if emp.branch else '',
            'check_in': day.check_in.strftime('%H:%M') if day and day.check_in else '—',
            'check_out': day.check_out.strftime('%H:%M') if day and day.check_out else '—',
            'late_minutes': day.late_minutes if day else 0,
            'status': status,
        })
    return {'work_date': work_date.isoformat(), 'rows': rows, 'stats': stats}


def monthly_report(year: int, month: int) -> dict:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    employees = (
        tenant_query(AttendanceEmployee)
        .filter_by(status='نشط')
        .order_by(AttendanceEmployee.name.asc())
        .all()
    )
    days = (
        tenant_query(AttendanceDay)
        .filter(and_(AttendanceDay.work_date >= start, AttendanceDay.work_date < end))
        .all()
    )
    by_emp: dict[int, list[AttendanceDay]] = {}
    for day in days:
        by_emp.setdefault(day.employee_id, []).append(day)

    rows = []
    for emp in employees:
        emp_days = by_emp.get(emp.id, [])
        present = sum(1 for d in emp_days if d.status == 'حاضر')
        late = sum(1 for d in emp_days if 'متأخر' in (d.status or ''))
        absent = sum(1 for d in emp_days if d.status in ('غائب', 'لم يحضر'))
        incomplete = sum(1 for d in emp_days if d.status in ('ناقص', 'انصراف مبكر'))
        total_late_min = sum(d.late_minutes or 0 for d in emp_days)
        total_worked = sum(d.worked_minutes or 0 for d in emp_days)
        rows.append({
            'employee_id': emp.id,
            'code': emp.code,
            'name': emp.name,
            'biometric_user_id': emp.biometric_user_id,
            'present_days': present,
            'late_days': late,
            'absent_days': absent,
            'incomplete_days': incomplete,
            'total_late_minutes': total_late_min,
            'total_worked_minutes': total_worked,
        })
    return {'year': year, 'month': month, 'rows': rows}
