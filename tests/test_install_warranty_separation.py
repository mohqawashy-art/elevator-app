"""اختبارات فصل التركيب عن الصيانة وتحويل الضمان."""
from types import SimpleNamespace

from installation.warranty import (
    should_create_warranty,
    work_phases_complete,
    warranty_start_completed,
)


def _step(group, status='مكتمل', key='x'):
    return SimpleNamespace(phase_group=group, status=status, step_key=key)


def test_work_phases_complete_requires_three_groups():
    steps = [
        _step('عقد'),
        _step('توريد'),
        _step('تركيب'),
        _step('تسليم', status='جاري'),
    ]
    assert not work_phases_complete(steps)
    steps[-1].status = 'مكتمل'
    assert work_phases_complete(steps)


def test_warranty_start_completed():
    steps = [_step('ضمان', status='جاري', key='warranty_start')]
    assert not warranty_start_completed(steps)
    steps[0].status = 'مكتمل'
    assert warranty_start_completed(steps)


def test_should_create_warranty_skips_if_already_linked():
    project = SimpleNamespace(
        warranty_contract_id=99,
        timeline_steps=[
            _step('توريد'),
            _step('تركيب'),
            _step('تسليم'),
        ],
    )
    assert not should_create_warranty(project)


def test_customer_matches_scope_includes_install_projects():
    from contract_codes import customer_matches_scope

    cust = SimpleNamespace(
        contracts=[],
        installation_projects=[SimpleNamespace(id=1)],
        installation_leads=[],
    )
    assert customer_matches_scope(cust, 'installation')
    assert not customer_matches_scope(cust, 'maintenance')

    maint = SimpleNamespace(
        contracts=[SimpleNamespace(contract_type='عقد صيانة')],
        installation_projects=[],
        installation_leads=[],
    )
    assert customer_matches_scope(maint, 'maintenance')
    assert not customer_matches_scope(maint, 'installation')
