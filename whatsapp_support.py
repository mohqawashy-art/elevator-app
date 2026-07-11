"""دعم واتساب التشغيلي — المرحلة 1: وارد المكتب ثم التوزيع."""
from __future__ import annotations

import re
from datetime import datetime

from models import Customer, Elevator, Fault, Settings, WhatsAppInbox, db
from operations import whatsapp_url
from tenant_scope import assign_organization, tenant_query

DEFAULT_OFFICE_WHATSAPP = '0555076078'
INBOX_OPEN = frozenset({'جديد', 'مربوط'})

# المرحلة 2 — رحلة حالة العميل
JOURNEY_STAGES = (
    'received',
    'assigned',
    'on_way',
    'resolved',
)
JOURNEY_LABELS = {
    'received': 'تأكيد الاستلام',
    'assigned': 'تعيين فني',
    'on_way': 'في الطريق',
    'resolved': 'تم الإصلاح',
}
RESOLVED_STATUSES = frozenset({'تم الاصلاح', 'تم الإصلاح', 'مغلق', 'محلول'})


def ensure_whatsapp_settings(settings: Settings) -> Settings:
    """ضمان رقم الاستقبال ووضع المكتب."""
    changed = False
    if not (settings.whatsapp_phone or '').strip():
        settings.whatsapp_phone = DEFAULT_OFFICE_WHATSAPP
        changed = True
    if not (settings.whatsapp_receive_mode or '').strip():
        settings.whatsapp_receive_mode = 'office'
        changed = True
    if changed:
        db.session.add(settings)
    return settings


def phone_key(phone: str) -> str:
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('966'):
        digits = digits[3:]
    if digits.startswith('0'):
        digits = digits[1:]
    return digits[-9:] if len(digits) >= 9 else digits


def display_phone(phone: str) -> str:
    key = phone_key(phone)
    if not key:
        return (phone or '').strip()
    return '0' + key if not key.startswith('0') else key


def find_customer_by_phone(phone: str) -> Customer | None:
    key = phone_key(phone)
    if not key:
        return None
    for cust in tenant_query(Customer).all():
        for p in (cust.phone, cust.phone2):
            if p and phone_key(p) == key:
                return cust
    return None


def customer_elevators(customer_id: int) -> list[Elevator]:
    return (
        tenant_query(Elevator)
        .filter_by(customer_id=customer_id)
        .order_by(Elevator.id.asc())
        .all()
    )


def intake_inbound(
    *,
    from_phone: str,
    body: str,
    from_name: str = '',
    media_url: str = '',
    wa_message_id: str = '',
    next_code_fn,
) -> WhatsAppInbox:
    phone = display_phone(from_phone)
    if not phone_key(phone):
        raise ValueError('رقم الجوال مطلوب')
    if wa_message_id:
        existing = tenant_query(WhatsAppInbox).filter_by(wa_message_id=wa_message_id).first()
        if existing:
            return existing

    customer = find_customer_by_phone(phone)
    elevators = customer_elevators(customer.id) if customer else []
    elevator = elevators[0] if len(elevators) == 1 else None
    status = 'مربوط' if customer else 'جديد'

    item = WhatsAppInbox(
        code=next_code_fn(WhatsAppInbox, 'WA-', digits=5),
        direction='inbound',
        from_phone=phone,
        from_name=(from_name or (customer.name if customer else '') or '').strip()[:120],
        body=(body or '').strip(),
        media_url=(media_url or '').strip()[:500] or None,
        status=status,
        stage='inbound',
        receive_target='office',
        customer_id=customer.id if customer else None,
        elevator_id=elevator.id if elevator else None,
        wa_message_id=(wa_message_id or '').strip()[:120] or None,
        received_at=datetime.utcnow(),
    )
    assign_organization(item)
    db.session.add(item)
    db.session.flush()
    return item


def link_inbox_item(
    item: WhatsAppInbox,
    *,
    customer_id: int | None,
    elevator_id: int | None,
) -> WhatsAppInbox:
    if customer_id:
        cust = tenant_query(Customer).filter_by(id=customer_id).first()
        if not cust:
            raise ValueError('العميل غير موجود')
        item.customer_id = cust.id
        if not item.from_name:
            item.from_name = cust.name
    if elevator_id:
        elev = tenant_query(Elevator).filter_by(id=elevator_id).first()
        if not elev:
            raise ValueError('المصعد غير موجود')
        if item.customer_id and elev.customer_id != item.customer_id:
            raise ValueError('المصعد لا يتبع هذا العميل')
        item.elevator_id = elev.id
        item.customer_id = elev.customer_id
    if item.customer_id and item.elevator_id and item.status in INBOX_OPEN:
        item.status = 'مربوط'
    elif item.customer_id and item.status == 'جديد':
        item.status = 'مربوط'
    return item


def create_fault_from_inbox(item: WhatsAppInbox, *, next_code_fn, priority: str = 'عاجلة') -> Fault:
    if item.fault_id:
        fault = tenant_query(Fault).filter_by(id=item.fault_id).first()
        if fault:
            return fault
    if not item.elevator_id:
        raise ValueError('اختر المصعد قبل إنشاء العطل')
    elev = tenant_query(Elevator).filter_by(id=item.elevator_id).first()
    if not elev:
        raise ValueError('المصعد غير موجود')

    report = (item.body or '').strip() or 'بلاغ واتساب'
    fault = Fault(
        code=next_code_fn(Fault, 'FA-', digits=5),
        elevator_id=elev.id,
        fault_type='بلاغ واتساب',
        description=report,
        client_report=report,
        reporter_name=item.from_name or (item.customer.name if item.customer else ''),
        reporter_phone=item.from_phone,
        priority=priority or 'عاجلة',
        status='مفتوح',
        notes='استُقبل عبر واتساب — بانتظار توزيع المكتب على الفني',
        reported_at=item.received_at or datetime.utcnow(),
    )
    assign_organization(fault)
    db.session.add(fault)
    db.session.flush()
    item.fault_id = fault.id
    item.customer_id = item.customer_id or elev.customer_id
    item.status = 'تم إنشاء عطل'
    return fault


def customer_phone_for_fault(fault: Fault) -> str:
    if fault.reporter_phone and phone_key(fault.reporter_phone):
        return display_phone(fault.reporter_phone)
    elev = fault.elevator
    cust = elev.customer if elev else None
    if cust:
        for p in (cust.phone2, cust.phone):
            if p and phone_key(p):
                return display_phone(p)
    return ''


def build_customer_journey_message(fault: Fault, stage: str) -> str:
    stage = (stage or '').strip()
    if stage not in JOURNEY_STAGES:
        raise ValueError('مرحلة غير معروفة')
    elev = fault.elevator
    cust = elev.customer if elev else None
    cust_name = (fault.reporter_name or (cust.name if cust else '') or 'عميلنا الكريم').strip()
    elev_code = elev.code if elev else '—'
    tech_name = fault.technician.name if fault.technician else 'الفني المختص'
    code = fault.code

    if stage == 'received':
        return (
            f'مرحباً {cust_name}\n'
            f'تم استلام بلاغكم بنجاح.\n'
            f'رقم المتابعة: {code}\n'
            f'المصعد: {elev_code}\n'
            f'المكتب يستلم البلاغ الآن وسيتم تحويله للفني قريباً.\n'
            f'شكراً لتواصلكم.'
        )
    if stage == 'assigned':
        return (
            f'مرحباً {cust_name}\n'
            f'بلاغكم {code} قيد المعالجة.\n'
            f'تم تعيين الفني: {tech_name}\n'
            f'المصعد: {elev_code}\n'
            f'سنتواصل عند التوجه للموقع.'
        )
    if stage == 'on_way':
        return (
            f'مرحباً {cust_name}\n'
            f'الفني {tech_name} في الطريق إليكم الآن.\n'
            f'بلاغ: {code} · المصعد: {elev_code}\n'
            f'نعتذر عن أي إزعاج ونقدّر تعاونكم.'
        )
    return (
        f'مرحباً {cust_name}\n'
        f'تم الانتهاء من بلاغكم {code}.\n'
        f'المصعد: {elev_code}\n'
        f'نأمل أن يكون كل شيء على ما يرام.\n'
        f'تقييمكم يهمنا: ردّوا برقم من 1 إلى 5 ⭐\n'
        f'شكراً لثقتكم.'
    )


def already_notified(fault_id: int, stage: str) -> bool:
    return (
        tenant_query(WhatsAppInbox)
        .filter_by(fault_id=fault_id, direction='outbound', stage=stage)
        .first()
        is not None
    )


def notify_customer_stage(
    fault: Fault,
    stage: str,
    *,
    next_code_fn,
    force: bool = False,
) -> dict:
    """يبني رسالة حالة للعميل ويسجّلها صادرة. يفتح wa.me حتى تفعيل Cloud API."""
    stage = (stage or '').strip()
    if stage not in JOURNEY_STAGES:
        return {'ok': False, 'error': 'مرحلة غير معروفة', 'url': ''}
    phone = customer_phone_for_fault(fault)
    if not phone:
        return {'ok': False, 'error': 'لا يوجد جوال للعميل/المبلّغ', 'url': ''}
    if not force and already_notified(fault.id, stage):
        existing = (
            tenant_query(WhatsAppInbox)
            .filter_by(fault_id=fault.id, direction='outbound', stage=stage)
            .order_by(WhatsAppInbox.id.desc())
            .first()
        )
        msg = build_customer_journey_message(fault, stage)
        return {
            'ok': True,
            'skipped': True,
            'url': whatsapp_url(phone, msg),
            'stage': stage,
            'label': JOURNEY_LABELS[stage],
            'log_id': existing.id if existing else None,
        }

    msg = build_customer_journey_message(fault, stage)
    elev = fault.elevator
    log = WhatsAppInbox(
        code=next_code_fn(WhatsAppInbox, 'WA-', digits=5),
        direction='outbound',
        from_phone=phone,
        from_name=(fault.reporter_name or (elev.customer.name if elev and elev.customer else ''))[:120],
        body=msg,
        status='مُرسل',
        stage=stage,
        receive_target='customer',
        customer_id=elev.customer_id if elev else None,
        elevator_id=fault.elevator_id,
        fault_id=fault.id,
        received_at=datetime.utcnow(),
        notes=f'رحلة حالة — {JOURNEY_LABELS.get(stage, stage)}',
    )
    assign_organization(log)
    db.session.add(log)
    db.session.flush()
    return {
        'ok': True,
        'skipped': False,
        'url': whatsapp_url(phone, msg),
        'stage': stage,
        'label': JOURNEY_LABELS[stage],
        'log_id': log.id,
    }


def auto_stage_for_fault_status(old_status: str | None, new_status: str | None, *, had_tech: bool, has_tech: bool) -> str | None:
    """يقترح مرحلة إشعار عند تغيّر العطل."""
    new_status = (new_status or '').strip()
    if new_status in RESOLVED_STATUSES and (old_status or '') not in RESOLVED_STATUSES:
        return 'resolved'
    if has_tech and not had_tech:
        return 'assigned'
    if new_status == 'قيد المعالجة' and (old_status or '') == 'مفتوح' and has_tech:
        return 'assigned'
    return None


def ack_whatsapp_url(item: WhatsAppInbox, fault: Fault | None = None) -> str:
    fault = fault or (tenant_query(Fault).filter_by(id=item.fault_id).first() if item.fault_id else None)
    if fault:
        try:
            return whatsapp_url(
                item.from_phone or customer_phone_for_fault(fault),
                build_customer_journey_message(fault, 'received'),
            )
        except ValueError:
            pass
    code = fault.code if fault else item.code
    msg = (
        f'تم استلام بلاغكم بنجاح.\n'
        f'رقم المتابعة: {code}\n'
        f'المكتب يستلم البلاغ الآن وسيتم تحويله للفني المختص قريباً.\n'
        f'شكراً لتواصلكم.'
    )
    return whatsapp_url(item.from_phone, msg)


def inbox_stats() -> dict:
    rows = tenant_query(WhatsAppInbox).all()
    return {
        'total': len(rows),
        'new': sum(1 for r in rows if r.status == 'جديد'),
        'linked': sum(1 for r in rows if r.status == 'مربوط'),
        'faulted': sum(1 for r in rows if r.status == 'تم إنشاء عطل'),
        'open': sum(1 for r in rows if r.status in INBOX_OPEN),
    }
