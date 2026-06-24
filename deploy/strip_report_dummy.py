#!/usr/bin/env python3
"""إزالة البيانات الوهمية من قوالب التقارير واستبدالها بعناصر تحميل."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates"

LOADING_ROW = '<tr><td colspan="20" style="text-align:center;padding:24px;color:var(--text3)">جاري تحميل البيانات...</td></tr>'

BOOT_SNIPPET = """<script>
window.__LC_REPORT_ROWS = {{ report_rows|tojson }};
window.__LC_REPORT_ID = {{ report_id|tojson }};
</script>
<script src="{{ url_for('static', filename='reports_live.js') }}?v=4"></script>"""

TABULAR = [
    "report-clients.html",
    "report-elevators.html",
    "report-contracts.html",
    "report-technicians.html",
    "report-maintenance.html",
    "report-faults.html",
    "report-revenues.html",
    "report-expenses.html",
    "report-invoices.html",
    "report-inventory.html",
    "report-stock.html",
    "report-parts.html",
]


def strip_tbody(content: str, marker: str, replacement_inner: str) -> str:
    pattern = re.compile(
        rf'(<tbody[^>]*{marker}[^>]*>)(.*?)(</tbody>)',
        re.S,
    )
    return pattern.sub(rf'\1{replacement_inner}\3', content, count=1)


def strip_all_tbodies(content: str) -> str:
    # شاشة العرض
    content = strip_tbody(content, r'id="report-tbody"', LOADING_ROW)
    # جدول الطباعة داخل rpt-table
    content = re.sub(
        r'(<table class="rpt-table">\s*<thead>.*?</thead>\s*<tbody>)(.*?)(</tbody>)',
        rf'\1{LOADING_ROW}\3',
        content,
        count=1,
        flags=re.S,
    )
    return content


def strip_stat_vals(content: str) -> str:
    content = re.sub(
        r'(<div class="rpt-stat-val">)(.*?)(</div>)',
        r'\1—\3',
        content,
    )
    # شبكة إحصائيات الطباعة
    content = re.sub(
        r'(<div style="font-size:18px;font-weight:700;color:#1a4fa0;font-family:DM Sans,sans-serif">)(.*?)(</div>)',
        r'\1—\3',
        content,
    )
    return content


def fix_table_info(content: str) -> str:
    return content.replace(
        'id="table-info">عرض 10 سجل',
        'id="table-info">—',
    )


def replace_script_tail(content: str) -> str:
    content = re.sub(
        r'<script src="\{\{ url_for\(\'static\', filename=\'reports_live\.js\'\) \}\}\?\?v=\d+"></script>',
        '',
        content,
    )
    content = re.sub(
        r'<script src="\{\{ url_for\(\'static\', filename=\'reports_live\.js\'\) \}\}\?v=\d+"></script>\s*</body>',
        BOOT_SNIPPET + '\n</body>',
        content,
        count=1,
    )
    if BOOT_SNIPPET not in content:
        content = content.replace(
            '</body>',
            BOOT_SNIPPET + '\n</body>',
            1,
        )
    return content


def patch_dashboard(content: str) -> str:
    content = re.sub(
        r'(<div class="kpi-val" id="kpi-\w+">)[^<]+(</div>)',
        r'\1—\2',
        content,
    )
    content = re.sub(
        r'(<div class="kpi-change[^"]*">)[^<]+(</div>)',
        r'\1\2',
        content,
    )
    # إزالة بيانات الشارت الثابتة
    content = re.sub(
        r"const REVENUE_DATA = \[.*?\];",
        "const REVENUE_DATA = [];",
        content,
        flags=re.S,
    )
    content = re.sub(
        r"const EXPENSE_DATA = \[.*?\];",
        "const EXPENSE_DATA = [];",
        content,
        flags=re.S,
    )
    content = re.sub(
        r"const VISITS_DATA = \[.*?\];",
        "const VISITS_DATA = [];",
        content,
        flags=re.S,
    )
    content = re.sub(
        r"const FAULTS_DATA = \[.*?\];",
        "const FAULTS_DATA = [];",
        content,
        flags=re.S,
    )
    content = content.replace(
        '<script src="{{ url_for(\'static\', filename=\'reports_live.js\') }}?v=3"></script>',
        '<script>window.__LC_DASHBOARD_YEAR = {{ current_year|default(2026) }};</script>\n'
        '<script src="{{ url_for(\'static\', filename=\'reports_live.js\') }}?v=4"></script>',
    )
    return content


def main() -> None:
    for fname in TABULAR:
        path = ROOT / fname
        text = path.read_text(encoding="utf-8")
        text = strip_all_tbodies(text)
        text = strip_stat_vals(text)
        text = fix_table_info(text)
        text = replace_script_tail(text)
        path.write_text(text, encoding="utf-8")
        print("stripped", fname)

    dash = ROOT / "report-dashboard.html"
    text = dash.read_text(encoding="utf-8")
    text = patch_dashboard(text)
    dash.write_text(text, encoding="utf-8")
    print("stripped report-dashboard.html")


if __name__ == "__main__":
    main()
