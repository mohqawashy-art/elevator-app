"""خيار بدون في مواصفات عرض السعر."""
from installation.catalog import (
    NONE_OPTION,
    is_none_option,
    origin_label,
    origin_label_from_spec,
)


def test_is_none_option():
    assert is_none_option(NONE_OPTION)
    assert is_none_option('بدون')
    assert not is_none_option('chinese')
    assert not is_none_option('')
    assert not is_none_option(None)


def test_origin_label_hides_none():
    assert origin_label(NONE_OPTION) == ''
    assert origin_label_from_spec({'machine_origin': NONE_OPTION}) == ''
    assert origin_label_from_spec({'machine_origin': 'chinese'}) == 'صيني'
