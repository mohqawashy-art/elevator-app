"""دعم واتساب التشغيلي — وارد المكتب + رحلة حالة على نفس كود البلاغ."""
from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy import or_

from models import Customer, Elevator, Fault, Settings, WhatsAppInbox, db
from operations import whatsapp_url
from tenant_scope import assign_organization, tenant_query

DEFAULT_OFFICE_WHATSAPP = '0555076078'
INBOX_OPEN = frozenset({'جديد', 'مربوط'})

JOURNEY_STAGES = (
    'received',
    'assigned',
    'on_way',
    'parts_needed',
    'resolved',
)
JOURNEY_LABELS = {
    'received': 'استلام البلاغ',
    'assigned': 'تعيين فني',
    'on_way': 'الفني في الطريق',
    'parts_needed': 'انتظار قطع غيار',
    'resolved': 'تم الإصلاح',
}
RESOLVED_STATUSES = frozenset({'تم الاصلاح', 'تم الإصلاح', 'مغلق', 'محلول'})
PARTS_STATUSES = frozenset({'انتظار قطع'})


def ensure_whatsapp_settings(settings: Settings) -> Settings:
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


def _digits_only(phone: str) -> str:
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('00'):
        digits = digits[2:]
    return digits


def _looks_saudi_local(digits: str) -> bool:
    if digits.startswith('966'):
        return True
    if digits.startswith('05') and len(digits) == 10:
        return True
    if len(digits) == 9 and digits.startswith('5'):
        return True
    return False


def phone_key(phone: str) -> str:
    """مفتاح مطابقة: سعودي = آخر 9 محلي؛ دولي = الرقم الدولي كاملاً."""
    digits = _digits_only(phone)
    if not digits:
        return ''
    if digits.startswith('966'):
        local = digits[3:]
        if local.startswith('0'):
            local = local[1:]
        return local[-9:] if len(local) >= 9 else local
    if _looks_saudi_local(digits):
        local = digits[1:] if digits.startswith('0') else digits
        return local[-9:] if len(local) >= 9 else local
    return digits


def display_phone(phone: str) -> str:
    """عرض/تخزين: سعودي كـ 05…؛ دولي كـ +كود الدولة بدون تحويل لسعودي."""
    raw = (phone or '').strip()
    digits = _digits_only(raw)
    if not digits:
        return raw
    if digits.startswith('966'):
        local = digits[3:]
        if local.startswith('0'):
            local = local[1:]
        return ('0' + local) if local and not local.startswith('0') else local
    if _looks_saudi_local(digits):
        if digits.startswith('0'):
            return digits
        return '0' + digits
    # دولي: احتفظ بـ + والكود كما أدخله المستخدم
    return '+' + digits


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


def thread_query():
    """بلاغات الوارد فقط — كل بلاغ بكود واحد."""
    return tenant_query(WhatsAppInbox).filter(
        or_(
            WhatsAppInbox.direction == 'inbound',
            WhatsAppInbox.direction.is_(None),
            WhatsAppInbox.direction == '',
        )
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
        journey_json='[]',
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
        notes=f'استُقبل عبر واتساب {item.code} — بانتظار توزيع المكتب على الفني',
        reported_at=item.received_at or datetime.utcnow(),
    )
    assign_organization(fault)
    db.session.add(fault)
    db.session.flush()
    item.fault_id = fault.id
    item.customer_id = item.customer_id or elev.customer_id
    item.status = 'تم إنشاء عطل'
    item.direction = 'inbound'
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


def resolution_summary_for_fault(fault: Fault, *, max_len: int = 280) -> str:
    """ملخص إصلاح من العطل/التقرير لرسالة انتهاء العميل."""
    parts: list[str] = []
    resolution = (fault.resolution or '').strip()
    if resolution:
        parts.append(resolution)
    tech_notes = (fault.tech_notes or '').strip()
    if tech_notes:
        first = tech_notes.split('\n\n')[0].strip()
        if first and first not in parts and first != resolution:
            parts.append(first)
    if not parts and (fault.report_json or '').strip():
        from fault_report import parse_fault_report_json

        meta = parse_fault_report_json(fault.report_json).get('meta') or {}
        for key in ('action_taken', 'diagnosis', 'final_notes'):
            val = (meta.get(key) or '').strip()
            if val:
                parts.append(val)
                break
    text = ' — '.join(parts)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_len:
        return text[: max_len - 1] + '…'
    return text


def fault_report_print_path(fault: Fault) -> str:
    return f'/faults/{fault.id}/report?print=1'


def build_customer_journey_message(
    fault: Fault,
    stage: str,
    *,
    thread_code: str = '',
    report_url: str = '',
) -> str:
    stage = (stage or '').strip()
    if stage not in JOURNEY_STAGES:
        raise ValueError('مرحلة غير معروفة')
    elev = fault.elevator
    cust = elev.customer if elev else None
    cust_name = (fault.reporter_name or (cust.name if cust else '') or 'عميلنا الكريم').strip()
    elev_code = elev.code if elev else '—'
    tech_name = fault.technician.name if fault.technician else 'الفني المختص'
    track = fault.code
    ref = f' (مرجع الوارد {thread_code})' if thread_code else ''

    if stage == 'received':
        return (
            f'مرحباً {cust_name}\n'
            f'تم استلام بلاغكم بنجاح.\n'
            f'رقم المتابعة: {track}{ref}\n'
            f'المصعد: {elev_code}\n'
            f'المكتب يستلم البلاغ الآن وسيتم تحويله للفني قريباً.\n'
            f'شكراً لتواصلكم.'
        )
    if stage == 'assigned':
        return (
            f'مرحباً {cust_name}\n'
            f'بلاغكم {track} قيد المعالجة.\n'
            f'تم تعيين الفني: {tech_name}\n'
            f'المصعد: {elev_code}\n'
            f'سنتواصل عند التوجه للموقع.'
        )
    if stage == 'on_way':
        return (
            f'مرحباً {cust_name}\n'
            f'الفني {tech_name} في الطريق إليكم الآن.\n'
            f'بلاغ: {track} · المصعد: {elev_code}\n'
            f'نعتذر عن أي إزعاج ونقدّر تعاونكم.'
        )
    if stage == 'parts_needed':
        return (
            f'مرحباً {cust_name}\n'
            f'بلاغكم {track} يحتاج قطع غيار لإكمال الإصلاح.\n'
            f'المصعد: {elev_code}\n'
            f'الفني: {tech_name}\n'
            f'نعمل على توفير القطع وسنُعلمكم فور استئناف العمل.\n'
            f'شكراً لصبركم.'
        )
    summary = resolution_summary_for_fault(fault)
    lines = [
        f'مرحباً {cust_name}',
        f'تم الانتهاء من بلاغكم {track}.',
        f'المصعد: {elev_code}',
        f'الفني: {tech_name}',
    ]
    if summary:
        lines.append(f'ملخص الإصلاح: {summary}')
    pdf = (report_url or '').strip()
    if pdf:
        lines.append(f'تقرير الإصلاح (PDF): {pdf}')
    else:
        lines.append('تقرير الإصلاح (PDF) جاهز لدى المكتب — سيُرفق مع الرسالة عند الإرسال.')
    lines.extend([
        'نأمل أن يكون كل شيء على ما يرام.',
        'تقييمكم يهمنا: ردّوا برقم من 1 إلى 5 ⭐',
        'شكراً لثقتكم.',
    ])
    return '\n'.join(lines)


def _load_journey(thread: WhatsAppInbox) -> list[dict]:
    raw = (thread.journey_json or '').strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _save_journey(thread: WhatsAppInbox, entries: list[dict]) -> None:
    thread.journey_json = json.dumps(entries, ensure_ascii=False)


def journey_has_stage(thread: WhatsAppInbox, stage: str) -> bool:
    return any((e or {}).get('stage') == stage for e in _load_journey(thread))


def find_thread_for_fault(fault_id: int) -> WhatsAppInbox | None:
    return (
        thread_query()
        .filter(WhatsAppInbox.fault_id == fault_id)
        .order_by(WhatsAppInbox.id.asc())
        .first()
    )


def ensure_thread_for_fault(fault: Fault, *, next_code_fn) -> WhatsAppInbox:
    thread = find_thread_for_fault(fault.id)
    if thread:
        return thread
    phone = customer_phone_for_fault(fault) or '0000000000'
    elev = fault.elevator
    thread = WhatsAppInbox(
        code=next_code_fn(WhatsAppInbox, 'WA-', digits=5),
        direction='inbound',
        from_phone=phone,
        from_name=(fault.reporter_name or (elev.customer.name if elev and elev.customer else ''))[:120],
        body=fault.client_report or fault.description or f'بلاغ مرتبط بـ {fault.code}',
        status='تم إنشاء عطل',
        stage='inbound',
        receive_target='office',
        customer_id=elev.customer_id if elev else None,
        elevator_id=fault.elevator_id,
        fault_id=fault.id,
        received_at=fault.reported_at or datetime.utcnow(),
        journey_json='[]',
        notes=f'خيط متابعة للعطل {fault.code}',
    )
    assign_organization(thread)
    db.session.add(thread)
    db.session.flush()
    return thread


def already_notified(fault_id: int, stage: str) -> bool:
    thread = find_thread_for_fault(fault_id)
    if thread and journey_has_stage(thread, stage):
        return True
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
    report_url: str = '',
) -> dict:
    """رسالة حالة على نفس كود الوارد — بدون WA جديد لكل مرحلة."""
    stage = (stage or '').strip()
    if stage not in JOURNEY_STAGES:
        return {'ok': False, 'error': 'مرحلة غير معروفة', 'url': ''}
    phone = customer_phone_for_fault(fault)
    if not phone:
        return {'ok': False, 'error': 'لا يوجد جوال للعميل/المبلّغ', 'url': ''}

    thread = ensure_thread_for_fault(fault, next_code_fn=next_code_fn)
    pdf = (report_url or '').strip()
    if stage == 'resolved' and not pdf:
        pdf = fault_report_print_path(fault)
    msg = build_customer_journey_message(
        fault, stage, thread_code=thread.code, report_url=pdf,
    )
    url = whatsapp_url(phone, msg)

    if not force and journey_has_stage(thread, stage):
        pending = False
        for e in _load_journey(thread):
            if (e or {}).get('stage') == stage:
                url = (e or {}).get('url') or url
                pending = bool((e or {}).get('pending_send'))
                break
        return {
            'ok': True,
            'skipped': True,
            'pending_send': pending,
            'url': url,
            'stage': stage,
            'label': JOURNEY_LABELS[stage],
            'thread_code': thread.code,
            'fault_code': fault.code,
            'log_id': thread.id,
            'report_url': pdf if stage == 'resolved' else '',
        }

    entries = _load_journey(thread)
    if force:
        entries = [e for e in entries if (e or {}).get('stage') != stage]
    entries.append({
        'stage': stage,
        'label': JOURNEY_LABELS.get(stage, stage),
        'body': msg,
        'url': url,
        'pending_send': True,
        'report_url': pdf if stage == 'resolved' else '',
        'at': datetime.utcnow().isoformat(sep=' ', timespec='seconds'),
    })
    _save_journey(thread, entries)
    thread.stage = stage
    if stage == 'resolved':
        thread.status = 'جاهز للإرسال'
    elif thread.status in ('جديد', 'مربوط'):
        thread.status = 'تم إنشاء عطل'
    db.session.add(thread)
    db.session.flush()
    return {
        'ok': True,
        'skipped': False,
        'pending_send': True,
        'url': url,
        'stage': stage,
        'label': JOURNEY_LABELS[stage],
        'thread_code': thread.code,
        'fault_code': fault.code,
        'log_id': thread.id,
        'report_url': pdf if stage == 'resolved' else '',
    }


def pending_customer_sends(*, limit: int = 30) -> list[dict]:
    """رسائل جاهزة ينتظر المكتب فتح wa.me وإرسالها."""
    rows = (
        thread_query()
        .order_by(WhatsAppInbox.id.desc())
        .limit(200)
        .all()
    )
    out: list[dict] = []
    for thread in rows:
        for entry in reversed(_load_journey(thread)):
            if not (entry or {}).get('pending_send'):
                continue
            url = (entry or {}).get('url') or ''
            if not url:
                continue
            fault = thread.fault
            out.append({
                'thread_id': thread.id,
                'thread_code': thread.code,
                'fault_id': thread.fault_id,
                'fault_code': fault.code if fault else '',
                'stage': entry.get('stage') or '',
                'label': entry.get('label') or JOURNEY_LABELS.get(entry.get('stage') or '', ''),
                'url': url,
                'from_phone': thread.from_phone or '',
                'from_name': thread.from_name or '',
                'at': entry.get('at') or '',
            })
            break
        if len(out) >= limit:
            break
    return out


def ack_pending_send(thread_id: int, *, stage: str | None = None) -> WhatsAppInbox | None:
    thread = thread_query().filter(WhatsAppInbox.id == thread_id).first()
    if not thread:
        return None
    entries = _load_journey(thread)
    changed = False
    for entry in entries:
        if not (entry or {}).get('pending_send'):
            continue
        if stage and entry.get('stage') != stage:
            continue
        entry['pending_send'] = False
        changed = True
        if stage:
            break
    if changed:
        _save_journey(thread, entries)
        if not any((e or {}).get('pending_send') for e in entries):
            if thread.stage == 'resolved' or thread.status == 'جاهز للإرسال':
                thread.status = 'مغلق'
        db.session.add(thread)
    return thread


def auto_stage_for_fault_status(
    old_status: str | None,
    new_status: str | None,
    *,
    had_tech: bool,
    has_tech: bool,
) -> str | None:
    new_status = (new_status or '').strip()
    old = (old_status or '').strip()
    if new_status in RESOLVED_STATUSES and old not in RESOLVED_STATUSES:
        return 'resolved'
    if new_status in PARTS_STATUSES and old not in PARTS_STATUSES:
        return 'parts_needed'
    if has_tech and not had_tech:
        return 'assigned'
    if new_status == 'قيد المعالجة' and old == 'مفتوح' and has_tech:
        return 'assigned'
    return None


def suggested_next_stage(fault: Fault, entries: list[dict] | None = None) -> str | None:
    """أقرب رسالة يجب تجهيزها حسب حالة العطل ومراحل الرحلة."""
    done = {(e or {}).get('stage') for e in (entries or []) if (e or {}).get('stage')}
    status = (fault.status or '').strip()
    has_tech = bool(fault.technician_id)
    if 'received' not in done:
        return 'received'
    if has_tech and 'assigned' not in done:
        return 'assigned'
    if has_tech and status == 'قيد المعالجة' and 'on_way' not in done:
        return 'on_way'
    if status in PARTS_STATUSES and 'parts_needed' not in done:
        return 'parts_needed'
    if status in RESOLVED_STATUSES and 'resolved' not in done:
        return 'resolved'
    return None


def journey_snapshots_for_faults(faults: list[Fault]) -> dict[int, dict]:
    """لقطة متابعة واتساب لكل عطل — للعرض بجانب الصف."""
    if not faults:
        return {}
    ids = [f.id for f in faults if f and f.id]
    if not ids:
        return {}
    threads = (
        thread_query()
        .filter(WhatsAppInbox.fault_id.in_(ids))
        .order_by(WhatsAppInbox.id.asc())
        .all()
    )
    by_fault: dict[int, WhatsAppInbox] = {}
    for t in threads:
        if t.fault_id and t.fault_id not in by_fault:
            by_fault[t.fault_id] = t

    out: dict[int, dict] = {}
    for fault in faults:
        thread = by_fault.get(fault.id)
        entries = _load_journey(thread) if thread else []
        pending = None
        for e in reversed(entries):
            if (e or {}).get('pending_send') and (e or {}).get('url'):
                pending = e
                break
        current = entries[-1] if entries else None
        next_stage = suggested_next_stage(fault, entries)
        # إن وُجد إرسال معلّق فهو الحالة الحالية للعمل
        display = pending or current
        out[fault.id] = {
            'thread_id': thread.id if thread else None,
            'thread_code': thread.code if thread else '',
            'current_stage': (display or {}).get('stage') or '',
            'current_label': (display or {}).get('label')
                or JOURNEY_LABELS.get((display or {}).get('stage') or '', '')
                or 'بدون رسالة',
            'current_preview': '',
            'pending_send': bool(pending),
            'pending_url': (pending or {}).get('url') or '',
            'pending_stage': (pending or {}).get('stage') or '',
            'pending_label': (pending or {}).get('label')
                or JOURNEY_LABELS.get((pending or {}).get('stage') or '', ''),
            'stages_done': [],
            'next_stage': next_stage,
            'next_label': JOURNEY_LABELS.get(next_stage or '', ''),
            'report_print_url': fault_report_print_path(fault),
            'show_pdf': (display or {}).get('stage') == 'resolved' or status_is_resolved(fault),
        }
    return out


def status_is_resolved(fault: Fault) -> bool:
    return (fault.status or '').strip() in RESOLVED_STATUSES


def ack_whatsapp_url(item: WhatsAppInbox, fault: Fault | None = None) -> str:
    fault = fault or (tenant_query(Fault).filter_by(id=item.fault_id).first() if item.fault_id else None)
    if fault:
        try:
            return whatsapp_url(
                item.from_phone or customer_phone_for_fault(fault),
                build_customer_journey_message(fault, 'received', thread_code=item.code),
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
    rows = thread_query().all()
    return {
        'total': len(rows),
        'new': sum(1 for r in rows if r.status == 'جديد'),
        'linked': sum(1 for r in rows if r.status == 'مربوط'),
        'faulted': sum(1 for r in rows if r.status == 'تم إنشاء عطل'),
        'ready_send': sum(1 for r in rows if r.status == 'جاهز للإرسال'),
        'open': sum(1 for r in rows if r.status in INBOX_OPEN),
    }


def parse_journey_for_template(item: WhatsAppInbox) -> list[dict]:
    return _load_journey(item)
