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


def step_template(step_key):
    return next((t for t in EXECUTION_STEP_TEMPLATES if t['key'] == step_key), None)


def step_has_auto_amount(step_key):
    return step_key in PAYMENT_STEP_KEYS


def step_amount_pct(step_key, quotation=None):
    """نسبة الدفعة من العرض المعتمد (0–100)."""
    if step_key not in PAYMENT_STEP_KEYS or not quotation:
        return None
    sched = quotation.payment_schedule()
    key_map = {
        'advance_payment': sched['advance_pct'],
        'payment_on_delivery': sched['supply_pct'],
        'payment_final': sched['final_pct'],
    }
    return key_map.get(step_key)


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
    sched = accepted.payment_schedule()
    hints = {
        'advance_payment': f'{sched["advance_pct"]:.0f}% من قيمة العقد',
        'payment_on_delivery': f'{sched["supply_pct"]:.0f}% من قيمة العقد بعد التوريد',
        'payment_final': f'{sched["final_pct"]:.0f}% من قيمة العقد عند التسليم',
    }
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
    for i, tpl in enumerate(EXECUTION_STEP_TEMPLATES):
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
    created = 0
    for i, tpl in enumerate(EXECUTION_STEP_TEMPLATES):
        if tpl['key'] in existing:
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
    tpl = next((t for t in EXECUTION_STEP_TEMPLATES if t['key'] == last_done.step_key), None)
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
    client_keys = {'advance_payment', 'payment_on_delivery', 'payment_final'}
    supplier_keys = {'supplier_payment'}
    client_paid = 0.0
    supplier_paid = 0.0
    client_due = 0.0
    for step in steps:
        if step.step_key in client_keys and quotation and step_has_auto_amount(step.step_key):
            client_due += client_payment_amount(step, quotation)
        if step.status != 'مكتمل':
            continue
        if step.step_key in client_keys:
            client_paid += client_payment_amount(step, quotation)
        elif step.step_key in supplier_keys and step.amount:
            supplier_paid += step.amount
    return {
        'client_paid': client_paid,
        'supplier_paid': supplier_paid,
        'client_due': client_due,
    }
