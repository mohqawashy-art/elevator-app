"""
مسح كل البيانات التشغيلية + تجهيز بيئة اختبار فارغة
  python reset_test_environment.py
  python reset_test_environment.py --with-items   # يستورد الأصناف من CSV للمخزن
"""

from __future__ import annotations

import argparse
import os
import sys

from app import app, db, hash_password
from models import Customer, InventoryItem, Settings, User
from seed_data import clear_business_data


def _ensure_admin_and_settings() -> None:
    if not User.query.filter_by(username="admin").first():
        db.session.add(
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="محمد القواشي",
                email="admin@liftcore.sa",
                role="admin",
                is_active=True,
            )
        )
    if not Settings.query.first():
        db.session.add(
            Settings(
                company_name="شركة جما تقنية للمصاعد",
                company_name_en="Jama Elevator Technology Co.",
                phone="0500000000",
                email="info@liftcore.sa",
                city="مكة المكرمة",
                tax_pct=15,
                currency="ر.س",
                language="ar",
            )
        )


def reset(with_items: bool = False, items_csv: str | None = None) -> None:
    with app.app_context():
        db.create_all()
        print("[1/3] مسح البيانات التشغيلية...")
        clear_business_data()
        _ensure_admin_and_settings()
        db.session.commit()

        customers = Customer.query.count()
        items = InventoryItem.query.count()
        print(f"      عملاء: {customers} | أصناف: {items}")

        if with_items:
            csv_path = items_csv or os.path.join(
                os.path.expanduser("~"),
                "Downloads",
                "جدول الاصناف 27_5_2026.csv",
            )
            if not os.path.isfile(csv_path):
                print(f"[!] ملف الأصناف غير موجود: {csv_path}")
            else:
                print(f"[2/3] استيراد الأصناف من: {csv_path}")
                from import_inventory_csv import import_inventory_csv

                stats = import_inventory_csv(csv_path, replace=False)
                print(
                    f"      أُضيف {stats['inserted']} صنف | "
                    f"الإجمالي {stats['total_in_db']}"
                )
        else:
            print("[2/3] تخطي الأصناف — أضفها يدوياً من صفحة الأصناف")

        print("[3/3] جاهز للاختبار من الصفر")
        print("      الدخول: admin / admin123")
        print("      سيناريو 10 عملاء: docs/SCENARIO_10_CLIENTS.md")
        print("      إفراغ جما على السيرفر: bash deploy/reset_jama_demo.sh")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-items",
        action="store_true",
        help="استيراد أصناف المخزن من CSV بعد المسح",
    )
    parser.add_argument("--items-csv", default="")
    args = parser.parse_args()
    try:
        reset(with_items=args.with_items, items_csv=args.items_csv or None)
    except Exception as exc:
        print(f"فشل: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
