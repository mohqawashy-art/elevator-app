"""قالب مراحل التنفيذ بعد قبول عرض السعر."""

from datetime import datetime

STEP_STATUSES = ('قادم', 'جاري', 'مكتمل', 'متأخر', 'ملغي')

EXECUTION_STEP_TEMPLATES = [
    {
        'key': 'advance_payment',
        'group': 'عقد',
        'title': 'استلام الدفعة المقدمة من العميل',
        'hint': 'تُحسب من نسبة الدفعة المقدمة في العرض',
        'has_amount': True,
        'project_status': 'عقد',
    },
    {
        'key': 'contract_signed',
        'group': 'عقد',
        'title': 'توقيع العقد مع العميل',
        'hint': 'اعتماد العرض وربط الشروط',
        'project_status': 'عقد',
    },
    {
        'key': 'supplier_rfq',
        'group': 'توريد',
        'title': 'طلب عروض أسعار من الموردين',
        'hint': 'مقارنة الأسعار والمواصفات',
        'project_status': 'توريد',
    },
    {
        'key': 'supplier_selection',
        'group': 'توريد',
        'title': 'اختيار المورد واعتماد الأسعار',
        'project_status': 'توريد',
    },
    {
        'key': 'supply_permit',
        'group': 'توريد',
        'title': 'إصدار أذن التوريد',
        'hint': 'موافقة داخلية قبل الشراء',
        'project_status': 'توريد',
    },
    {
        'key': 'supplier_payment',
        'group': 'توريد',
        'title': 'دفع قيمة البضاعة للمورد',
        'has_amount': True,
        'project_status': 'توريد',
    },
    {
        'key': 'site_handover',
        'group': 'توريد',
        'title': 'استلام الموقع من العميل',
        'hint': 'تسليم البئر جاهزاً للتركيب',
        'project_status': 'توريد',
    },
    {
        'key': 'material_delivery',
        'group': 'توريد',
        'title': 'توريد المعدات للموقع',
        'hint': 'استلام وفحص البضاعة',
        'project_status': 'توريد',
    },
    {
        'key': 'payment_on_delivery',
        'group': 'توريد',
        'title': 'استلام دفعة التوريد من العميل',
        'hint': 'تُحسب من نسبة دفعة التوريد في العرض',
        'has_amount': True,
        'project_status': 'توريد',
    },
    {
        'key': 'phase1_rails',
        'group': 'تركيب',
        'title': 'المرحلة الأولى — تثبيت السكك والهيكل',
        'project_status': 'تركيب',
    },
    {
        'key': 'phase2_electrical',
        'group': 'تركيب',
        'title': 'المرحلة الثانية — الكهرباء والترافلينج',
        'project_status': 'تركيب',
    },
    {
        'key': 'phase3_machine',
        'group': 'تركيب',
        'title': 'المرحلة الثالثة — الماكينة والكبينة والأبواب',
        'project_status': 'تركيب',
    },
    {
        'key': 'commissioning',
        'group': 'تركيب',
        'title': 'التشغيل والاختبار والضبط',
        'project_status': 'تركيب',
    },
    {
        'key': 'client_delivery',
        'group': 'تسليم',
        'title': 'التسليم الرسمي للعميل',
        'project_status': 'تسليم',
    },
    {
        'key': 'payment_final',
        'group': 'تسليم',
        'title': 'استلام الدفعة النهائية',
        'hint': 'تُحسب من نسبة الدفعة النهائية في العرض',
        'has_amount': True,
        'project_status': 'تسليم',
    },
    {
        'key': 'warranty_start',
        'group': 'ضمان',
        'title': 'بدء فترة الضمان والصيانة المجانية',
        'project_status': 'ضمان',
    },
]

PAYMENT_STEP_KEYS = frozenset({'advance_payment', 'payment_on_delivery', 'payment_final'})


def is_client_payment_step(step_key):
    key = str(step_key or '')
    return key in PAYMENT_STEP_KEYS or key.startswith('client_payment_')


def step_template(step_key):
    found = next((t for t in EXECUTION_STEP_TEMPLATES if t['key'] == step_key), None)
    if found:
        return found
    if is_client_payment_step(step_key):
        return {
            'key': step_key,
            'group': 'توريد',
            'has_amount': True,
            'project_status': 'توريد',
        }
    return None


def step_has_auto_amount(step_key):
    return is_client_payment_step(step_key)


def step_amount_pct(step_key, quotation=None):
    """نسبة الدفعة من العرض المعتمد (0–100)."""
    if not quotation or not is_client_payment_step(step_key):
        return None
    for it in quotation.payment_items():
        if it.get('key') == step_key:
            return float(it['pct'])
    return None


def _pay_step_template(item, group, project_status):
    label = (item.get('label') or 'دفعة').strip() or 'دفعة'
    pct = float(item.get('pct') or 0)
    title = label if label.startswith('استلام') else f'استلام {label}'
    return {
        'key': item['key'],
        'group': group,
        'title': title,
        'hint': f'{pct:.0f}% من قيمة العقد',
        'has_amount': True,
        'project_status': project_status,
    }


def execution_step_templates_for(quotation=None):
    """قالب التنفيذ مع دفعات العميل كما حُددت في العرض."""
    items = quotation.payment_items() if quotation else []
    if not items:
        return list(EXECUTION_STEP_TEMPLATES)
    out = []
    for tpl in EXECUTION_STEP_TEMPLATES:
        key = tpl['key']
        if key == 'advance_payment':
            out.append(_pay_step_template(items[0], 'عقد', 'عقد'))
            continue
        if key == 'payment_on_delivery':
            middles = items[1:-1] if len(items) >= 2 else []
            for mid in middles:
                out.append(_pay_step_template(mid, 'توريد', 'توريد'))
            continue
        if key == 'payment_final':
            if len(items) >= 2:
                out.append(_pay_step_template(items[-1], 'تسليم', 'تسليم'))
            continue
        out.append(tpl)
    return out


def calculate_step_amount(grand_total, step_key, quotation=None):
    """مبلغ الخطوة من نسبة العقد المعتمد."""
    if not quotation or not grand_total:
        return None
    return quotation.payment_amount(step_key, grand_total)


def apply_auto_amount(step, quotation, force=False):
    """تعبئة مبلغ الخطوة تلقائياً من العرض المعتمد."""
    if not quotation or not quotation.grand_total:
        return False
    amount = quotation.payment_amount(step.step_key, quotation.grand_total)
    if amount is None:
        return False
    if force or not step.amount:
        step.amount = amount
        return True
    return False


def sync_payment_step_hints(project):
    """تحديث تلميحات خطوات الدفع من نسب العرض المعتمد."""
    accepted = project.accepted_quotation
    if not accepted:
        return 0
    hints = {}
    for it in accepted.payment_items():
        key = it.get('key')
        if key:
            hints[key] = f'{it["pct"]:.0f}% من قيمة العقد'
    updated = 0
    for step in project.timeline_steps:
        hint = hints.get(step.step_key)
        if hint and step.hint != hint:
            step.hint = hint
            updated += 1
    return updated


def sync_project_auto_amounts(project, force=False):
    """مزامنة مبالغ دفعات العميل — دائماً من الإجمالي شامل الضريبة."""
    accepted = project.accepted_quotation
    if not accepted or not accepted.grand_total:
        return 0
    updated = 0
    for step in project.timeline_steps:
        if not step_has_auto_amount(step.step_key):
            continue
        if step.status == 'مكتمل' and not force:
            continue
        if apply_auto_amount(step, accepted, force=True):
            updated += 1
    sync_payment_step_hints(project)
    return updated


def client_payment_amount(step, quotation):
    """مبلغ دفعة العميل — من العقد شامل الضريبة."""
    if not quotation or not quotation.grand_total:
        return step.amount or 0
    if step_has_auto_amount(step.step_key):
        return quotation.payment_amount(step.step_key, quotation.grand_total) or 0
    return step.amount or 0


def chain_step_dates_after_edit(project, edited_step):
    """بعد التعديل: بدء المرحلة التالية = تاريخ اكتمال الحالية."""
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    updated = 0
    for i, step in enumerate(steps):
        if step.id != edited_step.id:
            continue
        if step.completed_at and i + 1 < len(steps):
            nxt = steps[i + 1]
            if nxt.status in ('جاري', 'متأخر', 'مكتمل') and nxt.started_at != step.completed_at:
                nxt.started_at = step.completed_at
                updated += 1
        break
    return updated


def sync_timeline_from_templates(project):
    """مزامنة ترتيب ومرحلة الخطوات مع القالب (للمشاريع القائمة)."""
    by_key = {s.step_key: s for s in project.timeline_steps}
    updated = 0
    for i, tpl in enumerate(execution_step_templates_for(project.accepted_quotation)):
        step = by_key.get(tpl['key'])
        if not step:
            continue
        if step.sort_order != i:
            step.sort_order = i
            updated += 1
        if step.phase_group != tpl['group']:
            step.phase_group = tpl['group']
            updated += 1
        hint = tpl.get('hint') or ''
        if step.hint != hint:
            step.hint = hint
            updated += 1
    return updated


def create_execution_timeline(project, db_session):
    """إنشاء خطوات التنفيذ للمشروع إن لم تكن موجودة."""
    from installation.models import InstallTimelineStep

    existing = {s.step_key for s in project.timeline_steps}
    org_id = getattr(project, 'organization_id', None)
    quotation = project.accepted_quotation
    templates = execution_step_templates_for(quotation)
    created = 0
    for i, tpl in enumerate(templates):
        if tpl['key'] in existing:
            continue
        if is_client_payment_step(tpl['key']) and quotation:
            pct = step_amount_pct(tpl['key'], quotation)
            if pct is not None and float(pct) <= 0:
                continue
        db_step = InstallTimelineStep(
            organization_id=org_id,
            project_id=project.id,
            step_key=tpl['key'],
            title=tpl['title'],
            phase_group=tpl['group'],
            sort_order=i,
            status='قادم',
            hint=tpl.get('hint') or '',
            has_amount=bool(tpl.get('has_amount')),
        )
        db_session.add(db_step)
        project.timeline_steps.append(db_step)
        created += 1
    if created:
        db_session.flush()
    sync_timeline_from_templates(project)
    sync_project_auto_amounts(project, force=True)
    return created


def sync_project_status_from_timeline(project):
    """تحديث حالة المشروع حسب آخر مرحلة مكتملة."""
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    if not steps:
        return
    last_done = None
    for step in steps:
        if step.status == 'مكتمل':
            last_done = step
    if not last_done:
        return
    tpl = step_template(last_done.step_key)
    if tpl and tpl.get('project_status'):
        project.status = tpl['project_status']


def timeline_progress(steps):
    """نسبة الإنجاز."""
    if not steps:
        return 0
    done = sum(1 for s in steps if s.status == 'مكتمل')
    return int(round(100 * done / len(steps)))


def active_timeline_steps(steps):
    """الخطوات الظاهرة — تختفي المكتملة من الصفحة."""
    return [s for s in sorted(steps, key=lambda s: s.sort_order) if s.status != 'مكتمل']


def advance_next_step(project, completed_step):
    """بعد إكمال خطوة، تفعيل التالية تلقائياً."""
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    found = False
    phase_start = completed_step.completed_at or datetime.utcnow()
    for step in steps:
        if found and step.status == 'قادم':
            step.status = 'جاري'
            step.started_at = phase_start
            accepted = project.accepted_quotation
            if accepted and accepted.grand_total:
                apply_auto_amount(step, accepted, force=True)
            return step
        if step.id == completed_step.id:
            found = True
    return None


def sync_step_timeline_dates(project):
    """ربط تاريخ بدء كل مرحلة بتاريخ اكتمال السابقة (للمشاريع القديمة)."""
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    if not steps:
        return 0
    updated = 0
    cursor = project.execution_started_at
    for step in steps:
        if step.status in ('جاري', 'متأخر', 'مكتمل'):
            if not step.started_at:
                step.started_at = cursor or datetime.utcnow()
                updated += 1
        if step.status == 'مكتمل' and step.completed_at:
            cursor = step.completed_at
        elif step.started_at:
            cursor = step.started_at
    return updated


def chain_step_dates_after_edit(project, edited_step):
    """بعد التعديل: بدء المرحلة التالية = تاريخ اكتمال الحالية."""
    steps = sorted(project.timeline_steps, key=lambda s: s.sort_order)
    updated = 0
    for i, step in enumerate(steps):
        if step.id != edited_step.id:
            continue
        if step.completed_at and i + 1 < len(steps):
            nxt = steps[i + 1]
            if nxt.status in ('جاري', 'متأخر', 'مكتمل') and nxt.started_at != step.completed_at:
                nxt.started_at = step.completed_at
                updated += 1
        break
    return updated


def steps_by_group(steps):
    groups = []
    seen = {}
    for step in sorted(steps, key=lambda s: s.sort_order):
        if step.phase_group not in seen:
            seen[step.phase_group] = []
            groups.append((step.phase_group, seen[step.phase_group]))
        seen[step.phase_group].append(step)
    return [g for g in groups if g[1]]


def is_execution_complete(steps):
    if not steps:
        return False
    return all(s.status == 'مكتمل' for s in steps)


def project_is_closed(project) -> bool:
    status = (getattr(project, 'status', None) or '').strip()
    return status in ('مكتمل', 'مغلق')


def expected_project_end_date(project):
    """أبعد تاريخ مخطط/مكتمل في الخطوات — للمشاريع المفتوحة فقط."""
    dates = []
    for step in getattr(project, 'timeline_steps', None) or []:
        if step.planned_date:
            dates.append(step.planned_date)
        if step.completed_at:
            dates.append(step.completed_at.date() if hasattr(step.completed_at, 'date') else step.completed_at)
    return max(dates) if dates else None


def freeze_project_end_date(project):
    """تجميد تاريخ الانتهاء عند الإغلاق — لا يُحدَّث لاحقاً."""
    from datetime import date as _date

    if getattr(project, 'end_date', None):
        return project.end_date
    end = expected_project_end_date(project) or _date.today()
    project.end_date = end
    return end


def mark_project_completed(project):
    """عند اكتمال كل المراحل: حالة مكتمل + تجميد تاريخ الانتهاء."""
    freeze_project_end_date(project)
    project.status = 'مكتمل'
    return project


def project_end_date_label(project) -> str:
    """عرض تاريخ الانتهاء — عند الإغلاق يُكتب «مكتمل» ويتوقف التحديث."""
    if project_is_closed(project):
        return 'مكتمل'
    end = expected_project_end_date(project)
    return end.isoformat() if end else '—'


PHASE_ORDER = ('عقد', 'توريد', 'تركيب', 'تسليم', 'ضمان')


def phase_track(steps):
    """شريط المراحل العليا — منجز / جاري / قادم."""
    by_group = {}
    for step in steps:
        g = step.phase_group or '—'
        if g not in by_group:
            by_group[g] = {'total': 0, 'done': 0, 'active': False}
        by_group[g]['total'] += 1
        if step.status == 'مكتمل':
            by_group[g]['done'] += 1
        if step.status in ('جاري', 'متأخر'):
            by_group[g]['active'] = True
    track = []
    for name in PHASE_ORDER:
        info = by_group.get(name)
        if not info or not info['total']:
            continue
        if info['done'] == info['total']:
            state = 'done'
        elif info['active']:
            state = 'active'
        elif info['done'] > 0:
            state = 'partial'
        else:
            state = 'pending'
        track.append({
            'name': name,
            'state': state,
            'done': info['done'],
            'total': info['total'],
        })
    return track


def current_timeline_step(active_steps):
    """الخطوة التي يعمل عليها المستخدم الآن."""
    for step in active_steps:
        if step.status == 'جاري':
            return step
    for step in active_steps:
        if step.status == 'متأخر':
            return step
    return active_steps[0] if active_steps else None


def upcoming_timeline_steps(active_steps, current_step, limit=5):
    if not current_step:
        return []
    out = []
    passed = False
    for step in active_steps:
        if passed:
            out.append(step)
            if len(out) >= limit:
                break
        if step.id == current_step.id:
            passed = True
    return out


def payment_totals(steps, quotation=None):
    supplier_keys = {'supplier_payment'}
    client_paid = 0.0
    supplier_paid = 0.0
    client_due = 0.0
    for step in steps:
        if quotation and is_client_payment_step(step.step_key):
            client_due += client_payment_amount(step, quotation)
        if step.status != 'مكتمل':
            continue
        if is_client_payment_step(step.step_key):
            client_paid += client_payment_amount(step, quotation)
        elif step.step_key in supplier_keys and step.amount:
            supplier_paid += step.amount
    return {
        'client_paid': client_paid,
        'supplier_paid': supplier_paid,
        'client_due': client_due,
    }
