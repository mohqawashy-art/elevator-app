from inventory_units import format_inventory_qty, normalize_inventory_qty, unit_allows_decimals


def test_piece_unit_is_integer_only():
    assert unit_allows_decimals('قطعة') is False
    assert normalize_inventory_qty(5, 'قطعة') == 5.0
    assert format_inventory_qty(5.0, 'قطعة') == '5'
    try:
        normalize_inventory_qty(1.5, 'قطعة')
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert 'لا تقبل كسور' in str(exc)


def test_liter_unit_allows_decimals():
    assert unit_allows_decimals('لتر') is True
    assert normalize_inventory_qty(2.5, 'لتر') == 2.5
    assert format_inventory_qty(2.5, 'لتر') == '2.5'


def test_format_strips_trailing_zero_for_decimal_unit():
    assert format_inventory_qty(4.0, 'متر') == '4'


def test_qty_field_allows_zero():
    from inventory_units import normalize_inventory_qty_field

    assert normalize_inventory_qty_field(0, 'قطعة') == 0.0
    assert normalize_inventory_qty_field(3, 'قطعة') == 3.0
