"""
استيراد جدول الأصناف من CSV إلى inventory_items
  python import_inventory_csv.py
  python import_inventory_csv.py "C:\\Users\\HOME\\Downloads\\جدول الاصناف 27_5_2026.csv"
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

from app import app, db
from models import InventoryItem


DEFAULT_CSV = os.path.join(
    os.path.expanduser("~"),
    "Downloads",
    "جدول الاصناف 27_5_2026.csv",
)

COLUMN_MAP = {
    "كود الصنف": "code",
    "اسم الصنف": "name",
    "الصنيف": "category",
    "الوحدة": "unit",
    "موقع التخزين": "location",
    "سعر الشراء": "buy_price",
    "اخر سعر للشراء": "last_buy_price",
    "الرصيد الحالي": "current_qty",
    "الحد الادنى": "min_qty",
    "المورد الاساسي": "supplier",
    "حالة الصنف": "item_status",
    "ملاحظات": "notes",
}


def _float(val, default=0.0) -> float:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    text = str(val).strip().replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _normalize_code(raw: str) -> str:
    code = _str(raw)
    if not code:
        return ""
    if not code.startswith("#"):
        digits = "".join(ch for ch in code if ch.isdigit())
        if digits:
            return f"#{digits.zfill(3)}"
    return code


def _read_inventory_df(path: str) -> pd.DataFrame:
    lower = path.lower()
    if lower.endswith(('.xlsx', '.xls')):
        return pd.read_excel(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def import_inventory_file(path: str, replace: bool = False) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"الملف غير موجود: {path}")

    df = _read_inventory_df(path)
    missing = [col for col in COLUMN_MAP if col not in df.columns]
    if missing:
        raise ValueError(f"أعمدة ناقصة في الملف: {', '.join(missing)}")

    stats = {"rows": 0, "inserted": 0, "updated": 0, "skipped": 0}

    with app.app_context():
        db.create_all()
        if replace:
            InventoryItem.query.delete()
            db.session.commit()

        for _, row in df.iterrows():
            stats["rows"] += 1
            name = _str(row.get("اسم الصنف"))
            code = _normalize_code(row.get("كود الصنف"))
            if not name or name.lower() == "untitled record":
                stats["skipped"] += 1
                continue
            if not code:
                stats["skipped"] += 1
                continue

            buy_price = _float(row.get("سعر الشراء"))
            last_buy = _float(row.get("اخر سعر للشراء"))
            if last_buy > 0:
                buy_price = last_buy

            payload = {
                "name": name,
                "category": _str(row.get("الصنيف")),
                "unit": _str(row.get("الوحدة")) or "قطعة",
                "location": _str(row.get("موقع التخزين")),
                "current_qty": _float(row.get("الرصيد الحالي")),
                "min_qty": _float(row.get("الحد الادنى")),
                "buy_price": buy_price,
                "supplier": _str(row.get("المورد الاساسي")),
            }

            sell_price = _float(row.get("سعر البيع")) if "سعر البيع" in df.columns else 0.0
            if sell_price <= 0:
                sell_price = buy_price
            payload["sell_price"] = sell_price

            notes_parts = []
            status = _str(row.get("حالة الصنف"))
            if status:
                notes_parts.append(f"الحالة: {status}")
            extra_notes = _str(row.get("ملاحظات"))
            if extra_notes:
                notes_parts.append(extra_notes)
            payload["notes"] = " — ".join(notes_parts)

            item = InventoryItem.query.filter_by(code=code).first()
            if item:
                for key, val in payload.items():
                    setattr(item, key, val)
                stats["updated"] += 1
            else:
                item = InventoryItem(code=code, **payload)
                db.session.add(item)
                stats["inserted"] += 1

        db.session.commit()
        stats["total_in_db"] = InventoryItem.query.count()

    return stats


def import_inventory_csv(path: str, replace: bool = False) -> dict:
    return import_inventory_file(path, replace=replace)


def main():
    parser = argparse.ArgumentParser(description="استيراد أصناف المخزن من CSV أو Excel")
    parser.add_argument("csv_path", nargs="?", default=DEFAULT_CSV)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="حذف كل الأصناف الحالية قبل الاستيراد",
    )
    args = parser.parse_args()

    try:
        stats = import_inventory_file(args.csv_path, replace=args.replace)
    except Exception as exc:
        print(f"فشل الاستيراد: {exc}", file=sys.stderr)
        sys.exit(1)

    print("تم الاستيراد بنجاح")
    print(f"  الملف: {args.csv_path}")
    print(f"  صفوف الملف: {stats['rows']}")
    print(f"  أُضيف: {stats['inserted']}")
    print(f"  حُدّث: {stats['updated']}")
    print(f"  تُخطّى: {stats['skipped']}")
    print(f"  إجمالي الأصناف في القاعدة: {stats['total_in_db']}")


if __name__ == "__main__":
    main()
