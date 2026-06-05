"""
LiftCore — استيراد بيانات حقيقية من Excel
  python import_real_data.py
  python import_real_data.py "C:\\Users\\HOME\\Downloads"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import timedelta
from typing import Any

import pandas as pd

from app import app, db
from models import (
    Contract,
    ContractElevator,
    Customer,
    Elevator,
    Expense,
    MaintenanceVisit,
    PartsBilling,
    Revenue,
    Technician,
)
from seed_data import clear_business_data

FILE_PATTERNS = {
    "customers": "العملاء",
    "contracts": "العقود",
    "elevators": "المصاعد",
    "technicians": "الفنيين",
    "visits": "سجل الزيارات",
    "expenses": "المصروفات",
    "revenues": "إيرادات",
    "spare_parts": "بيان تركيب قطع الغيار",
}


def _score_excel_file(key: str, path: str) -> int:
    filename = os.path.basename(path)
    fragment = FILE_PATTERNS[key]
    score = 120 if filename.startswith(fragment) else (60 if fragment in filename else -999)
    lowered = filename.lower()
    if "checklist" in lowered:
        score -= 300
    if lowered.startswith("عملاء_") and key != "customers":
        score -= 200
    if key == "customers" and lowered.startswith("عملاء_"):
        score -= 250
    for token, pts in (("5_6_2026", 40), ("30_5_2026", 25), ("27_5_2026", 15)):
        if token in filename:
            score += pts
            break
    try:
        score += min(os.path.getsize(path) // 500, 40)
    except OSError:
        pass
    return score


def find_excel_files(folder: str, prefer_date: str = "5_6_2026") -> dict[str, str]:
    candidates: dict[str, list[str]] = {k: [] for k in FILE_PATTERNS}
    if not os.path.isdir(folder):
        return {}
    for name in os.listdir(folder):
        if not name.endswith(".xlsx") or name.startswith("~$"):
            continue
        full = os.path.join(folder, name)
        for key, fragment in FILE_PATTERNS.items():
            if fragment in name:
                candidates[key].append(full)
                break
    found = {}
    for key, paths in candidates.items():
        if not paths:
            continue
        dated = [p for p in paths if prefer_date in os.path.basename(p)]
        pool = dated or paths
        found[key] = max(pool, key=lambda p: _score_excel_file(key, p))
    return found


def _cell(row: dict[str, Any], *candidates: str):
    for key in candidates:
        if key in row and pd.notna(row[key]):
            return row[key]
    for key, value in row.items():
        for candidate in candidates:
            if candidate in str(key) and pd.notna(value):
                return value
    return None


def _str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def _f(val, default=0.0) -> float:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _i(val, default=0) -> int:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _parse_date(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, "date") and callable(val.date):
        return val.date()
    dt = pd.to_datetime(str(val).strip(), dayfirst=True, errors="coerce")
    return None if pd.isna(dt) else dt.date()


def _norm_id(val) -> str:
    s = _str(val)
    return s[:-2] if s.endswith(".0") else s


def _extract_cn(text: str) -> str | None:
    m = re.search(r"CN-\d+", _str(text))
    return m.group(0) if m else None


def _extract_el(text: str) -> str | None:
    m = re.search(r"EL-\d+", _str(text).split("|")[0])
    return m.group(0) if m else None


def _extract_tech(text: str) -> str | None:
    m = re.search(r"Tech-\d+", _str(text).split(",")[0], re.I)
    return f"Tech-{m.group(0).split('-')[-1]}" if m else None


def _norm_visit_code(code: str) -> str:
    text = re.sub(r"\s+", "", code)
    if text.upper().startswith("VI") and not text.startswith("VI-"):
        text = re.sub(r"^VI", "VI-", text, flags=re.I)
    return text


def _norm_city(val) -> str:
    s = _str(val)
    return "مكة" if "مكة" in s else (s or "مكة")


def _norm_contract_status(val) -> str:
    m = {"ساري": "نشط", "أوشك على الانتهاء": "على وشك الانتهاء", "منتهي": "منتهي", "ملغي": "ملغي"}
    return m.get(_str(val), "نشط")


def _norm_visit_status(val) -> str:
    return "مكتملة" if _str(val) in ("مكتمل", "تم الاصلاح") else _str(val) or "مكتملة"


def _invoice_status(value, paid) -> str:
    value, paid = _f(value), _f(paid)
    if paid <= 0:
        return "غير مدفوع"
    if value > 0 and paid >= value:
        return "مدفوع"
    if paid > 0:
        return "مدفوع جزئياً"
    return "غير مدفوع"


def import_all(folder: str, reset: bool = True) -> dict[str, int]:
    paths = find_excel_files(folder)
    stats = {k: 0 for k in FILE_PATTERNS}
    stats["files_found"] = len(paths)
    if not paths:
        raise FileNotFoundError(f"لم يُعثر على ملفات Excel في: {folder}")

    if reset:
        clear_business_data()

    customers: dict[str, Customer] = {}
    contracts: dict[str, Contract] = {}
    elevators: dict[str, Elevator] = {}
    techs: dict[str, Technician] = {}

    # ── عملاء ──
    if "customers" in paths:
        for _, row in pd.read_excel(paths["customers"]).iterrows():
            r = row.to_dict()
            code = _str(_cell(r, "رقم العميل"))
            name = _str(_cell(r, "اسم العميل")) or _str(_cell(r, "اسم العميل | رقم العميل"))
            if not code or not name:
                continue
            c = Customer(
                code=code,
                name=name,
                city=_norm_city(_cell(r, "المدينة")),
                district=_str(_cell(r, "الحي أو المنطقة")),
                address=_str(_cell(r, "العنوان")),
                phone=_norm_id(_cell(r, "الجوال")),
                national_id=_norm_id(_cell(r, "رقم الهوية")),
                email=_str(_cell(r, "البريد الالكتروني")),
                status=_str(_cell(r, "حالة العميل")) or "نشط",
                notes=_str(_cell(r, "ملاحظات")),
            )
            db.session.add(c)
            customers[code] = c
        db.session.flush()
        stats["customers"] = len(customers)

    contract_to_customer = {}
    if "customers" in paths:
        for _, row in pd.read_excel(paths["customers"]).iterrows():
            cn, cc = _extract_cn(_cell(row.to_dict(), "رقم العقد")), _str(_cell(row.to_dict(), "رقم العميل"))
            if cn and cc in customers:
                contract_to_customer[cn] = customers[cc]

    # ── فنيون ──
    if "technicians" in paths:
        for _, row in pd.read_excel(paths["technicians"]).iterrows():
            r = row.to_dict()
            code = _extract_tech(_cell(r, "Technical ID | رقم الفني", "رقم واسم الفني"))
            name = _str(_cell(r, "Technical Name | اسم الفني"))
            if not code or not name:
                continue
            t = Technician(
                code=code,
                name=name,
                job_title=_str(_cell(r, "Job Title | المسمى الوظيفي")).split("|")[-1].strip(),
                status="متاح",
                city="مكة",
                emergency=True,
            )
            db.session.add(t)
            techs[code] = t
        db.session.flush()
        stats["technicians"] = len(techs)

    # ── عقود ──
    if "contracts" in paths:
        for _, row in pd.read_excel(paths["contracts"]).iterrows():
            r = row.to_dict()
            code = _str(_cell(r, "رقم العقد"))
            name = _str(_cell(r, "العملاء"))
            annual = _f(_cell(r, "قيمة العقد"))
            if (not name or name.lower() == "nan") and annual <= 0:
                continue
            start, end = _parse_date(_cell(r, "تاريخ بداية العقد")), _parse_date(_cell(r, "تاريخ انتهاء العقد"))
            if not code or not start or not end:
                continue
            cust = contract_to_customer.get(code)
            if not cust and name:
                cust = next((c for c in customers.values() if c.name == name), None)
            paid = _f(_cell(r, "المبلغ المسدد"))
            val = annual
            tax = round(val * 0.15, 2)
            c = Contract(
                code=code,
                customer_id=cust.id if cust else None,
                contract_type="عقد صيانة" if _str(_cell(r, "نوع العقد")) == "صيانة" else _str(_cell(r, "نوع العقد")) or "عقد صيانة",
                start_date=start,
                end_date=end,
                duration_months=max(0, (end.year - start.year) * 12 + end.month - start.month),
                maint_frequency=_str(_cell(r, "برنامج الصيانة")) or "سنوي",
                visits_per_month=1,
                value=val,
                tax_pct=15,
                tax_amount=tax,
                total=round(val + tax, 2),
                payment_terms="دفعة واحدة",
                invoice_status=_invoice_status(val, paid),
                status=_norm_contract_status(_cell(r, "حالة العقد")),
                reminder_date=end - timedelta(days=30),
                notes=_str(_cell(r, "ملاحظات")),
            )
            db.session.add(c)
            contracts[code] = c
        db.session.flush()
        stats["contracts"] = len(contracts)

    # ── مصاعد ──
    if "elevators" in paths:
        for _, row in pd.read_excel(paths["elevators"]).iterrows():
            r = row.to_dict()
            el_code = _extract_el(_cell(r, "رقم المصعد"))
            cn_code = _extract_cn(_cell(r, "رقم العقد", "Link to Contracts / العقود"))
            if not el_code:
                continue
            contract = contracts.get(cn_code)
            customer = contract.customer if contract else contract_to_customer.get(cn_code or "")
            if not customer and contract:
                customer = Customer.query.get(contract.customer_id)
            if not customer:
                continue
            e = Elevator(
                code=el_code,
                customer_id=customer.id,
                building_name=_str(_cell(r, "Title")) or customer.name,
                city=customer.city,
                district=customer.district,
                elev_type=_str(_cell(r, "نوع المصعد")),
                capacity_kg=_i(_cell(r, "الحمولة (كجم)")),
                floors=_i(_cell(r, "عدد الوقفات")),
                status="نشط" if _str(_cell(r, "حالة المصعد")) in ("فعال", "نشط") else _str(_cell(r, "حالة المصعد")) or "نشط",
                notes=_str(_cell(r, "حالة الضمان")),
            )
            db.session.add(e)
            db.session.flush()
            elevators[el_code] = e
            if contract:
                db.session.add(ContractElevator(contract_id=contract.id, elevator_id=e.id))
        db.session.flush()
        stats["elevators"] = len(elevators)

    # ── زيارات ──
    seen_visits = set()
    if "visits" in paths:
        photo_cols = [c for c in pd.read_excel(paths["visits"]).columns if "صورة" in str(c)]
        for _, row in pd.read_excel(paths["visits"]).iterrows():
            r = row.to_dict()
            vcode = _norm_visit_code(_str(_cell(r, "رقم الزيارة")))
            if not vcode or vcode in seen_visits:
                continue
            seen_visits.add(vcode)
            cn = _extract_cn(_cell(r, "رقم العقد", "العقود"))
            el = _extract_el(_cell(r, "رقم المصعد"))
            elev = elevators.get(el)
            if not elev:
                continue
            contract = contracts.get(cn)
            tech = techs.get(_extract_tech(_cell(r, "الفنيين")) or "")
            vdate = _parse_date(_cell(r, "تاريخ الزيارة"))
            if not vdate:
                continue
            works = [f"{lbl}: {_str(_cell(r, col))}" for lbl, col in (
                ("تقرير", "تقرير الزيارة"), ("وصف العطل", "وصف العطل (من العميل)"),
                ("التشخيص", "التشخيص الفني"), ("الإجراء", "الاجراء المتخذ"),
            ) if _str(_cell(r, col))]
            db.session.add(MaintenanceVisit(
                code=vcode,
                contract_id=contract.id if contract else None,
                elevator_id=elev.id,
                technician_id=tech.id if tech else None,
                visit_type=_str(_cell(r, "نوع الزيارة")) or "صيانة دورية",
                visit_date=vdate,
                visit_time=_str(_cell(r, "وقت الزيارة")),
                status=_norm_visit_status(_cell(r, "حالة الزيارة")),
                works_done="\n".join(works) or None,
                observations=_str(_cell(r, "توصيات ختامية")) or None,
                notes=_str(_cell(r, "قطع الغيار")) or None,
            ))
        db.session.flush()
        stats["visits"] = MaintenanceVisit.query.count()

    # ── إيرادات ──
    if "revenues" in paths:
        for _, row in pd.read_excel(paths["revenues"]).iterrows():
            r = row.to_dict()
            num = _i(_cell(r, "رقم العملية"))
            cn = _extract_cn(_cell(r, "العقود", "Title"))
            contract = contracts.get(cn) if cn else None
            rdate = _parse_date(_cell(r, "التاريخ"))
            if not rdate:
                continue
            amount = _f(_cell(r, "المبلغ"))
            tax = round(amount * 0.15, 2)
            db.session.add(Revenue(
                code=f"REV-{num:04d}" if num else f"REV-{Revenue.query.count()+1:04d}",
                customer_id=contract.customer_id if contract else None,
                contract_id=contract.id if contract else None,
                revenue_date=rdate,
                revenue_type=_str(_cell(r, "نوع الايراد")) or "أخرى",
                payment_method=_str(_cell(r, "طريقة الدفع")) or "كاش",
                amount=amount,
                tax_amount=tax,
                total=round(amount + tax, 2),
                status="محصّل" if _str(_cell(r, "Status")) in ("محصل", "محصّل") else _str(_cell(r, "Status")) or "محصّل",
                reference=_str(_cell(r, "مرفقات")),
                notes=_str(_cell(r, "ملاحظات")),
            ))
        db.session.flush()
        stats["revenues"] = Revenue.query.count()

    # ── مصروفات ──
    if "expenses" in paths:
        for _, row in pd.read_excel(paths["expenses"]).iterrows():
            r = row.to_dict()
            num = _i(_cell(r, "رقم العملية"))
            edate = _parse_date(_cell(r, "التاريخ"))
            if not edate:
                continue
            db.session.add(Expense(
                code=f"EXP-{num:04d}" if num else f"EXP-{Expense.query.count()+1:04d}",
                expense_date=edate,
                expense_type=_str(_cell(r, "نوع المصروف")) or "أخرى",
                description=_str(_cell(r, "ملاحظات")) or _str(_cell(r, "نوع المصروف")),
                responsible=_str(_cell(r, "مسئول الصرف")),
                payment_method=_str(_cell(r, "طريقة الدفع")) or "كاش",
                amount=_f(_cell(r, "المبلغ")),
                reference=_str(_cell(r, "مرفقات")),
                notes=_str(_cell(r, "المورد")),
            ))
        db.session.flush()
        stats["expenses"] = Expense.query.count()

    # ── قطع غيار ──
    if "spare_parts" in paths:
        for _, row in pd.read_excel(paths["spare_parts"]).iterrows():
            r = row.to_dict()
            num = _i(_cell(r, "رقم العمليه"))
            cn = _extract_cn(_cell(r, "العقود", "Title"))
            contract = contracts.get(cn) if cn else None
            bdate = _parse_date(_cell(r, "التاريخ"))
            if not bdate:
                continue
            cost, sell = _f(_cell(r, "سعر التكلفة")), _f(_cell(r, "السعر للعميل"))
            elev_id = None
            if contract:
                from models import ContractElevator, Elevator
                link = ContractElevator.query.filter_by(contract_id=contract.id).first()
                if link:
                    elev_id = link.elevator_id
                elif contract.customer_id:
                    elev = Elevator.query.filter_by(customer_id=contract.customer_id).first()
                    elev_id = elev.id if elev else None
            db.session.add(PartsBilling(
                code=f"PB-{num:03d}" if num else f"PB-{PartsBilling.query.count()+1:03d}",
                customer_id=contract.customer_id if contract else None,
                contract_id=contract.id if contract else None,
                elevator_id=elev_id,
                billing_date=bdate,
                description=_str(_cell(r, "بيان قطع الغيار")),
                cost_price=cost,
                sell_price=sell,
                profit=round(sell - cost, 2),
                payment_method=_str(_cell(r, "طريقة الدفع")),
                status="محصل" if _str(_cell(r, "حالة التحصيل")) == "محصل" else _str(_cell(r, "حالة التحصيل")) or "غير محصل",
                notes=_str(_cell(r, "ملحوظات")) or _str(_cell(r, "بيان فاتورة")),
            ))
        db.session.flush()
        stats["spare_parts"] = PartsBilling.query.count()

    db.session.commit()
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=os.path.join(os.path.expanduser("~"), "Downloads"))
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    with app.app_context():
        db.create_all()
        stats = import_all(args.folder, reset=not args.no_reset)
        print("اكتمل الاستيراد:")
        for k, v in stats.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
