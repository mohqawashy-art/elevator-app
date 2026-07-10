#!/usr/bin/env python3
"""استبدال Model.query بـ tenant_query — أسبوع 5–6."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODELS = [
    'Customer', 'Elevator', 'Contract', 'ContractElevator', 'Technician',
    'TechnicianDocument', 'MaintenanceTeam', 'MaintenanceVisit', 'VisitTechnician',
    'Fault', 'FaultTechnician', 'Revenue', 'Expense', 'Invoice', 'InventoryItem',
    'StockMovement', 'PartsBilling', 'PurchaseOrder', 'PurchaseOrderLine',
    'ElevatorEstimate', 'ElevatorEstimateLine', 'Signatory', 'Settings', 'User',
    'AuditLog', 'InstallLead', 'InstallProject', 'InstallQuotation',
    'InstallQuotationLine', 'InstallTimelineStep',
]

IMPORT_LINE = (
    'from tenant_scope import assign_organization, tenant_get_or_404, tenant_query'
)

FILES = [
    'app.py',
    'operations.py',
    'customer_billing.py',
    'report_data.py',
    'entity_links.py',
    'installation/routes.py',
]


def transform(text: str) -> str:
    for model in MODELS:
        text = re.sub(
            rf'\b{model}\.query\.get_or_404\(',
            f'tenant_get_or_404({model}, ',
            text,
        )
        text = re.sub(
            rf'\b{model}\.query\.get\(([^)]+)\)',
            rf'tenant_query({model}).filter_by(id=\1).first()',
            text,
        )
        text = re.sub(rf'\b{model}\.query\b', f'tenant_query({model})', text)
    return text


def ensure_import(text: str) -> str:
    if 'tenant_query' in text and IMPORT_LINE not in text:
        lines = text.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith('from ') or line.startswith('import '):
                insert_at = i + 1
        lines.insert(insert_at, IMPORT_LINE)
        return '\n'.join(lines) + ('\n' if text.endswith('\n') else '')
    return text


def main() -> int:
    for rel in FILES:
        path = ROOT / rel
        if not path.is_file():
            print(f'skip missing {rel}')
            continue
        original = path.read_text(encoding='utf-8')
        updated = transform(original)
        if rel != 'app.py':
            updated = ensure_import(updated)
        if updated != original:
            path.write_text(updated, encoding='utf-8')
            print(f'updated {rel}')
        else:
            print(f'unchanged {rel}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
