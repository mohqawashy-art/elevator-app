"""أسماء المباني في تسلسل العقود."""
from types import SimpleNamespace

from app import _contract_building_names, _elevator_building_display, contract_to_js_dict


def test_contract_building_names_unique_joined():
    c = SimpleNamespace(
        elevators=[
            SimpleNamespace(elevator_id=1),
            SimpleNamespace(elevator_id=2),
            SimpleNamespace(elevator_id=3),
        ]
    )
    elevator_by_id = {
        1: SimpleNamespace(building_name='برج النور'),
        2: SimpleNamespace(building_name='برج النور'),
        3: SimpleNamespace(building_name='فيلا السلام'),
    }
    assert _contract_building_names(c, elevator_by_id=elevator_by_id) == 'برج النور، فيلا السلام'


def test_contract_to_js_dict_includes_buildings():
    c = SimpleNamespace(
        id=10,
        code='CN-00001',
        customer_id=1,
        customer=SimpleNamespace(name='عميل', name_en='', city='', lat='', lng='', status='نشط'),
        contract_type='صيانة',
        start_date=None,
        end_date=None,
        duration_months=12,
        elevators=[SimpleNamespace(elevator_id=5)],
        maint_frequency='',
        visits_per_month=1,
        value=1000,
        tax_pct=15,
        tax_amount=150,
        total=1150,
        payment_terms='',
        paid_amount=0,
        invoice_status='غير مدفوع',
        status='نشط',
        reminder_date=None,
        due_date=None,
        city='',
        district='',
        address='',
        notes='',
        file_path=None,
    )
    row = contract_to_js_dict(
        c,
        renewed_ids=set(),
        elevator_by_id={5: SimpleNamespace(building_name='مجمع الأندلس')},
    )
    assert row['buildings'] == 'مجمع الأندلس'


def test_elevator_building_display_strips_code_suffix():
    elev = SimpleNamespace(building_name='حمدي حمدان — EL-0054', code='EL-0054')
    assert _elevator_building_display(elev) == 'حمدي حمدان'


def test_elevator_building_display_skips_code_only():
    elev = SimpleNamespace(building_name='EL-0054', code='EL-0054')
    assert _elevator_building_display(elev) == ''


def test_contract_building_names_without_elevator_codes():
    c = SimpleNamespace(
        elevators=[
            SimpleNamespace(elevator_id=1),
            SimpleNamespace(elevator_id=2),
        ]
    )
    elevator_by_id = {
        1: SimpleNamespace(building_name='برج النور — EL-0001', code='EL-0001'),
        2: SimpleNamespace(building_name='برج النور — EL-0002', code='EL-0002'),
    }
    assert _contract_building_names(c, elevator_by_id=elevator_by_id) == 'برج النور'
