"""اختبار تقرير قطع الغيار."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from report_data import REPORT_FETCHERS


def test_report_parts_in_registry():
    assert 'report-parts' in REPORT_FETCHERS
    assert callable(REPORT_FETCHERS['report-parts'])
