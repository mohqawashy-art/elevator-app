"""حالة عرض العقد بعد التجديد."""
from datetime import date, timedelta
from types import SimpleNamespace

from app import contract_display_status


def test_expired_without_renewal_is_expired():
    c = SimpleNamespace(
        id=1,
        status='منتهي',
        end_date=date.today() - timedelta(days=10),
    )
    assert contract_display_status(c, renewed_ids=set()) == 'منتهي'


def test_expired_with_renewal_is_renewed():
    c = SimpleNamespace(
        id=1,
        status='منتهي',
        end_date=date.today() - timedelta(days=10),
    )
    assert contract_display_status(c, renewed_ids={1}) == 'تم تجديده'


def test_explicit_renewed_status():
    c = SimpleNamespace(id=2, status='تم تجديده', end_date=date.today() - timedelta(days=5))
    assert contract_display_status(c, renewed_ids=set()) == 'تم تجديده'


def test_active_not_overridden_by_empty_renewed():
    c = SimpleNamespace(id=3, status='نشط', end_date=date.today() + timedelta(days=100))
    assert contract_display_status(c, renewed_ids=set()) == 'نشط'


def test_expiring_requires_end_date_within_30_days():
    c = SimpleNamespace(id=4, status='على وشك الانتهاء', end_date=None)
    assert contract_display_status(c, renewed_ids=set()) == 'نشط'


def test_expiring_from_end_date_even_if_status_active():
    c = SimpleNamespace(id=5, status='نشط', end_date=date.today() + timedelta(days=10))
    assert contract_display_status(c, renewed_ids=set()) == 'على وشك الانتهاء'


def test_install_contract_excluded_from_expiring_alert(client):
    from datetime import date as date_cls

    from app import _contracts_expiring_display_status, db
    from contract_codes import CONTRACT_PREFIX_INSTALLATION
    from models import Contract, Customer, Organization
    from tests.conftest import login_as

    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        cust = Customer(
            organization_id=org.id,
            code='C-EXP1',
            name='عميل تنبيه',
            status='نشط',
        )
        db.session.add(cust)
        db.session.flush()
        install = Contract(
            organization_id=org.id,
            code=f'{CONTRACT_PREFIX_INSTALLATION}99999',
            customer_id=cust.id,
            contract_type='عقد تركيب',
            status='على وشك الانتهاء',
            start_date=date_cls.today(),
            end_date=date_cls.today() + timedelta(days=10),
        )
        maint = Contract(
            organization_id=org.id,
            code='CN-99998',
            customer_id=cust.id,
            contract_type='عقد صيانة',
            status='نشط',
            start_date=date_cls.today(),
            end_date=date_cls.today() + timedelta(days=15),
        )
        db.session.add_all([install, maint])
        db.session.commit()
        expiring = _contracts_expiring_display_status()
        codes = {c.code for c in expiring}
        assert install.code not in codes
        assert maint.code in codes
