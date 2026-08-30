"""فلاتر الجداول تدعم اختيار أكثر من قيمة في البند الواحد."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD = os.path.join(ROOT, 'templates', 'partials', 'liftcore_head.html')
JS = os.path.join(ROOT, 'static', 'liftcore-filter-multi.js')
CSS = os.path.join(ROOT, 'static', 'liftcore-filter-multi.css')
CONTRACTS = os.path.join(ROOT, 'templates', 'contracts.html')


def test_filter_multi_static_exists():
    assert os.path.isfile(JS)
    assert os.path.isfile(CSS)


def test_filter_multi_linked_from_head():
    text = open(HEAD, encoding='utf-8').read()
    assert 'liftcore-filter-multi.css' in text
    assert 'liftcore-filter-multi.js' in text


def test_filter_multi_api():
    js = open(JS, encoding='utf-8').read()
    assert 'function allows(' in js
    assert 'global.LiftCoreFilter' in js
    assert 'global.lcAllows' in js
    assert 'lc-filter-multi-btn' in js


def test_contracts_status_uses_multi_allow():
    text = open(CONTRACTS, encoding='utf-8').read()
    assert "lcAllows('f-status'" in text
    assert 'getContractDisplayStatus(c) === st' not in text


def test_list_pages_use_multi_allow():
    pages = [
        'templates/clients.html',
        'templates/elevators.html',
        'templates/faults.html',
        'templates/revenues.html',
        'templates/invoices.html',
        'templates/technicians.html',
        'templates/maintenance-visits.html',
        'templates/expenses.html',
        'templates/inventory.html',
        'templates/stock-movements.html',
        'templates/parts-billing.html',
    ]
    for rel in pages:
        text = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        assert 'lcAllows(' in text, rel
