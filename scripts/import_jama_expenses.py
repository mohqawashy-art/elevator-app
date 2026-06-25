#!/usr/bin/env python3
"""Import Jama expenses from Excel."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd

from app import app, db
from import_real_data import _cell, _f, _i, _parse_date, _str
from models import Expense


def import_expenses(path: str, *, dry_run: bool = False, skip_existing: bool = True) -> dict[str, int]:
    df = pd.read_excel(path)
    stats = {
        "rows": len(df),
        "imported": 0,
        "skipped_existing": 0,
        "errors": 0,
    }
    existing_codes = {e.code.upper() for e in Expense.query.all() if e.code}

    for _, row in df.iterrows():
        r = row.to_dict()
        num = _i(_cell(r, "رقم العملية"))
        code = f"EXP-{num:04d}" if num else ""
        edate = _parse_date(_cell(r, "التاريخ"))
        amount = _f(_cell(r, "المبلغ"))

        if not code or not edate or amount <= 0:
            stats["errors"] += 1
            continue

        if skip_existing and code.upper() in existing_codes:
            stats["skipped_existing"] += 1
            continue

        expense = Expense(
            code=code,
            expense_date=edate,
            expense_type=_str(_cell(r, "نوع المصروف")) or "أخرى",
            description=_str(_cell(r, "ملاحظات")) or _str(_cell(r, "نوع المصروف")),
            responsible=_str(_cell(r, "مسئول الصرف")),
            payment_method=_str(_cell(r, "طريقة الدفع")) or "كاش",
            amount=amount,
            reference=_str(_cell(r, "مرفقات")),
            notes=_str(_cell(r, "المورد")),
        )
        if not dry_run:
            db.session.add(expense)
            existing_codes.add(code.upper())
        stats["imported"] += 1

    if not dry_run:
        db.session.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Jama expenses from Excel")
    parser.add_argument("xlsx", help="Path to expenses .xlsx")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Import even if expense code exists")
    args = parser.parse_args()

    if not os.path.isfile(args.xlsx):
        print(f"ERROR: file not found: {args.xlsx}")
        return 1

    with app.app_context():
        db.create_all()
        print("Database:", app.config.get("SQLALCHEMY_DATABASE_URI", ""))
        print("File:", args.xlsx)
        result = import_expenses(
            args.xlsx,
            dry_run=args.dry_run,
            skip_existing=not args.force,
        )
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
