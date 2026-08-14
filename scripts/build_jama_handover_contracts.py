# -*- coding: utf-8 -*-
"""بناء ملف عقود جما بعد تسليم الإدارة في 1/11/2025.

عقود الإدارة السابقة فقط: المتبقي من 1/11 حتى التجديد (أو نهاية العقد القديم)،
غير مدفوع، بدون ضريبة، بدون صفوف تجديد أو عقود جديدة.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

HANDOVER = date(2025, 11, 1)
TODAY = date(2026, 8, 14)
TAX_PCT = 0.0
CHARGE_NOTE = (
    "قيمة العقد غير المحصّلة من الإدارة الجديدة تُحمَّل على حساب د. سمير السباعي"
)

OLD_PATH = Path(r"c:\Users\HOME\OneDrive\Desktop\عقود سابقة.xlsx")
CUR_PATH = Path(r"c:\Users\HOME\Downloads\العقود 14_8_2026.xlsx")
OUT_DESKTOP = Path(r"c:\Users\HOME\OneDrive\Desktop\عقود جما ليفت كور - تسليم 1-11-2025.xlsx")
OUT_DESKTOP_ASCII = Path(r"c:\Users\HOME\OneDrive\Desktop\jama_handover_contracts_1_11_2025.xlsx")
OUT_REPO = Path(r"d:\New folder\elevator-app\deploy\data\jama_import\عقود_تسليم_1_11_2025.xlsx")
OUT_REPO_ASCII = Path(r"d:\New folder\elevator-app\deploy\data\jama_import\jama_handover_contracts_1_11_2025.xlsx")
OUT_JSON = Path(r"d:\New folder\elevator-app\.tmp-handover-summary.json")


def parse_date(v):
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
    s = str(v).strip()
    if not s or s in ("-", "nan", "None"):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.split()[0][:10], fmt).date()
        except Exception:
            pass
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt.date() if pd.notna(dt) else None


def money(v) -> float:
    if v is None:
        return 0.0
    try:
        if pd.isna(v):
            return 0.0
    except Exception:
        pass
    s = str(v).replace("﷼", "").replace(",", "").replace(" ", "").strip()
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def norm_name(s) -> str:
    if s is None:
        return ""
    try:
        if pd.isna(s):
            return ""
    except Exception:
        pass
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")


def code_num(code: str) -> int | None:
    m = re.search(r"(\d+)", str(code or ""))
    return int(m.group(1)) if m else None


def cn_code(n: int) -> str:
    return f"CN-{n:05d}"


def customer_code(n: int) -> str:
    return f"C-{n:04d}"


def elev_codes(text) -> str:
    seen, out = set(), []
    for m in re.finditer(r"EL-(\d+)", str(text or ""), re.I):
        code = f"EL-{int(m.group(1)):04d}"
        if code not in seen:
            seen.add(code)
            out.append(code)
    return ", ".join(out)


def iso(d: date | None) -> str:
    return d.isoformat() if d else ""


def round2(v: float) -> float:
    return round(float(v or 0), 2)


def prorate(value: float, start: date | None, end: date | None, from_d: date, to_d: date) -> float:
    if not start or not end or to_d <= from_d or value <= 0:
        return 0.0
    total_days = max((end - start).days, 1)
    use_days = max((to_d - from_d).days, 0)
    return round2(value * use_days / total_days)


def contract_type_ui(raw: str) -> str:
    s = (raw or "").strip()
    if s == "صيانة":
        return "عقد صيانة"
    if s == "تركيب":
        return "عقد تركيب"
    return s or "عقد صيانة"


def load_old() -> list[dict]:
    raw = pd.read_excel(OLD_PATH, header=None)
    header_row = None
    for i, row in raw.iterrows():
        vals = [str(x).strip() if pd.notna(x) else "" for x in row.tolist()]
        if any("رقم العقد" in v for v in vals) and any("اسم العميل" in v for v in vals):
            header_row = i
            break
    headers = [str(x).strip() if pd.notna(x) else f"col{j}" for j, x in enumerate(raw.iloc[header_row].tolist())]
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = headers
    recs = []
    for _, r in df.iterrows():
        name = str(r.get("اسم العميل") or "").strip()
        code = str(r.get("رقم العقد") or "").strip()
        if not name or name in ("nan", "None") or "إجمالي" in name or "اجمالي" in name:
            continue
        n = code_num(code)
        if n is None:
            continue
        recs.append(
            {
                "old_code": code,
                "n": n,
                "name": name,
                "area": str(r.get("المنطقة") or "").strip(),
                "n_el": str(r.get("عدد المصاعد") or "").strip(),
                "value": money(r.get("قيمة التعاقد")),
                "collected": money(r.get("المستلم من قيمة العقد")),
                "remaining_pay": money(r.get("المتبقي من قيمة العقد")),
                "start": parse_date(r.get("تاريخ العقد")),
                "jama_start": parse_date(r.get("بداية جما التميز")) or HANDOVER,
                "end": parse_date(r.get("تاريخ الانتهاء")),
                "remaining_value": money(r.get("قيمة المدة المتبقية")),
            }
        )
    return recs


def load_cur() -> list[dict]:
    df = pd.read_excel(CUR_PATH)
    recs = []
    for _, r in df.iterrows():
        code = str(r.get("رقم العقد") or "").strip()
        n = code_num(code)
        if n is None:
            continue
        notes = r.get("ملاحظات")
        recs.append(
            {
                "code": code if str(code).upper().startswith("CN-") else cn_code(n),
                "n": n,
                "name": str(r.get("العملاء") or "").strip(),
                "el": elev_codes(r.get("رقم المصعد")),
                "n_el": str(r.get("عدد المصاعد") or "").strip(),
                "area": str(r.get("المنطقة") or "").strip(),
                "address": str(r.get("العنوان") or "").strip() if pd.notna(r.get("العنوان")) else "",
                "ctype": str(r.get("نوع العقد") or "").strip(),
                "freq": (str(r.get("برنامج الصيانة") or "سنوي").strip() or "سنوي"),
                "start": parse_date(r.get("تاريخ بداية العقد")),
                "end": parse_date(r.get("تاريخ انتهاء العقد")),
                "renew": parse_date(r.get("تاريخ التجديد")),
                "value": money(r.get("قيمة العقد")),
                "paid": money(r.get("المبلغ المسدد")),
                "remain": money(r.get("المبلغ المتبقي")),
                "notes": str(notes).strip() if pd.notna(notes) else "",
            }
        )
    return recs


def is_same_period(old: dict, cur: dict) -> bool:
    if not (old.get("start") and old.get("end") and cur.get("start") and cur.get("end")):
        return False
    return abs((cur["start"] - old["start"]).days) <= 10 and abs((cur["end"] - old["end"]).days) <= 10


def is_renewal(old: dict, cur: dict) -> bool:
    if not cur.get("start") or not old.get("end"):
        return False
    if is_same_period(old, cur):
        return False
    # تجديد = فترة جديدة تبدأ عند نهاية القديم أو بعدها (سماح 21 يوماً للتجديد المبكر)
    return cur["start"] >= (old["end"] - timedelta(days=21))


def leftover_end_for(old: dict, cur: dict | None, renewed: bool) -> date | None:
    old_end = old.get("end")
    if not old_end:
        return None
    if renewed and cur and cur.get("start"):
        if cur["start"] < old_end:
            return cur["start"]
        return old_end
    return old_end


def status_for_end(end: date | None, renewed: bool) -> str:
    if renewed:
        return "تم تجديده"
    if end and end < TODAY:
        return "منتهي"
    if end and (end - TODAY).days <= 30:
        return "على وشك الانتهاء"
    return "نشط"


def make_row(
    *,
    code: str,
    customer_n: int,
    name: str,
    ctype: str,
    start: date,
    end: date,
    freq: str,
    value: float,
    paid: float,
    status: str,
    elev: str,
    notes: str,
    area: str,
    address: str,
    classification: str,
    source_old: str,
    source_cur: str,
) -> dict:
    value = round2(value)
    paid = round2(paid)
    tax = round2(value * TAX_PCT / 100.0)
    total = round2(value + tax)
    return {
        "رقم العقد": code,
        "كود العميل": customer_code(customer_n),
        "اسم العميل": name,
        "العملاء": name,
        "نوع العقد": contract_type_ui(ctype),
        "تاريخ بداية العقد": iso(start),
        "تاريخ انتهاء العقد": iso(end),
        "تاريخ البداية": iso(start),
        "تاريخ الانتهاء": iso(end),
        "تكرار الصيانة": freq or "سنوي",
        "برنامج الصيانة": freq or "سنوي",
        "قيمة العقد": value,
        "قيمة العقد قبل الضريبة": value,
        "نسبة الضريبة %": TAX_PCT,
        "الإجمالي شامل الضريبة": total,
        "المبلغ المسدد": paid,
        "المبلغ المتبقي": round2(max(value - paid, 0)),
        "شروط الدفع": "دفعة واحدة",
        "حالة العقد": status,
        "أكواد المصاعد": elev,
        "رقم المصعد": elev.replace(", ", " | ") if elev else "",
        "ملاحظات": notes,
        "المنطقة": area,
        "العنوان": address,
        "التصنيف": classification,
        "مصدر قديم": source_old,
        "مصدر حالي": source_cur,
    }


def build() -> tuple[list[dict], dict]:
    old_recs = load_old()
    cur_recs = load_cur()
    old_by_n = {o["n"]: o for o in old_recs}
    cur_by_n: dict[int, dict] = {}
    extras_same_n: list[dict] = []
    for c in cur_recs:
        if c["n"] in cur_by_n:
            extras_same_n.append(c)
        else:
            cur_by_n[c["n"]] = c

    rows: list[dict] = []
    stats = {
        "old": len(old_recs),
        "cur": len(cur_recs),
        "leftover_renewed": 0,
        "leftover_running": 0,
        "leftover_ended": 0,
        "renewals": 0,
        "new_only": 0,
        "skipped_zero_days": 0,
        "unmatched_old": [],
        "flags": [],
    }

    used_cur = set()

    for n, old in sorted(old_by_n.items()):
        cur = cur_by_n.get(n)
        name = (cur["name"] if cur and cur.get("name") else old["name"])
        area = (cur["area"] if cur and cur.get("area") else old.get("area") or "")
        address = cur.get("address") if cur else ""
        elev = cur.get("el") if cur else ""
        ctype = cur.get("ctype") if cur else "صيانة"
        freq = cur.get("freq") if cur else "سنوي"
        renewed = bool(cur) and is_renewal(old, cur)
        same = bool(cur) and is_same_period(old, cur)

        start_l = HANDOVER
        end_l = leftover_end_for(old, cur, renewed)
        if not end_l:
            stats["unmatched_old"].append({"n": n, "name": old["name"], "reason": "لا تاريخ نهاية"})
            continue
        if end_l <= start_l:
            stats["skipped_zero_days"] += 1
            stats["flags"].append(f"C-{n:03d} بدون أيام متبقية بعد 1/11")
            if cur:
                used_cur.add(n)
            continue

        value_l = prorate(old["value"], old["start"], old["end"], start_l, end_l)
        if value_l <= 0 and old["value"] > 0:
            value_l = round2(old.get("remaining_value") or 0)
            if renewed and old.get("end") and old["end"] > end_l and old.get("remaining_value"):
                full_days = max((old["end"] - HANDOVER).days, 1)
                value_l = round2(old["remaining_value"] * (end_l - HANDOVER).days / full_days)

        st = status_for_end(end_l, renewed)
        if renewed:
            klass = "متبقي حتى التجديد — غير مدفوع"
            stats["leftover_renewed"] += 1
        elif end_l < TODAY:
            klass = "متبقي من عقد قديم — منتهي غير مدفوع"
            stats["leftover_ended"] += 1
        else:
            klass = "متبقي من عقد قديم — ساري غير مدفوع"
            stats["leftover_running"] += 1

        note_bits = [
            "فترة متبقية بعد تسليم الإدارة في 1/11/2025",
            "القيمة محصّلة من الإدارة السابقة وغير محصّلة للإدارة الحالية",
            CHARGE_NOTE,
            f"أصل {old['old_code']} من {iso(old['start'])} إلى {iso(old['end'])} قيمة {round2(old['value'])}",
            f"المتبقي المحسوب من {iso(start_l)} إلى {iso(end_l)}",
        ]
        if cur and cur.get("notes"):
            note_bits.append(cur["notes"])
        rows.append(
            make_row(
                code=cn_code(n),
                customer_n=n,
                name=name,
                ctype=ctype,
                start=start_l,
                end=end_l,
                freq=freq,
                value=value_l,
                paid=0.0,
                status=st,
                elev=elev,
                notes=" | ".join(note_bits),
                area=area,
                address=address or "",
                classification=klass,
                source_old=old["old_code"],
                source_cur=cur["code"] if cur else "",
            )
        )

        if renewed and cur:
            used_cur.add(n)
            # التجديدات لا تُدرج — الملف للعقود القديمة فقط
            year = cur["start"].year if cur.get("start") else TODAY.year
            gap = (cur["start"] - end_l).days if end_l else 0
            if gap > 45:
                stats["flags"].append(
                    f"{cn_code(n)} فجوة {gap} يوماً بين نهاية المتبقي {iso(end_l)} وبداية التجديد {iso(cur['start'])}"
                )
        elif cur:
            used_cur.add(n)
            if not same and not renewed:
                stats["flags"].append(
                    f"CN-{n:05d} تواريخ لا تطابق القديم تماماً "
                    f"(قديم {iso(old.get('start'))}→{iso(old.get('end'))} / "
                    f"حالي {iso(cur.get('start'))}→{iso(cur.get('end'))}) — عُومل كنفس العقد"
                )

    for c in cur_recs:
        if c["n"] in used_cur and c is cur_by_n.get(c["n"]):
            continue
        # عقود جديدة أو صفوف إضافية بنفس الرقم (نادرة)
        already = c["n"] in used_cur
        if already:
            # صف إضافي لعميل/عقد مختلف بنفس الرقم؟ نتركه كعقد جديد بكود كما هو إن لم يُستخدم
            stats["flags"].append(f"صف حالي إضافي {c['code']} {c['name']} — لم يُدمج تلقائياً")
            continue
        used_cur.add(c["n"])
        if c.get("start") and c["start"] < HANDOVER:
            # عقد حالي بدأ قبل التسليم وليس له أصل في ملف العقود السابقة
            end_l = c.get("end")
            if end_l and end_l > HANDOVER:
                value_l = prorate(c["value"], c["start"], c["end"], HANDOVER, end_l)
                st = status_for_end(end_l, False)
                rows.append(
                    make_row(
                        code=cn_code(c["n"]),
                        customer_n=c["n"],
                        name=c["name"],
                        ctype=c.get("ctype") or "صيانة",
                        start=HANDOVER,
                        end=end_l,
                        freq=c.get("freq") or "سنوي",
                        value=value_l,
                        paid=0.0,
                        status=st,
                        elev=c.get("el") or "",
                        notes=(
                            "عقد ظاهر في الملف الحالي بدأ قبل 1/11/2025 وليس في ملف العقود السابقة | "
                            "عُومل كمتبقي غير مدفوع من تاريخ التسليم | "
                            + CHARGE_NOTE
                            + (" | " + c["notes"] if c.get("notes") else "")
                        ).strip(" |"),
                        area=c.get("area") or "",
                        address=c.get("address") or "",
                        classification="متبقي بدون أصل في ملف العقود السابقة — غير مدفوع",
                        source_old="",
                        source_cur=c["code"],
                    )
                )
                stats["leftover_running" if end_l >= TODAY else "leftover_ended"] += 1
                stats["flags"].append(f"{c['code']} بدأ قبل التسليم ولم يُوجد في العقود السابقة")
                continue
        # عقود الإدارة الحالية الجديدة — خارج هذا الملف
        continue

    stats["out_rows"] = len(rows)
    stats["leftover_value_sum"] = round2(
        sum(r["قيمة العقد"] for r in rows if "متبقي" in r["التصنيف"])
    )
    stats["renewal_value_sum"] = round2(
        sum(r["قيمة العقد"] for r in rows if r["التصنيف"] == "تجديد من الإدارة الحالية")
    )
    stats["new_value_sum"] = round2(
        sum(r["قيمة العقد"] for r in rows if r["التصنيف"] == "عقد جديد من الإدارة الحالية")
    )
    stats["extras_same_n"] = [
        {"code": x["code"], "name": x["name"], "start": iso(x.get("start"))} for x in extras_same_n
    ]
    return rows, stats


def write_xlsx(rows: list[dict], stats: dict) -> None:
    # ورقة أولى بأسماء أعمدة الواجهة + سكربت السيرفر معاً
    import_cols = [
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
        "التصنيف",
    ]
    review_cols = [
        "التصنيف",
        "رقم العقد",
        "كود العميل",
        "اسم العميل",
        "تاريخ بداية العقد",
        "تاريخ انتهاء العقد",
        "قيمة العقد",
        "المبلغ المسدد",
        "المبلغ المتبقي",
        "حالة العقد",
        "مصدر قديم",
        "مصدر حالي",
        "رقم المصعد",
        "المنطقة",
        "ملاحظات",
    ]
    df = pd.DataFrame(rows)
    summary = pd.DataFrame(
        [
            ["تاريخ تسليم الإدارة", "2025-11-01"],
            ["تاريخ الملف الحالي", "2026-08-14"],
            ["عقود قديمة في الملف السابق", stats["old"]],
            ["عقود في الملف الحالي", stats["cur"]],
            ["صفوف الاستيراد الناتجة", stats["out_rows"]],
            ["متبقي حتى التجديد (غير مدفوع)", stats["leftover_renewed"]],
            ["متبقي ساري غير مجدّد (غير مدفوع)", stats["leftover_running"]],
            ["متبقي منتهي غير مجدّد (غير مدفوع)", stats["leftover_ended"]],
            ["تجديدات الإدارة الحالية", stats["renewals"]],
            ["عقود جديدة (لا أصل قديم)", stats["new_only"]],
            ["تخطي صفر أيام بعد 1/11", stats["skipped_zero_days"]],
            ["مجموع قيمة المتبقي (قبل الضريبة)", stats["leftover_value_sum"]],
            ["مجموع قيمة التجديدات (قبل الضريبة)", stats["renewal_value_sum"]],
            ["مجموع قيمة العقود الجديدة (قبل الضريبة)", stats["new_value_sum"]],
        ],
        columns=["البند", "القيمة"],
    )
    guide = pd.DataFrame(
        [
            ["الهدف", "عقود الإدارة السابقة فقط بعد التسليم في 1/11/2025 — بدون تجديدات وبدون عقود جديدة"],
            [
                "العقد القديم",
                "يبدأ 1/11/2025 وينتهي عند تجديد الإدارة الحالية (أو نهاية العقد القديم إن لم يُجدَّد). القيمة = حصة الفترة المتبقية. المبلغ المسدد = 0. القيمة غير المحصّلة من الإدارة الجديدة تُحمَّل على حساب د. سمير السباعي (مثبّت في الملاحظات).",
            ],
            [
                "المبالغ",
                "بدون ضريبة. قيمة العقد = الإجمالي، ونسبة الضريبة 0. لا تُضاف 15٪.",
            ],
            [
                "الاستيراد",
                "ورقة «العقود» الأولى جاهزة للواجهة ولسكربت السيرفر. الأفضل: bash deploy/import_jama_contracts_tenant.sh",
            ],
        ],
        columns=["العنصر", "الشرح"],
    )

    for path in (OUT_DESKTOP, OUT_REPO):
        path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df[import_cols].to_excel(writer, index=False, sheet_name="العقود")
            df[review_cols].to_excel(writer, index=False, sheet_name="مراجعة")
            summary.to_excel(writer, index=False, sheet_name="ملخص")
            guide.to_excel(writer, index=False, sheet_name="دليل")
        print("WROTE", path)
    shutil.copy2(OUT_DESKTOP, OUT_DESKTOP_ASCII)
    shutil.copy2(OUT_REPO, OUT_REPO_ASCII)
    print("WROTE", OUT_DESKTOP_ASCII)
    print("WROTE", OUT_REPO_ASCII)


def main() -> int:
    rows, stats = build()
    write_xlsx(rows, stats)
    OUT_JSON.write_text(json.dumps({"stats": stats, "sample": rows[:8]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ROWS", len(rows))
    print("leftover_renewed", stats["leftover_renewed"])
    print("leftover_running", stats["leftover_running"])
    print("leftover_ended", stats["leftover_ended"])
    print("renewals", stats["renewals"])
    print("new_only", stats["new_only"])
    print("leftover_value", stats["leftover_value_sum"])
    print("renewal_value", stats["renewal_value_sum"])
    print("new_value", stats["new_value_sum"])
    print("flags", len(stats["flags"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
