from elevator_estimate_calc import calculate_lines, summarize_lines


def test_estimate_totals_are_whole_riyals():
    lines = calculate_lines({
        'machine_type': 'MR',
        'elev_type': 'مصعد ركاب',
        'floors': 5,
        'stops': 5,
        'capacity_kg': 630,
        'doors_count': 5,
        'include_installation': '1',
        'include_install_materials': '1',
        'include_shaft_work': '0',
    })
    assert lines
    for ln in lines:
        assert ln['quantity'] == round(ln['quantity'])
        assert ln['unit_price'] == round(ln['unit_price'])
        assert ln['line_total'] == round(ln['line_total'])

    totals = summarize_lines(lines, margin_pct=12.5, vat_pct=15)
    for key in ('cost_subtotal', 'margin_amount', 'subtotal', 'vat_amount', 'total'):
        assert totals[key] == round(totals[key])
