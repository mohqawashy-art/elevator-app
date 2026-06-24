#!/usr/bin/env python3
"""ربط أنماط الطباعة وتحسين قوالب التقارير."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "templates"

PRINT_ASSETS = (
    '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'reports-print.css\') }}?v=1">\n'
    '<script src="{{ url_for(\'static\', filename=\'reports-print.js\') }}?v=1"></script>'
)

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


def add_print_assets(text: str) -> str:
    if "reports-print.css" in text:
        return text
    marker = '<link rel="stylesheet" href="/static/liftcore-layout.css">'
    if marker in text:
        return text.replace(marker, marker + "\n" + PRINT_ASSETS, 1)
    marker2 = "{% include 'partials/liftcore_head.html' %}"
    if marker2 in text:
        return text.replace(marker2, marker2 + "\n" + PRINT_ASSETS, 1)
    return text


def add_screen_only(text: str) -> str:
    text = text.replace('<div class="filter-card"', '<div class="filter-card screen-only"', 1)
    text = text.replace('<div class="page-header">', '<div class="page-header screen-only">', 1)
    text = re.sub(
        r'(<div class="rpt-stat-row"[^>]*)(style=)',
        r'\1class="screen-only" \2',
        text,
        count=1,
    )
    text = text.replace(
        '<div class="table-wrap">',
        '<div class="table-wrap screen-only">',
        1,
    )
    return text


def fix_print_stats_grid(text: str) -> str:
    return text.replace(
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">',
        '<div id="rpt-print-stats" class="rpt-print-stats" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">',
        1,
    )


def fix_print_buttons(text: str) -> str:
    text = text.replace('onclick="window.print()"', 'onclick="LiftCorePrint.report()"')
    return text


def fix_print_media(text: str) -> str:
    """استبدال قواعد الطباعة المدمجة بإشارة للملف الموحّد."""
    text = re.sub(
        r"@media print\{[^}]+\}",
        "/* print styles → reports-print.css */",
        text,
        count=1,
    )
    return text


def add_print_tbody_id(text: str) -> str:
    return re.sub(
        r'(<table class="rpt-table">\s*<thead>.*?</thead>\s*<tbody)(>)',
        r'\1 id="print-tbody"\2',
        text,
        count=1,
        flags=re.S,
    )


def patch_tabular(fname: str) -> None:
    path = ROOT / fname
    text = path.read_text(encoding="utf-8")
    text = add_print_assets(text)
    text = add_screen_only(text)
    text = fix_print_stats_grid(text)
    text = fix_print_buttons(text)
    text = fix_print_media(text)
    text = add_print_tbody_id(text)
    path.write_text(text, encoding="utf-8")
    print("print", fname)


def patch_annual() -> None:
    path = ROOT / "report-annual.html"
    text = path.read_text(encoding="utf-8")
    text = add_print_assets(text)
    text = fix_print_buttons(text)
    text = text.replace('<div class="page-header">', '<div class="page-header screen-only">', 1)
    text = text.replace('<div class="filter-card"', '<div class="filter-card screen-only"', 1)
    text = re.sub(
        r"@media print\{[^}]+\}",
        "/* print styles → reports-print.css */",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")
    print("print report-annual.html")


def patch_dashboard() -> None:
    path = ROOT / "report-dashboard.html"
    text = path.read_text(encoding="utf-8")
    text = add_print_assets(text)
    text = fix_print_buttons(text)
    text = text.replace('<div class="page-header">', '<div class="page-header screen-only">', 1)
    if 'class="year-selector"' not in text:
        text = text.replace(
            '<select id="sel-year"',
            '<select id="sel-year" class="year-selector"',
            1,
        )
    text = re.sub(
        r"/\* Print \*/\s*\.print-toolbar\{[^}]+\}\s*@media print\{[^}]+\}",
        "/* print styles → reports-print.css */",
        text,
        count=1,
        flags=re.S,
    )
    path.write_text(text, encoding="utf-8")
    print("print report-dashboard.html")


def main() -> None:
    for fname in TABULAR:
        patch_tabular(fname)
    patch_annual()
    patch_dashboard()


if __name__ == "__main__":
    main()
