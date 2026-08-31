"""اختبارات إجماليات الإيرادات المشتركة."""
from report_data import summarize_revenue_rows


def test_summarize_revenue_rows_totals():
    rows = [
        {'total': 1000, 'status': 'محصّل'},
        {'total': 500, 'status': 'معلق'},
        {'total': 3900, 'status': 'ملغي'},
    ]
    s = summarize_revenue_rows(rows)
    assert s['total'] == 5400.0
    assert s['collected'] == 1000.0
    assert s['pending'] == 500.0
    assert s['cancelled'] == 3900.0
    assert s['count'] == 3
    assert s['cancelled_count'] == 1


def test_summarize_revenue_rows_status_aliases():
    rows = [
        {'total': 200, 'status': 'محصل'},
        {'total': 300, 'status': 'غير محصّل'},
    ]
    s = summarize_revenue_rows(rows)
    assert s['collected'] == 200.0
    assert s['pending'] == 300.0
