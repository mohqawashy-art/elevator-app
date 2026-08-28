"""اختبار قاعدة بيانات الأذكار JSON."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AZKAR_JSON = os.path.join(ROOT, 'static', 'data', 'azkar-duas.json')


def test_azkar_duas_json_loads():
    with open(AZKAR_JSON, encoding='utf-8') as f:
        data = json.load(f)
    assert data['version'] >= 1
    items = data['items']
    assert len(items) >= 10
    ids = [it['id'] for it in items]
    assert len(ids) == len(set(ids))
    for it in items:
        assert it.get('text')
        assert it.get('category') in ('dua', 'dhikr')
