"""LiftCore — مزامنة فورية بين جلسات الموظفين (polling + revision)."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from flask import url_for
from sqlalchemy import event

from models import (
    AppLiveState,
    Contract,
    Customer,
    Elevator,
    Expense,
    Fault,
    InventoryItem,
    Invoice,
    MaintenanceVisit,
    PartsBilling,
    Revenue,
    StockMovement,
    Technician,
    db,
)

PAGE_ALIASES = {
    '': 'dashboard',
    'dashboard': 'dashboard',
    'clients': 'clients',
    'contracts': 'contracts',
    'elevators': 'elevators',
    'technicians': 'technicians',
    'maintenance-visits': 'maintenance-visits',
    'faults': 'faults',
    'parts-billing': 'parts-billing',
    'inventory': 'inventory',
    'stock-movements': 'stock-movements',
    'revenues': 'revenues',
    'expenses': 'expenses',
    'invoices': 'invoices',
    'purchase-orders': 'purchase-orders',
    'elevator-estimates': 'elevator-estimates',
    'reports': 'reports',
}


def _helpers():
    import app as app_module
    return app_module


def ensure_live_state():
    row = AppLiveState.query.get(1)
    if row is None:
        db.session.add(AppLiveState(id=1, revision=0))
        db.session.commit()


def get_live_revision():
    row = AppLiveState.query.get(1)
    return int(row.revision if row else 0)


def resolve_page_key(path: str) -> str | None:
    path = (path or '/').split('?')[0].rstrip('/') or '/'
    if path == '/':
        return 'dashboard'
    for skip in ('/login', '/print', '/report', '/field', 'visit-report', 'fault-report'):
        if skip in path:
            return None
    slug = path.lstrip('/').split('/')[0]
    return PAGE_ALIASES.get(slug)


def register_live_sync():
    @event.listens_for(db.session, 'before_flush')
    def _live_before_flush(session, flush_context, instances):
        changed = False
        for obj in list(session.new) + list(session.dirty) + list(session.deleted):
            if isinstance(obj, AppLiveState):
                continue
            changed = True
            break
        if not changed:
            return
        state = session.get(AppLiveState, 1)
        if state is None:
            session.add(AppLiveState(id=1, revision=1))
        else:
            state.revision = int(state.revision or 0) + 1


def build_sync_payload(page_key: str):
    builders = {
        'dashboard': _sync_dashboard,
        'clients': _sync_clients,
        'contracts': _sync_contracts,
        'elevators': _sync_elevators,
        'technicians': _sync_technicians,
        'maintenance-visits': _sync_maintenance_visits,
        'faults': _sync_faults,
        'parts-billing': _sync_parts_billing,
        'inventory': _sync_inventory,
        'stock-movements': _sync_stock_movements,
        'revenues': _sync_revenues,
        'expenses': _sync_expenses,
        'invoices': _sync_invoices,
        'elevator-estimates': _sync_elevator_estimates,
    }
    fn = builders.get(page_key)
    if not fn:
        return None
    return fn()


def _sync_dashboard():
    h = _helpers()
    stats, _alerts = h.get_dashboard_stats()
    return {'STATS': stats}


def _sync_clients():
    h = _helpers()
    customers = Customer.query.order_by(Customer.id.desc()).all()
    rows = []
    for c in customers:
        rows.append({
            'id': c.id,
            'code': c.code,
            'name': c.name,
            'name_en': c.name_en or '',
            'city': c.city or '',
            'district': c.district or '',
            'phone': c.phone or '',
            'phone2': c.phone2 or '',
            'email': c.email or '',
            'contact': c.contact_person or '',
            'role': c.contact_role or '',
            'entity_type': c.entity_type or 'فرد',
            'national_id': c.national_id or '',
            'cr_number': c.cr_number or '',
            'elevators': len(c.elevators),
            'fleet_status': h.customer_fleet_status(c),
            'contracts': len(c.contracts),
            'contract_status': (
                h.contract_display_status(
                    c.contracts[0],
                    renewed_ids=h._annotate_contract_renewals(list(c.contracts or [])),
                ) if c.contracts else 'بدون عقد'
            ),
            'status': c.status,
            'notes': c.notes or '',
            'address': c.address or '',
            'lat': c.lat or '',
            'lng': c.lng or '',
            'maps_url': c.maps_url or '',
            'building_photo_url': h.upload_url(c.building_photo_path),
        })
    return {'CUSTOMERS': rows}


def _sync_contracts():
    h = _helpers()
    contracts = Contract.query.order_by(Contract.id.desc()).all()
    renewed_ids = h._annotate_contract_renewals(contracts)
    customers = Customer.query.order_by(Customer.name).all()
    all_elevators = Elevator.query.all()
    elevator_by_id = {e.id: e for e in all_elevators}
    elev_lookup = {
        e.id: {'code': e.code, 'building': e.building_name or '', 'customer_id': e.customer_id}
        for e in all_elevators
    }
    rows = []
    for c in contracts:
        row = h.contract_to_js_dict(c, renewed_ids=renewed_ids, elevator_by_id=elevator_by_id)
        rows.append(row)
    cust_rows = [{
        'id': c.id,
        'name': c.name,
        'code': c.code,
        'city': c.city or '',
        'district': c.district or '',
        'address': c.address or '',
        'phone': c.phone or '',
        'contact_person': c.contact_person or '',
        'lat': c.lat or '',
        'lng': c.lng or '',
        'maps_url': c.maps_url or '',
        'building_photo_url': h.upload_url(c.building_photo_path),
    } for c in customers]
    return {'CONTRACTS': rows, 'CUSTOMERS': cust_rows, 'ELEVATOR_LOOKUP': elev_lookup}


def _sync_elevators():
    h = _helpers()
    elevs = Elevator.query.order_by(Elevator.id.desc()).all()
    customers = Customer.query.order_by(Customer.name).all()
    rows = []
    for e in elevs:
        rows.append({
            'id': e.id,
            'code': e.code,
            'customer_id': e.customer_id,
            'customer': e.customer.name if e.customer else '',
            'customer_name_en': (e.customer.name_en or '') if e.customer else '',
            'building': e.building_name or '',
            'city': e.city or '',
            'district': e.district or '',
            'elev_type': e.elev_type or '',
            'brand': e.brand or '',
            'model': e.model or '',
            'capacity': e.capacity_kg or 0,
            'capacity_persons': e.capacity_persons or 0,
            'floors': e.floors or 0,
            'stops': e.stops or 0,
            'doors': e.doors_count or 0,
            'speed': e.speed or '',
            'serial': e.serial_number or '',
            'machine_type': e.machine_type or '',
            'door_type': e.door_type or '',
            'control_type': e.control_type or '',
            'control_drive': e.control_drive or '',
            'control_operation': e.control_operation or '',
            'control_detail': e.control_detail or '',
            'install_date': e.install_date.isoformat() if e.install_date else '',
            'warranty_end': e.warranty_end.isoformat() if e.warranty_end else '',
            'last_maint': e.last_maintenance.isoformat() if e.last_maintenance else '',
            'next_maint': e.next_maintenance.isoformat() if e.next_maintenance else '',
            'maint_freq': e.maint_frequency or '',
            'address': e.address or '',
            'status': e.status,
            'notes': e.notes or '',
            'customer_lat': (e.customer.lat or '') if e.customer else '',
            'customer_lng': (e.customer.lng or '') if e.customer else '',
        })
    cust_rows = [{
        'id': c.id,
        'code': c.code,
        'name': c.name,
        'city': c.city or '',
        'district': c.district or '',
        'lat': c.lat or '',
        'lng': c.lng or '',
    } for c in customers]
    return {'ELEVATORS': rows, 'CUSTOMERS': cust_rows}


def _sync_technicians():
    h = _helpers()
    techs = Technician.query.order_by(Technician.id.desc()).all()
    rows = []
    for t in techs:
        docs = []
        for d in t.documents:
            fname = d.file_name or ''
            low = fname.lower()
            docs.append({
                'id': d.id,
                'doc_type': d.doc_type or '',
                'title': d.title or d.file_name or '',
                'file_name': fname,
                'url': url_for('static', filename=d.file_path) if d.file_path else '',
                'is_image': low.endswith(('.png', '.jpg', '.jpeg', '.webp')),
                'is_pdf': low.endswith('.pdf'),
                'uploaded_at': d.uploaded_at.strftime('%Y-%m-%d') if d.uploaded_at else '',
            })
        rows.append({
            'id': t.id,
            'code': t.code,
            'name': t.name,
            'name_en': t.name_en or '',
            'phone': t.phone or '',
            'phone2': t.phone2 or '',
            'job_title': t.job_title or '',
            'specialization': t.specialization or '',
            'team': t.team or 'عام',
            'city': t.city or '',
            'national_id': t.national_id or '',
            'hire_date': t.hire_date.isoformat() if t.hire_date else '',
            'salary': t.salary or 0,
            'emergency': t.emergency,
            'status': t.status or 'متاح',
            'display_status': h.technician_display_status(t),
            'visits': len(t.visits),
            'faults': len(t.faults),
            'notes': t.notes or '',
            'photo_url': h.upload_url(t.photo_path) if t.photo_path else '',
            'signature_url': h.upload_url(t.signature_path) if t.signature_path else '',
            'has_sign_pin': bool(t.sign_pin_hash),
            'documents': len(t.documents),
            'docs': docs,
        })
    unassigned = Fault.query.filter(
        Fault.technician_id.is_(None),
        Fault.status.in_(['مفتوح', 'قيد المعالجة']),
    ).count()
    return {'TECHNICIANS': rows, 'UNASSIGNED_FAULTS': unassigned}


def _sync_maintenance_visits():
    h = _helpers()
    from operations import is_fault_visit_type

    visits = [
        v for v in MaintenanceVisit.query.order_by(MaintenanceVisit.visit_date.desc()).all()
        if not is_fault_visit_type(v.visit_type)
    ]
    elevators = Elevator.query.all()
    customers = Customer.query.order_by(Customer.name).all()
    contracts = Contract.query.order_by(Contract.start_date.desc()).all()
    technicians = Technician.query.filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).all()
    return {
        'VISITS': h._visits_js_list(visits),
        'CUSTOMERS': [{'id': c.id, 'code': c.code, 'name': c.name} for c in customers],
        'ELEVATORS': [{
            'id': e.id, 'code': e.code, 'customer_id': e.customer_id,
            'customer': e.customer.name if e.customer else '',
        } for e in elevators],
        'CONTRACTS': [{'id': c.id, 'code': c.code, 'customer_id': c.customer_id} for c in contracts],
        'TECHNICIANS': [{'id': t.id, 'name': t.name} for t in technicians],
        'VISIT_MAP_POINTS': h._visit_map_points(visits),
    }


def _sync_faults():
    h = _helpers()
    faults = Fault.query.order_by(Fault.reported_at.desc()).all()
    elevators = Elevator.query.all()
    customers = Customer.query.order_by(Customer.name).all()
    inventory_items = InventoryItem.query.order_by(InventoryItem.name).all()
    technicians = Technician.query.filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).all()
    return {
        'FAULTS': h._faults_js_list(faults),
        'CUSTOMERS': [{
            'id': c.id, 'code': c.code, 'name': c.name,
            'city': c.city or '', 'district': c.district or '',
            'contact_person': c.contact_person or '', 'phone': c.phone or '',
            'building_photo_url': h._static_upload_url(c.building_photo_path) or '',
        } for c in customers],
        'ELEVATORS': [{
            'id': e.id, 'code': e.code, 'customer_id': e.customer_id,
            'customer': e.customer.name if e.customer else '',
            'building_name': e.building_name or '',
            'city': e.city or '', 'district': e.district or '',
        } for e in elevators],
        'TECHNICIANS': [{'id': t.id, 'name': t.name} for t in technicians],
        'INVENTORY_ITEMS': [{
            'id': i.id, 'code': i.code, 'name': i.name,
            'unit': i.unit or 'قطعة', 'buy_price': i.buy_price or 0,
            'sell_price': i.sell_price or 0,
        } for i in inventory_items],
    }


def _sync_parts_billing():
    h = _helpers()
    parts = PartsBilling.query.order_by(PartsBilling.billing_date.desc()).all()
    customers = Customer.query.order_by(Customer.name).all()
    contracts = Contract.query.order_by(Contract.code).all()
    return {
        'PARTS': h._parts_js_list(parts),
        'CUSTOMERS': [{'id': c.id, 'code': c.code, 'name': c.name} for c in customers],
        'CONTRACTS': [{'id': c.id, 'code': c.code, 'customer_id': c.customer_id} for c in contracts],
    }


def _sync_inventory():
    items = InventoryItem.query.order_by(InventoryItem.id.desc()).all()
    return {
        'ITEMS': [{
            'id': i.id,
            'code': i.code or '',
            'name': i.name or '',
            'category': i.category or '',
            'unit': i.unit or 'قطعة',
            'current_qty': float(i.current_qty or 0),
            'min_qty': float(i.min_qty or 0),
            'buy_price': float(i.buy_price or 0),
            'sell_price': float(i.sell_price or 0),
            'stock_value': float(i.stock_value or 0),
            'order_status': i.order_status,
            'supplier': i.supplier or '',
            'location': i.location or '',
            'notes': i.notes or '',
        } for i in items],
    }


def _sync_stock_movements():
    movements = StockMovement.query.order_by(StockMovement.movement_date.desc()).all()
    items = InventoryItem.query.all()
    technicians = Technician.query.filter(Technician.status.in_(['نشط', 'متاح', 'مشغول'])).all()
    return {
        'MOVEMENTS': [{
            'id': m.id,
            'code': m.code,
            'item_id': m.item_id,
            'item_name': m.item.name if m.item else '',
            'item_code': m.item.code if m.item else '',
            'movement_date': str(m.movement_date or ''),
            'direction': m.direction,
            'movement_type': m.movement_type or '',
            'quantity': m.quantity or 0,
            'unit_price': m.unit_price or 0,
            'total_value': m.total_value or 0,
            'technician': m.technician.name if m.technician else '—',
            'tech_id': m.technician_id,
            'reason': m.reason or '',
            'notes': m.notes or '',
        } for m in movements],
        'ITEMS': [{
            'id': i.id, 'code': i.code, 'name': i.name,
            'unit': i.unit or 'قطعة', 'buy_price': i.buy_price or 0,
        } for i in items],
        'TECHNICIANS': [{'id': t.id, 'name': t.name} for t in technicians],
    }


def _sync_revenues():
    revs = Revenue.query.order_by(Revenue.revenue_date.desc()).all()
    customers = Customer.query.all()
    return {
        'REVENUES': [{
            'id': r.id,
            'code': r.code,
            'customer_id': r.customer_id,
            'contract_id': r.contract_id,
            'customer': r.customer.name if r.customer else '—',
            'contract': r.contract.code if r.contract else '—',
            'revenue_date': str(r.revenue_date or ''),
            'revenue_type': r.revenue_type or '',
            'pay_method': r.payment_method or '',
            'amount': r.amount or 0,
            'tax_amount': r.tax_amount or 0,
            'total': r.total or 0,
            'status': r.status or 'محصّل',
            'reference': r.reference or '',
            'notes': r.notes or '',
            'created_by': (getattr(r, 'created_by_name', None) or '—'),
        } for r in revs],
        'CUSTOMERS': [{'id': c.id, 'name': c.name, 'code': c.code} for c in customers],
    }


def _sync_expenses():
    expenses = Expense.query.order_by(Expense.expense_date.desc()).all()
    return {
        'EXPENSES': [{
            'id': e.id,
            'code': e.code,
            'expense_date': str(e.expense_date or ''),
            'expense_type': e.expense_type or '',
            'description': e.description or '',
            'responsible': e.responsible or '',
            'pay_method': e.payment_method or '',
            'amount': e.amount or 0,
            'reference': e.reference or '',
            'notes': e.notes or '',
            'created_by': (getattr(e, 'created_by_name', None) or '—'),
        } for e in expenses],
    }


def _sync_invoices():
    invoices = Invoice.query.order_by(Invoice.id.desc()).all()
    customers = Customer.query.all()
    return {
        'INVOICES': [{
            'id': i.id,
            'code': i.code,
            'invoice_type': i.invoice_type or 'فاتورة',
            'customer_id': i.customer_id,
            'contract_id': i.contract_id,
            'customer': i.customer.name if i.customer else '—',
            'customer_name_en': (i.customer.name_en or '') if i.customer else '',
            'contract': i.contract.code if i.contract else '—',
            'invoice_date': str(i.invoice_date or ''),
            'due_date': str(i.due_date or ''),
            'description': i.description or '',
            'amount': i.amount or 0,
            'tax_amount': i.tax_amount or 0,
            'total': i.total or 0,
            'pay_method': i.payment_method or '',
            'status': i.status or 'غير مدفوعة',
            'notes': i.notes or '',
        } for i in invoices],
        'CUSTOMERS': [{'id': c.id, 'name': c.name, 'code': c.code} for c in customers],
    }


def _sync_elevator_estimates():
    customers = Customer.query.order_by(Customer.name).all()
    return {
        'EST_CUSTOMERS': [{'id': c.id, 'name': c.name, 'code': c.code} for c in customers],
    }
