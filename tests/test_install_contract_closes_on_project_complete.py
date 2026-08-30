"""عقد التركيب ينتهي بتسليم الأعمال — لا مدة صيانة تقويمية."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from installation.timeline import close_linked_install_contract, mark_project_completed


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return self._row


def test_create_install_contract_has_no_maintenance_duration():
    from sales.service import create_install_contract_from_quotation

    project = SimpleNamespace(contract_id=None, customer_id=7)
    quotation = SimpleNamespace(
        code='IQ-1',
        quote_type='new',
        customer_id=7,
        grand_total=115000,
        subtotal=100000,
        tax_amount=15000,
    )
    fake_contract = SimpleNamespace()
    ContractMock = MagicMock(return_value=fake_contract)

    with patch('sales.service.Contract', ContractMock), patch(
        'sales.service.assign_organization'
    ), patch('sales.service.db') as db:
        db.session.add.side_effect = lambda _o: None
        db.session.flush.side_effect = lambda: setattr(fake_contract, 'id', 99)
        result = create_install_contract_from_quotation(
            project, quotation, next_code_fn=lambda *_a, **_k: 'CI-00001',
        )

    assert result is fake_contract
    kwargs = ContractMock.call_args.kwargs
    assert kwargs['contract_type'] == 'عقد تركيب'
    assert kwargs['start_date'] == kwargs['end_date']
    assert kwargs['duration_months'] is None
    assert kwargs.get('reminder_date') is None
    assert 'تسليم' in (kwargs['notes'] or '')
    assert project.contract_id == 99


def test_create_upgrade_quote_makes_modernization_contract():
    from sales.service import create_install_contract_from_quotation

    project = SimpleNamespace(contract_id=None, customer_id=7)
    quotation = SimpleNamespace(
        code='IQ-2',
        quote_type='upgrade',
        customer_id=7,
        grand_total=23000,
        subtotal=20000,
        tax_amount=3000,
    )
    fake_contract = SimpleNamespace()
    with patch('sales.service.Contract', MagicMock(return_value=fake_contract)), patch(
        'sales.service.assign_organization'
    ), patch('sales.service.db') as db:
        db.session.add.side_effect = lambda _o: None
        db.session.flush.side_effect = lambda: setattr(fake_contract, 'id', 5)
        create_install_contract_from_quotation(
            project, quotation, next_code_fn=lambda *_a, **_k: 'CI-00002',
        )
        from sales.service import Contract as C  # patched already used
    # re-read last call via MagicMock on sales.service.Contract — need capture
    # Assert via project link only if kwargs not available; re-run with capture:

    ContractMock = MagicMock(return_value=fake_contract)
    with patch('sales.service.Contract', ContractMock), patch(
        'sales.service.assign_organization'
    ), patch('sales.service.db') as db:
        db.session.add.side_effect = lambda _o: None
        db.session.flush.side_effect = lambda: setattr(fake_contract, 'id', 5)
        create_install_contract_from_quotation(
            project, quotation, next_code_fn=lambda *_a, **_k: 'CI-00002',
        )
    assert ContractMock.call_args.kwargs['contract_type'] == 'عقد تحديث'


def test_close_linked_install_contract_sets_work_duration():
    start = date(2026, 1, 10)
    end = date(2026, 4, 20)
    contract = SimpleNamespace(
        id=1,
        contract_type='عقد تركيب',
        start_date=start,
        end_date=start,
        duration_months=None,
        status='نشط',
        reminder_date=date(2026, 12, 1),
        notes='من عرض',
    )
    project = SimpleNamespace(
        contract_id=1,
        code='IP-1',
        end_date=end,
        start_date=start,
        status='جاري',
    )
    with patch(
        'tenant_scope.tenant_query',
        return_value=_FakeQuery(contract),
    ):
        closed = close_linked_install_contract(project)

    assert closed is contract
    assert contract.status == 'منتهي'
    assert contract.end_date == end
    assert contract.duration_months == 3
    assert contract.reminder_date is None
    assert 'أُغلق بتسليم' in contract.notes


def test_mark_project_completed_closes_contract():
    project = SimpleNamespace(
        contract_id=None,
        end_date=None,
        status='تركيب',
        timeline_steps=[],
    )
    with patch(
        'installation.timeline.close_linked_install_contract'
    ) as close_fn, patch(
        'installation.timeline.freeze_project_end_date',
        return_value=date.today(),
    ):
        mark_project_completed(project)
    assert project.status == 'مكتمل'
    close_fn.assert_called_once_with(project)
