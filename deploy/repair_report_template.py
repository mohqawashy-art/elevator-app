#!/usr/bin/env python3
"""إصلاح قالب تقرير واحد مع الحفاظ على UTF-8."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates"

LOADING_ROW = '<tr><td colspan="20" style="text-align:center;padding:24px;color:var(--text3)">جاري تحميل البيانات...</td></tr>'

BOOT_SNIPPET = """<script>
window.__LC_REPORT_ROWS = {{ report_rows|tojson }};
window.__LC_REPORT_ID = {{ report_id|tojson }};
</script>
<script src="{{ url_for('static', filename='reports_live.js') }}?v=4"></script>"""

PRINT_ASSETS = (
    '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'reports-print.css\') }}?v=1">\n'
    '<script src="{{ url_for(\'static\', filename=\'reports-print.js\') }}?v=1"></script>'
)


def repair(fname: str, report_id: str = "report-clients") -> None:
    path = ROOT / fname
    text = path.read_text(encoding="utf-8")

    if 'data-report-id' not in text:
        text = text.replace("<body>", f'<body data-report-id="{report_id}">', 1)

    text = re.sub(
        r'(<table class="rpt-table">\s*<thead>.*?</thead>\s*<tbody>)(.*?)(</tbody>)',
        rf'\1{LOADING_ROW}\3',
        text,
        count=1,
        flags=re.S,
    )
    text = re.sub(
        r'(<tbody id="report-tbody">)(.*?)(</tbody>)',
        rf'\1{LOADING_ROW}\3',
        text,
        count=1,
        flags=re.S,
    )

    text = re.sub(
        r'(<div class="rpt-stat-val">)(.*?)(</div>)',
        r'\1—\3',
        text,
    )
    text = re.sub(
        r'(<div style="font-size:18px;font-weight:700;color:#1a4fa0;font-family:DM Sans,sans-serif">)(.*?)(</div>)',
        r'\1—\3',
        text,
    )
    text = text.replace('id="table-info">عرض 10 سجل', 'id="table-info">—')

    text = text.replace('<div class="filter-card"', '<div class="filter-card screen-only"', 1)
    text = text.replace('<div class="page-header">', '<div class="page-header screen-only">', 1)
    text = text.replace(
        '<div class="rpt-stat-row"',
        '<div class="rpt-stat-row screen-only"',
        1,
    )
    text = text.replace('<div class="table-wrap">', '<div class="table-wrap screen-only">', 1)
    text = text.replace('onclick="window.print()"', 'onclick="LiftCorePrint.report()"')

    text = text.replace(
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">',
        '<div id="rpt-print-stats" class="rpt-print-stats" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">',
        1,
    )

    text = re.sub(
        r'(<table class="rpt-table">\s*<thead>.*?</thead>\s*<tbody)(>)',
        r'\1 id="print-tbody"\2',
        text,
        count=1,
        flags=re.S,
    )

    text = re.sub(r"@media print\{[^}]+\}", "", text, count=1)

    if "reports-print.css" not in text:
        marker = '<link rel="stylesheet" href="/static/liftcore-layout.css">'
        text = text.replace(marker, marker + "\n" + PRINT_ASSETS, 1)

    text = re.sub(
        r'<script src="\{\{ url_for\(\'static\', filename=\'reports_live\.js\'\) \}\}[^<]*></script>\s*</body>',
        BOOT_SNIPPET + "\n</body>",
        text,
        count=1,
    )
    if BOOT_SNIPPET not in text:
        text = text.replace("</body>", BOOT_SNIPPET + "\n</body>", 1)

    path.write_text(text, encoding="utf-8", newline="\n")
    print("repaired", fname, "utf-8 ok, arabic sample:", "تقرير العملاء" in text)


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "report-clients.html"
    rid = sys.argv[2] if len(sys.argv) > 2 else "report-clients"
    repair(name, rid)
