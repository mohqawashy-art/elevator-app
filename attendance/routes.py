"""واجهات حضور وانصراف."""

from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from attendance.protocols import PROTOCOL_CHOICES, PROTOCOL_HELP, normalize_protocol
from attendance.service import (
    device_to_js_dict,
    employee_to_js_dict,
    ensure_default_branch,
    ensure_manual_device,
    import_technicians_as_employees,
    ingest_attendance_punch,
    monthly_report,
    new_device_auth_token,
    next_biometric_user_id,
    parse_punch_timestamp,
    punch_status_from_event,
    today_summary,
)
from models import AttendanceBranch, AttendanceEmployee, BiometricDevice, db
from tenant_scope import assign_organization, tenant_get_or_404, tenant_query

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')
adms_bp = Blueprint('attendance_adms', __name__, url_prefix='/iclock')


def _parse_float(raw, default=0.0):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_date(raw):
    text = (raw or '').strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _branches_js():
    return [
        {'id': b.id, 'code': b.code, 'name': b.name, 'is_default': bool(b.is_default)}
        for b in tenant_query(AttendanceBranch).filter_by(is_active=True).order_by(AttendanceBranch.id).all()
    ]


@attendance_bp.route('/employees')
def employees_page():
    ensure_default_branch()
    emps = tenant_query(AttendanceEmployee).order_by(AttendanceEmployee.name.asc()).all()
    return render_template(
        'attendance_employees.html',
        employees_js=[employee_to_js_dict(e) for e in emps],
        branches_js=_branches_js(),
        next_bio_id=next_biometric_user_id(),
    )


@attendance_bp.route('/employees/add', methods=['POST'])
def employees_add():
    ensure_default_branch()
    branch_id = request.form.get('branch_id', type=int)
    if not branch_id:
        branch = ensure_default_branch()
        branch_id = branch.id
    bio_id = (request.form.get('biometric_user_id') or next_biometric_user_id()).strip()
    if tenant_query(AttendanceEmployee).filter_by(biometric_user_id=bio_id).first():
        flash('رقم البصمة مستخدم لموظف آخر.', 'error')
        return redirect(url_for('attendance.employees_page', department=request.args.get('department')))

    from attendance.service import _next_employee_code

    emp = AttendanceEmployee(
        code=(request.form.get('code') or _next_employee_code()).strip(),
        name=(request.form.get('name') or '').strip(),
        name_en=(request.form.get('name_en') or '').strip() or None,
        job_title=(request.form.get('job_title') or '').strip() or None,
        department=(request.form.get('department') or '').strip() or None,
        branch_id=branch_id,
        biometric_user_id=bio_id,
        phone=(request.form.get('phone') or '').strip() or None,
        national_id=(request.form.get('national_id') or '').strip() or None,
        hire_date=_parse_date(request.form.get('hire_date')),
        salary=_parse_float(request.form.get('salary'), 0) or None,
        status=(request.form.get('status') or 'نشط').strip(),
        notes=(request.form.get('notes') or '').strip() or None,
    )
    if not emp.name:
        flash('اسم الموظف مطلوب.', 'error')
        return redirect(url_for('attendance.employees_page', department=request.args.get('department')))
    assign_organization(emp)
    db.session.add(emp)
    db.session.commit()
    flash('تمت إضافة الموظف.', 'success')
    return redirect(url_for('attendance.employees_page', department=request.args.get('department')))


@attendance_bp.route('/employees/edit/<int:emp_id>', methods=['POST'])
def employees_edit(emp_id):
    emp = tenant_get_or_404(AttendanceEmployee, emp_id)
    bio_id = (request.form.get('biometric_user_id') or emp.biometric_user_id).strip()
    clash = tenant_query(AttendanceEmployee).filter(
        AttendanceEmployee.biometric_user_id == bio_id,
        AttendanceEmployee.id != emp.id,
    ).first()
    if clash:
        flash('رقم البصمة مستخدم لموظف آخر.', 'error')
        return redirect(url_for('attendance.employees_page', department=request.args.get('department')))

    emp.name = (request.form.get('name') or emp.name).strip()
    emp.name_en = (request.form.get('name_en') or '').strip() or None
    emp.job_title = (request.form.get('job_title') or '').strip() or None
    emp.department = (request.form.get('department') or '').strip() or None
    emp.branch_id = request.form.get('branch_id', type=int) or emp.branch_id
    emp.biometric_user_id = bio_id
    emp.phone = (request.form.get('phone') or '').strip() or None
    emp.national_id = (request.form.get('national_id') or '').strip() or None
    emp.hire_date = _parse_date(request.form.get('hire_date')) or emp.hire_date
    salary = _parse_float(request.form.get('salary'), 0)
    emp.salary = salary or None
    emp.status = (request.form.get('status') or emp.status).strip()
    emp.notes = (request.form.get('notes') or '').strip() or None
    db.session.commit()
    flash('تم تحديث بيانات الموظف.', 'success')
    return redirect(url_for('attendance.employees_page', department=request.args.get('department')))


@attendance_bp.route('/employees/import-technicians', methods=['POST'])
def employees_import_technicians():
    stats = import_technicians_as_employees()
    flash(
        f"استيراد الفنيين: {stats['created']} جديد، {stats['linked']} مربوط مسبقاً.",
        'success',
    )
    return redirect(url_for('attendance.employees_page', department=request.args.get('department')))


@attendance_bp.route('/today')
def today_page():
    work_date_raw = (request.args.get('date') or '').strip()
    work_date = date.fromisoformat(work_date_raw) if work_date_raw else None
    summary = today_summary(work_date)
    employees = tenant_query(AttendanceEmployee).filter_by(status='نشط').order_by(
        AttendanceEmployee.name.asc(),
    ).all()
    return render_template(
        'attendance_today.html',
        summary=summary,
        employees_js=[employee_to_js_dict(e) for e in employees],
    )


@attendance_bp.route('/monthly')
def monthly_page():
    today = date.today()
    year = request.args.get('year', type=int) or today.year
    month = request.args.get('month', type=int) or today.month
    report = monthly_report(year, month)
    return render_template('attendance_monthly.html', report=report)


@attendance_bp.route('/devices')
def devices_page():
    ensure_default_branch()
    devices = tenant_query(BiometricDevice).order_by(BiometricDevice.id.desc()).all()
    host = (request.host or '').split(':')[0]
    return render_template(
        'attendance_devices.html',
        devices_js=[device_to_js_dict(d) for d in devices],
        branches_js=_branches_js(),
        protocol_choices=PROTOCOL_CHOICES,
        protocol_help=PROTOCOL_HELP,
        server_host=host,
    )


@attendance_bp.route('/devices/add', methods=['POST'])
def devices_add():
    branch = ensure_default_branch()
    branch_id = request.form.get('branch_id', type=int) or branch.id
    serial = (request.form.get('serial_number') or '').strip()
    name = (request.form.get('name') or '').strip()
    protocol = normalize_protocol(request.form.get('protocol'))
    if protocol == 'manual':
        from attendance.service import effective_organization_id_for_attendance
        serial = serial or f'MANUAL-ORG-{effective_organization_id_for_attendance()}'
    if not serial or not name:
        flash('الرقم التسلسلي واسم الجهاز مطلوبان.', 'error')
        return redirect(url_for('attendance.devices_page', department=request.args.get('department')))
    if BiometricDevice.query.filter_by(serial_number=serial).first():
        flash('الرقم التسلسلي مسجّل مسبقاً.', 'error')
        return redirect(url_for('attendance.devices_page', department=request.args.get('department')))

    device = BiometricDevice(
        branch_id=branch_id,
        serial_number=serial,
        name=name,
        model=(request.form.get('model') or 'ZKTeco').strip(),
        protocol=protocol,
        auth_token=new_device_auth_token(),
        is_active=True,
    )
    assign_organization(device)
    db.session.add(device)
    db.session.commit()
    flash('تم تسجيل جهاز البصمة.', 'success')
    return redirect(url_for('attendance.devices_page', department=request.args.get('department')))


@attendance_bp.route('/devices/edit/<int:device_id>', methods=['POST'])
def devices_edit(device_id):
    device = tenant_get_or_404(BiometricDevice, device_id)
    device.name = (request.form.get('name') or device.name).strip()
    device.model = (request.form.get('model') or device.model).strip()
    device.branch_id = request.form.get('branch_id', type=int) or device.branch_id
    device.protocol = normalize_protocol(request.form.get('protocol'), device.protocol or 'adms_zkteco')
    device.is_active = (request.form.get('status') or 'نشط') == 'نشط'
    db.session.commit()
    flash('تم تحديث الجهاز.', 'success')
    return redirect(url_for('attendance.devices_page', department=request.args.get('department')))


@attendance_bp.route('/branches/add', methods=['POST'])
def branches_add():
    code = (request.form.get('code') or '').strip()
    name = (request.form.get('name') or '').strip()
    if not code or not name:
        flash('رمز الفرع واسمه مطلوبان.', 'error')
        return redirect(request.referrer or url_for('attendance.devices_page'))
    if tenant_query(AttendanceBranch).filter_by(code=code).first():
        flash('رمز الفرع مستخدم.', 'error')
        return redirect(request.referrer or url_for('attendance.devices_page'))
    branch = AttendanceBranch(
        code=code,
        name=name,
        name_en=(request.form.get('name_en') or '').strip() or None,
        is_default=False,
        is_active=True,
    )
    assign_organization(branch)
    db.session.add(branch)
    db.session.commit()
    flash('تمت إضافة الفرع.', 'success')
    return redirect(request.referrer or url_for('attendance.devices_page'))


@attendance_bp.route('/punch/manual', methods=['POST'])
def punch_manual():
    emp_id = request.form.get('employee_id', type=int)
    emp = tenant_get_or_404(AttendanceEmployee, emp_id) if emp_id else None
    if not emp or emp.status != 'نشط':
        flash('اختر موظفاً نشطاً.', 'error')
        return redirect(url_for('attendance.today_page', department=request.args.get('department')))

    date_raw = (request.form.get('punch_date') or '').strip()
    time_raw = (request.form.get('punch_time') or '').strip()
    ts = parse_punch_timestamp(f'{date_raw} {time_raw}')
    if not ts:
        flash('التاريخ أو الوقت غير صالح.', 'error')
        return redirect(url_for('attendance.today_page', department=request.args.get('department')))

    device = ensure_manual_device()
    status_code = punch_status_from_event(request.form.get('punch_type') or 'in', default=0)
    ingest_attendance_punch(
        device=device,
        biometric_user_id=emp.biometric_user_id,
        punched_at=ts,
        status_code=status_code,
        verify_mode=0,
        raw_line='manual',
    )
    flash('تم تسجيل الحركة.', 'success')
    return redirect(url_for('attendance.today_page', date=date_raw, department=request.args.get('department')))


@attendance_bp.route('/api/punch', methods=['POST'])
def api_punch():
    from attendance.webhook import handle_webhook_punch
    return handle_webhook_punch()


@adms_bp.route('/cdata', methods=['GET', 'POST'])
def iclock_cdata():
    from attendance.adms import handle_iclock_cdata
    return handle_iclock_cdata()


@adms_bp.route('/getrequest', methods=['GET'])
def iclock_getrequest():
    from attendance.adms import handle_iclock_getrequest
    return handle_iclock_getrequest()


@adms_bp.route('/devicecmd', methods=['POST'])
def iclock_devicecmd():
    from attendance.adms import handle_iclock_devicecmd
    return handle_iclock_devicecmd()


@adms_bp.route('/registry', methods=['GET', 'POST'])
def iclock_registry():
    from attendance.adms import handle_iclock_registry
    return handle_iclock_registry()
