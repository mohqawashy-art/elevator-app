"""دعم واتساب التشغيلي — المرحلة 1: وارد المكتب ثم التوزيع."""
from __future__ import annotations

import re
from datetime import datetime

from models import Customer, Elevator, Fault, Settings, WhatsAppInbox, db
from operations import whatsapp_url
from tenant_scope import assign_organization, tenant_query

DEFAULT_OFFICE_WHATSAPP = '0555076078'
INBOX_OPEN = frozenset({'جديد', 'مربوط'})


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


def ack_whatsapp_url(item: WhatsAppInbox, fault: Fault | None = None) -> str:
    fault = fault or (tenant_query(Fault).filter_by(id=item.fault_id).first() if item.fault_id else None)
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
