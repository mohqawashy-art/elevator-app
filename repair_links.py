"""
إصلاح روابط البيانات المستوردة.
تشغيل: python repair_links.py
"""

from app import app, db
from entity_links import active_contract_for_elevator, resolve_parts_links
from models import Fault, MaintenanceVisit, PartsBilling


def repair_visit_contracts():
    fixed = 0
    for v in MaintenanceVisit.query.all():
        if v.contract_id:
            continue
        c = active_contract_for_elevator(v.elevator_id, v.visit_date)
        if c:
            v.contract_id = c.id
            fixed += 1
    return fixed


def repair_parts_links():
    fixed = 0
    for p in PartsBilling.query.all():
        links = resolve_parts_links(
            customer_id=p.customer_id,
            contract_id=p.contract_id,
            elevator_id=p.elevator_id,
            technician_id=p.technician_id,
        )
        changed = False
        for key in ('customer_id', 'contract_id', 'elevator_id'):
            if not getattr(p, key) and links.get(key):
                setattr(p, key, links[key])
                changed = True
        if changed:
            fixed += 1
    return fixed


def migrate_fault_visits(dry_run=False):
    """تحويل زيارات نوع «عطل» إلى جدول faults (مرة واحدة)."""
    from app import next_code

    created = skipped = 0
    visits = MaintenanceVisit.query.filter(
        MaintenanceVisit.visit_type.contains('عطل')
    ).all()
    existing_codes = {f.code for f in Fault.query.all()}

    for v in visits:
        fcode = v.code.replace('VI-', 'FA-', 1) if v.code.startswith('VI-') else f'FA-{v.code}'
        if fcode in existing_codes:
            skipped += 1
            continue
        if dry_run:
            created += 1
            continue
        desc_parts = [x for x in (v.works_done, v.observations, v.notes) if x]
        f = Fault(
            code=fcode if not Fault.query.filter_by(code=fcode).first() else next_code(Fault, 'FA-', digits=5),
            elevator_id=v.elevator_id,
            technician_id=v.technician_id,
            fault_type=v.visit_type or 'عطل',
            description='\n'.join(desc_parts) or 'من سجل الزيارات',
            priority=v.priority or 'عادية',
            reported_at=v.visit_date,
            status='محلول' if v.status == 'مكتملة' else 'مفتوح',
            resolution=v.works_done or '',
            notes=v.notes or '',
        )
        db.session.add(f)
        existing_codes.add(f.code)
        created += 1
    return created, skipped


def main():
    with app.app_context():
        v = repair_visit_contracts()
        p = repair_parts_links()
        db.session.commit()
        print(f'زيارات: رُبط {v} عقداً')
        print(f'قطع غيار: أُصلح {p} سجل')
        created, skipped = migrate_fault_visits(dry_run=True)
        print(f'أعطال محتملة من الزيارات: {created} (تخطي {skipped}) — شغّل --migrate-faults لتنفيذ')


if __name__ == '__main__':
    import sys
    if '--migrate-faults' in sys.argv:
        with app.app_context():
            c, s = migrate_fault_visits(dry_run=False)
            db.session.commit()
            print(f'تم إنشاء {c} عطل، تخطي {s}')
    else:
        main()
