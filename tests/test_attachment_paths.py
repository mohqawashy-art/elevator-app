"""تخزين وقراءة مسارات المرفقات المتعددة."""
from attachment_paths import (
    attachment_has,
    attachment_items,
    parse_attachment_paths,
    serialize_attachment_paths,
)


def test_parse_single_path():
    assert parse_attachment_paths('uploads/foo.pdf') == ['uploads/foo.pdf']


def test_parse_json_multi():
    raw = 'JSON:["uploads/a.pdf","uploads/b.pdf"]'
    assert parse_attachment_paths(raw) == ['uploads/a.pdf', 'uploads/b.pdf']


def test_serialize_single_and_multi():
    assert serialize_attachment_paths(['uploads/one.pdf']) == 'uploads/one.pdf'
    multi = serialize_attachment_paths(['uploads/a.pdf', 'uploads/b.pdf'])
    assert multi.startswith('JSON:')
    assert parse_attachment_paths(multi) == ['uploads/a.pdf', 'uploads/b.pdf']


def test_attachment_items_indices():
    items = attachment_items(
        serialize_attachment_paths(['uploads/a.pdf', 'uploads/b.pdf']),
        lambda p: '/static/' + p,
        name_fn=lambda p: p.split('/')[-1],
    )
    assert len(items) == 2
    assert items[0]['index'] == 0
    assert items[1]['index'] == 1
    assert items[0]['url'] == '/static/uploads/a.pdf'


def test_attachment_has_empty():
    assert not attachment_has(None)
    assert not attachment_has('')
