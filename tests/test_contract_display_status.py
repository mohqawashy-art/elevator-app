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
