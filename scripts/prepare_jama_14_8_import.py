# -*- coding: utf-8 -*-
"""تجهيز ملفات جما 14/8/2026 لرفع ليفت كور (واجهة + سكربت السيرفر).

يحافظ على أكواد سمارت سويت: C-xxxx / CN-xxxxx / EL-xxxx / Tech-xxx
ويربط العقود والمصاعد بكود العميل من ملف العملاء (بالاسم أولاً).
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

SRC_CLIENTS = Path(r"c:\Users\HOME\Downloads\العملاء 14_8_2026.xlsx")
SRC_CONTRACTS = Path(r"c:\Users\HOME\Downloads\العقود 14_8_2026 (1).xlsx")
SRC_ELEVATORS = Path(r"c:\Users\HOME\Downloads\المصاعد 14_8_2026.xlsx")
SRC_TECHS = Path(r"c:\Users\HOME\Downloads\الفنيين 14_8_2026.xlsx")

DESKTOP = Path(r"c:\Users\HOME\OneDrive\Desktop\جما استيراد 14-8-2026")
DESKTOP_ASCII = Path(r"c:\Users\HOME\OneDrive\Desktop\jama_import_14_8_2026")
REPO = Path(r"d:\New folder\elevator-app\deploy\data\jama_import")
SUMMARY = Path(r"d:\New folder\elevator-app\.tmp-jama-14-8-import-summary.json")

TAX_PCT = 15.0
# ليفت كور يلزم تاريخ بداية/نهاية — إن نقص في سمارت سويت نضع تاريخ التسليم ليُحفظ السجل
FALLBACK_START = date(2025, 11, 1)


def _str(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    s = str(v).strip()
    if s.lower() in ("nan", "none", "-"):
        return ""
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _norm_name(s) -> str:
    s = re.sub(r"\s+", " ", _str(s)).strip()
    return (
        s.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ة", "ه")
        .replace("ى", "ي")
    )


def _money(v) -> float:
    s = _str(v).replace("﷼", "").replace(",", "").replace(" ", "")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def _parse_date(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = _str(v)
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s.split()[0][:10], fmt).date()
        except ValueError:
            continue
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt.date() if pd.notna(dt) else None


def _iso(d) -> str:
    return d.isoformat() if d else ""


def _c_code(v) -> str:
    m = re.search(r"C-(\d+)", _str(v), re.I)
    return f"C-{int(m.group(1)):04d}" if m else ""


def _cn_code(v) -> str:
    m = re.search(r"CN-(\d+)", _str(v), re.I)
    return f"CN-{int(m.group(1)):05d}" if m else ""


def _el_code(v) -> str:
    m = re.search(r"EL-(\d+)", _str(v), re.I)
    return f"EL-{int(m.group(1)):04d}" if m else ""


def _el_list(v) -> str:
    seen, out = set(), []
    for m in re.finditer(r"EL-(\d+)", _str(v), re.I):
        code = f"EL-{int(m.group(1)):04d}"
        if code not in seen:
            seen.add(code)
            out.append(code)
    return ", ".join(out)


def _c_from_cn(cn: str) -> str:
    m = re.search(r"CN-(\d+)", cn or "", re.I)
    return f"C-{int(m.group(1)):04d}" if m else ""


def _city(v) -> str:
    s = _str(v)
    return "مكة" if "مكة" in s else (s or "مكة")


def _contract_status(v) -> str:
    s = _str(v)
    if "تجديده" in s or s in ("تم تجديده", "مجدد"):
        return "تم تجديده"
    if "منته" in s:
        return "منتهي"
    if "ملغ" in s:
        return "ملغي"
    if "وشك" in s or "قرب" in s:
        return "على وشك الانتهاء"
    return "نشط"


def _elev_status(v) -> str:
    s = _str(v)
    if s in ("فعال", "نشط", ""):
        return "نشط"
    if "توقف" in s:
        return "متوقف"
    if "صيان" in s:
        return "تحت الصيانة"
    return s or "نشط"


def _contract_type(v) -> str:
    s = _str(v)
    if not s or s == "صيانة":
        return "عقد صيانة"
    return s


def _tech_status(v) -> str:
    s = _str(v).lower()
    if "off" in s or "غير" in s:
        return "غير نشط"
    return "متاح"


def _job(v) -> str:
    s = _str(v)
    if "|" in s:
        s = s.split("|")[-1].strip()
    return s or "فني مصاعد"


def _read(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def write_xlsx(path: Path, sheet: str, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=columns)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet, index=False)


def main() -> None:
    clients_df = _read(SRC_CLIENTS)
    contracts_df = _read(SRC_CONTRACTS)
    elev_df = _read(SRC_ELEVATORS)
    techs_df = _read(SRC_TECHS)

    clients: list[dict] = []
    by_code: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    added_from_contracts = 0

    for _, row in clients_df.iterrows():
        code = _c_code(row.get("رقم العميل"))
        name = _str(row.get("اسم العميل")) or _str(row.get("اسم العميل | رقم العميل"))
        if "|" in name:
            name = name.split("|", 1)[0].strip()
        if not code or not name:
            continue
        rec = {
            "رقم العميل": code,
            "الاسم (عربي)": name,
            "اسم العميل": name,
            "رقم الهاتف": _str(row.get("الجوال")),
            "الجوال": _str(row.get("الجوال")),
            "المدينة": _city(row.get("المدينة")),
            "الحي أو المنطقة": _str(row.get("الحي أو المنطقة")),
            "الحي": _str(row.get("الحي أو المنطقة")),
            "العنوان": "",
            "رقم الهوية": _str(row.get("رقم الهوية")),
            "البريد الالكتروني": _str(row.get("البريد الالكتروني")),
            "البريد الإلكتروني": _str(row.get("البريد الالكتروني")),
            "حالة العميل": _str(row.get("حالة العميل")) or "نشط",
            "ملاحظات": _str(row.get("ملاحظات")),
            "نوع المتعاقد": "فرد",
        }
        clients.append(rec)
        by_code[code] = rec
        key = _norm_name(name)
        if key and key not in by_name:
            by_name[key] = rec

    def resolve_customer(name: str, cn: str) -> dict | None:
        key = _norm_name(name)
        if key and key in by_name:
            return by_name[key]
        guessed = _c_from_cn(cn)
        if guessed and guessed in by_code:
            return by_code[guessed]
        return None

    for _, row in contracts_df.iterrows():
        cn = _cn_code(row.get("رقم العقد")) or _cn_code(row.get("اسم العميل ورقم العقد"))
        name = _str(row.get("العملاء"))
        addr = _str(row.get("العنوان"))
        district = _str(row.get("المنطقة"))
        phone = _str(row.get("الجوال"))
        nid = _str(row.get("رقم الهوية"))
        cust = resolve_customer(name, cn)
        if cust:
            if addr and not cust["العنوان"]:
                cust["العنوان"] = addr
            if district and not cust["الحي أو المنطقة"]:
                cust["الحي أو المنطقة"] = district
                cust["الحي"] = district
            if phone and not cust["رقم الهاتف"]:
                cust["رقم الهاتف"] = phone
                cust["الجوال"] = phone
            if nid and not cust["رقم الهوية"]:
                cust["رقم الهوية"] = nid
            continue
        if not name:
            continue
        code = _c_from_cn(cn)
        if not code or code in by_code:
            n = max((int(re.search(r"(\d+)", c).group(1)) for c in by_code), default=0) + 1
            while f"C-{n:04d}" in by_code:
                n += 1
            code = f"C-{n:04d}"
        rec = {
            "رقم العميل": code,
            "الاسم (عربي)": name,
            "اسم العميل": name,
            "رقم الهاتف": phone,
            "الجوال": phone,
            "المدينة": "مكة",
            "الحي أو المنطقة": district,
            "الحي": district,
            "العنوان": addr,
            "رقم الهوية": nid,
            "البريد الالكتروني": "",
            "البريد الإلكتروني": "",
            "حالة العميل": "نشط",
            "ملاحظات": f"أُضيف من ملف العقود {cn}".strip(),
            "نوع المتعاقد": "فرد",
        }
        clients.append(rec)
        by_code[code] = rec
        by_name[_norm_name(name)] = rec
        added_from_contracts += 1

    client_cols = [
        "رقم العميل",
        "الاسم (عربي)",
        "اسم العميل",
        "رقم الهاتف",
        "الجوال",
        "المدينة",
        "الحي أو المنطقة",
        "الحي",
        "العنوان",
        "رقم الهوية",
        "البريد الالكتروني",
        "البريد الإلكتروني",
        "حالة العميل",
        "نوع المتعاقد",
        "ملاحظات",
    ]

    contracts: list[dict] = []
    skipped_contracts = []
    included_without_dates = []
    for _, row in contracts_df.iterrows():
        cn = _cn_code(row.get("رقم العقد")) or _cn_code(row.get("اسم العميل ورقم العقد"))
        name = _str(row.get("العملاء"))
        if not cn:
            skipped_contracts.append({"رقم العقد": cn, "العملاء": name, "سبب": "بدون رقم عقد"})
            continue
        start = _parse_date(row.get("تاريخ بداية العقد")) or _parse_date(row.get("تاريخ التجديد"))
        end = _parse_date(row.get("تاريخ انتهاء العقد"))
        date_fallback = False
        if not start:
            start = FALLBACK_START
            date_fallback = True
        if not end:
            end = start + timedelta(days=365)
            date_fallback = True
        cust = resolve_customer(name, cn)
        if not cust:
            skipped_contracts.append({"رقم العقد": cn, "العملاء": name, "سبب": "لا عميل"})
            continue
        value = _money(row.get("قيمة العقد"))
        if value <= 0:
            value = _money(row.get("ملاحظات"))
        paid = 0.0
        tax_pct = TAX_PCT if value > 0 else 0.0
        tax = round(value * tax_pct / 100.0, 2)
        total = round(value + tax, 2)
        els = _el_list(row.get("رقم المصعد")) or _el_list(row.get("اسم العميل ورقم العقد"))
        status = _contract_status(row.get("حالة العقد"))
        notes_parts = []
        src_note = _str(row.get("ملاحظات"))
        if src_note:
            notes_parts.append(src_note)
        if _money(row.get("قيمة العقد")) <= 0:
            deals = _money(row.get("اجمالي التعاملات"))
            parts_paid = _money(row.get("قيمة المسدد من قطع الغيار"))
            if deals > 0:
                notes_parts.append(f"إجمالي التعاملات في سمارت سويت: {deals:g}")
            if parts_paid > 0:
                notes_parts.append(f"مسدد قطع غيار في سمارت سويت: {parts_paid:g}")
        if date_fallback:
            notes_parts.append(
                "تاريخ البداية/الانتهاء غير موجود في سمارت سويت — وُضع 1/11/2025 ليُحفظ السجل"
            )
            included_without_dates.append({"رقم العقد": cn, "العملاء": name, "حالة العقد": status})
        notes = " | ".join(notes_parts)
        contracts.append(
            {
                "كود العميل": cust["رقم العميل"],
                "اسم العميل": cust["اسم العميل"],
                "العملاء": cust["اسم العميل"],
                "رقم العقد": cn,
                "نوع العقد": _contract_type(row.get("نوع العقد")),
                "تاريخ البداية": _iso(start),
                "تاريخ الانتهاء": _iso(end),
                "تاريخ بداية العقد": _iso(start),
                "تاريخ انتهاء العقد": _iso(end),
                "تكرار الصيانة": _str(row.get("برنامج الصيانة")) or "سنوي",
                "برنامج الصيانة": _str(row.get("برنامج الصيانة")) or "سنوي",
                "قيمة العقد": value,
                "قيمة العقد قبل الضريبة": value,
                "نسبة الضريبة %": tax_pct,
                "الإجمالي شامل الضريبة": total,
                "المبلغ المسدد": paid,
                "المبلغ المتبقي": total,
                "شروط الدفع": "دفعة واحدة",
                "حالة العقد": status,
                "أكواد المصاعد": els,
                "رقم المصعد": els,
                "ملاحظات": notes,
                "المنطقة": _str(row.get("المنطقة")) or cust["الحي أو المنطقة"],
                "العنوان": _str(row.get("العنوان")) or cust["العنوان"],
            }
        )

    contract_cols = [
        "كود العميل",
        "اسم العميل",
        "العملاء",
        "رقم العقد",
        "نوع العقد",
        "تاريخ البداية",
        "تاريخ الانتهاء",
        "تاريخ بداية العقد",
        "تاريخ انتهاء العقد",
        "تكرار الصيانة",
        "برنامج الصيانة",
        "قيمة العقد",
        "قيمة العقد قبل الضريبة",
        "نسبة الضريبة %",
        "الإجمالي شامل الضريبة",
        "المبلغ المسدد",
        "المبلغ المتبقي",
        "شروط الدفع",
        "حالة العقد",
        "أكواد المصاعد",
        "رقم المصعد",
        "ملاحظات",
        "المنطقة",
        "العنوان",
    ]

    by_cn = {r["رقم العقد"]: r for r in contracts}
    elevators: list[dict] = []
    skipped_elev = []
    for _, row in elev_df.iterrows():
        el = _el_code(row.get("رقم المصعد"))
        cn = _cn_code(row.get("رقم العقد")) or _cn_code(row.get("Title")) or _cn_code(
            row.get("Link to Contracts / العقود")
        )
        title = _str(row.get("Title")) or _str(row.get("Link to Contracts / العقود"))
        name = re.sub(r"^CN-\d+\s*", "", title).strip()
        if not el:
            skipped_elev.append({"title": title, "سبب": "بدون رقم مصعد"})
            continue
        contract = by_cn.get(cn or "")
        cust = None
        if contract:
            cust = by_code.get(contract["كود العميل"])
        if not cust:
            cust = resolve_customer(name, cn or "")
        if not cust:
            skipped_elev.append({"رقم المصعد": el, "رقم العقد": cn, "سبب": "لا عميل"})
            continue
        warranty = _str(row.get("حالة الضمان"))
        notes = f"حالة الضمان: {warranty}" if warranty else ""
        elev_type = _str(row.get("نوع المصعد")) or "مصعد ركاب"
        elevators.append(
            {
                "Title": title or f"{cn}  {cust['اسم العميل']}",
                "رقم المصعد": el,
                "كود المصعد": el,
                "كود العميل": cust["رقم العميل"],
                "اسم العميل": cust["اسم العميل"],
                "رقم العقد": cn,
                "Link to Contracts / العقود": title,
                "المبنى": f"{cust['اسم العميل']} — {el}",
                "المدينة": cust["المدينة"],
                "الحي": cust["الحي"],
                "الحي أو المنطقة": cust["الحي أو المنطقة"],
                "نوع المصعد": elev_type,
                "عدد الوقفات": row.get("عدد الوقفات") if pd.notna(row.get("عدد الوقفات")) else "",
                "عدد الطوابق": row.get("عدد الوقفات") if pd.notna(row.get("عدد الوقفات")) else "",
                "الحمولة (كجم)": row.get("الحمولة (كجم)") if pd.notna(row.get("الحمولة (كجم)")) else "",
                "الحمولة": row.get("الحمولة (كجم)") if pd.notna(row.get("الحمولة (كجم)")) else "",
                "حالة المصعد": _elev_status(row.get("حالة المصعد")),
                "الحالة": _elev_status(row.get("حالة المصعد")),
                "حالة الضمان": warranty,
                "ملاحظات": notes,
            }
        )

    elev_cols = [
        "Title",
        "رقم المصعد",
        "كود المصعد",
        "كود العميل",
        "اسم العميل",
        "رقم العقد",
        "Link to Contracts / العقود",
        "المبنى",
        "المدينة",
        "الحي",
        "الحي أو المنطقة",
        "نوع المصعد",
        "عدد الوقفات",
        "عدد الطوابق",
        "الحمولة (كجم)",
        "الحمولة",
        "حالة المصعد",
        "الحالة",
        "حالة الضمان",
        "ملاحظات",
    ]

    techs: list[dict] = []
    for _, row in techs_df.iterrows():
        code = _str(row.get("Technical ID | رقم الفني"))
        m = re.search(r"Tech-\d+", code, re.I)
        code = m.group(0) if m else code
        name = _str(row.get("Technical Name | اسم الفني"))
        if not code or not name:
            continue
        job = _job(row.get("Job Title | المسمى الوظيفي"))
        status_src = _str(row.get("Status | الحالة"))
        techs.append(
            {
                "رقم واسم الفني": f"{code} {name}",
                "Technical ID | رقم الفني": code,
                "رقم الفني": code,
                "Technical Name | اسم الفني": name,
                "اسم الفني": name,
                "Job Title | المسمى الوظيفي": _str(row.get("Job Title | المسمى الوظيفي")),
                "المسمى الوظيفي": job,
                "Status | الحالة": status_src,
                "الحالة": _tech_status(status_src),
                "Notes | ملاحظات": _str(row.get("Notes | ملاحظات")),
                "ملاحظات": _str(row.get("Notes | ملاحظات")),
            }
        )

    tech_cols = [
        "رقم واسم الفني",
        "Technical ID | رقم الفني",
        "رقم الفني",
        "Technical Name | اسم الفني",
        "اسم الفني",
        "Job Title | المسمى الوظيفي",
        "المسمى الوظيفي",
        "Status | الحالة",
        "الحالة",
        "Notes | ملاحظات",
        "ملاحظات",
    ]

    files = {
        "clients": ("العملاء.xlsx", "jama_clients_14_8_2026.xlsx", "العملاء", clients, client_cols),
        "technicians": ("الفنيين.xlsx", "jama_technicians_14_8_2026.xlsx", "الفنيين", techs, tech_cols),
        "elevators": ("المصاعد.xlsx", "jama_elevators_14_8_2026.xlsx", "المصاعد", elevators, elev_cols),
        "contracts": ("العقود.xlsx", "jama_contracts_14_8_2026.xlsx", "العقود", contracts, contract_cols),
    }

    written = []
    for key, (ar_name, en_name, sheet, rows, cols) in files.items():
        for folder in (DESKTOP, DESKTOP_ASCII, REPO):
            folder.mkdir(parents=True, exist_ok=True)
        ar_path = DESKTOP / ar_name
        en_desk = DESKTOP_ASCII / en_name
        en_repo = REPO / en_name
        write_xlsx(ar_path, sheet, rows, cols)
        shutil.copy2(ar_path, en_desk)
        shutil.copy2(ar_path, en_repo)
        written.append(
            {
                "key": key,
                "rows": len(rows),
                "desktop_ar": str(ar_path),
                "desktop_en": str(en_desk),
                "repo": str(en_repo),
            }
        )

    unmatched_cn_to_c = []
    for r in contracts:
        guessed = _c_from_cn(r["رقم العقد"])
        if guessed and guessed != r["كود العميل"]:
            unmatched_cn_to_c.append(
                {"رقم العقد": r["رقم العقد"], "كود العميل": r["كود العميل"], "المتوقع من الرقم": guessed}
            )

    summary = {
        "source": {
            "clients": str(SRC_CLIENTS),
            "contracts": str(SRC_CONTRACTS),
            "elevators": str(SRC_ELEVATORS),
            "technicians": str(SRC_TECHS),
        },
        "counts": {
            "clients_src": int(len(clients_df)),
            "clients_out": len(clients),
            "clients_added_from_contracts": added_from_contracts,
            "contracts_src": int(len(contracts_df)),
            "contracts_out": len(contracts),
            "contracts_included_without_dates": len(included_without_dates),
            "elevators_src": int(len(elev_df)),
            "elevators_out": len(elevators),
            "elevators_skipped": len(skipped_elev),
            "technicians_out": len(techs),
            "contract_value_sum": round(sum(r["قيمة العقد"] for r in contracts), 2),
            "contract_paid_sum": round(sum(r["المبلغ المسدد"] for r in contracts), 2),
            "contract_total_with_vat": round(sum(r["الإجمالي شامل الضريبة"] for r in contracts), 2),
            "tax_pct": TAX_PCT,
        },
        "skipped_contracts": skipped_contracts,
        "included_without_dates": included_without_dates,
        "skipped_elevators": skipped_elev,
        "cn_not_same_number_as_customer": unmatched_cn_to_c[:40],
        "cn_not_same_number_as_customer_count": len(unmatched_cn_to_c),
        "files": written,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))
    print("written", len(written), "file groups")
    print("summary", SUMMARY)


if __name__ == "__main__":
    main()
