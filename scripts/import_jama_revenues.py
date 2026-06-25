#!/usr/bin/env python3
"""Import Jama revenues from Excel."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from app import app, db
from entity_links import contract_by_code, customer_by_name
from import_real_data import _cell, _extract_cn, _f, _i, _parse_date, _str
from models import Revenue


def _map_status(raw: str) -> str:
    s = _str(raw)
    if s in ("محصل", "محصّل", "مكتملة"):
        return "محصّل"
    if s in ("معلق", "معلّق"):
        return "معلق"
    if "لغ" in s:
        return "ملغي"
    return s or "محصّل"


def import_revenues(path: str, *, dry_run: bool = False, skip_existing: bool = True) -> dict[str, int]:
    df = pd.read_excel(path)
    stats = {
        "rows": len(df),
        "imported": 0,
        "skipped_existing": 0,
        "skipped_missing": 0,
        "errors": 0,
    }
    missing_samples: list[str] = []

    existing_codes = {r.code.upper() for r in Revenue.query.all() if r.code}

    for _, row in df.iterrows():
        r = row.to_dict()
        num = _i(_cell(r, "رقم العملية"))
        code = f"REV-{num:04d}" if num else ""
        cn = _extract_cn(_cell(r, "العقود", "Title"))
        rdate = _parse_date(_cell(r, "التاريخ"))
        amount = _f(_cell(r, "المبلغ"))

        if not code or not rdate or amount <= 0:
            stats["errors"] += 1
            continue

        if skip_existing and code.upper() in existing_codes:
            stats["skipped_existing"] += 1
            continue

        contract = contract_by_code(cn) if cn else None
        customer = contract.customer if contract else customer_by_name(_str(_cell(r, "Title")))
        if not contract and not customer:
            stats["skipped_missing"] += 1
            if len(missing_samples) < 15:
                missing_samples.append(f"{code}: no contract/customer for {cn or _str(_cell(r, 'Title'))}")
            continue

        tax = round(amount * 0.15, 2)
        revenue = Revenue(
            code=code,
            customer_id=customer.id if customer else (contract.customer_id if contract else None),
            contract_id=contract.id if contract else None,
            revenue_date=rdate,
            revenue_type=_str(_cell(r, "نوع الايراد")) or "أخرى",
            payment_method=_str(_cell(r, "طريقة الدفع")) or "كاش",
            amount=amount,
            tax_amount=tax,
            total=round(amount + tax, 2),
            status=_map_status(_cell(r, "Status", "الحالة")),
            reference=_str(_cell(r, "مرفقات")),
            notes=_str(_cell(r, "ملاحظات")),
        )
        if not dry_run:
            db.session.add(revenue)
            existing_codes.add(code.upper())
        stats["imported"] += 1

    if not dry_run:
        db.session.commit()

    stats["missing_samples"] = missing_samples
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Jama revenues from Excel")
    parser.add_argument("xlsx", help="Path to revenues .xlsx")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Import even if revenue code exists")
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f"ERROR: file not found: {args.xlsx}")
        return 1

    with app.app_context():
        db.create_all()
        print("Database:", app.config.get("SQLALCHEMY_DATABASE_URI", ""))
        print("File:", args.xlsx)
        result = import_revenues(
            args.xlsx,
            dry_run=args.dry_run,
            skip_existing=not args.force,
        )
        print(result)
        if result.get("missing_samples"):
            print("Missing samples:")
            for line in result["missing_samples"]:
                print(" ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
