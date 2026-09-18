#!/usr/bin/env python3
"""تحويل عقود سمارت سويت + عقود سابقة → ملفات استيراد جما (عقود + إيرادات).

القواعد:
- تاريخ القطع: 2025-11-01 (بداية جما التميز)
- مطابقة ملف السابقة بالاسم → تحصيل مالك سابق
- عقد يبدأ في/بعد القطع وغير موجود في السابقة → تجديد/عقد جما
- المتبقي يُترك على العقد (غير مدفوع) لتحصيل جما لاحقاً
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

CUTOVER = date(2025, 11, 1)
NOTE_PREV = 'تحصيل مالك سابق — قبل/عند استلام جما 1/11/2025'
NOTE_JAMA = 'تحصيل جما (تجديد/عقد بعد الاستلام)'

HEADER_FILL = PatternFill('solid', fgColor='0F3D68')
HEADER_FONT = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
THIN = Border(
    left=Side(style='thin', color='D0D7DE'),
    right=Side(style='thin', color='D0D7DE'),
    top=Side(style='thin', color='D0D7DE'),
    bottom=Side(style='thin', color='D0D7DE'),
)


def _str(v) -> str:
    if v is None:
        return ''
    return str(v).strip()


def _f(v) -> float:
    if v is None or v == '':
        return 0.0
    try:
        return float(str(v).replace(',', '').replace(' ', '').replace('ر.س', ''))
    except ValueError:
        return 0.0


def _parse_date(v):
    if v is None or v == '':
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = _str(v).split()[0]
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _norm_name(name: str) -> str:
    s = ' '.join(_str(name).split())
    for a, b in (
        ('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ى', 'ي'), ('ة', 'ه'),
        ('ؤ', 'و'), ('ئ', 'ي'), ('ال', 'ال'),
    ):
        s = s.replace(a, b)
    s = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', s)
    return ' '.join(s.split())


def _norm_cn(code: str) -> str:
    s = _str(code).upper()
    m = re.search(r'CN\s*-?\s*(\d+)', s)
    if m:
        return f'CN-{int(m.group(1)):05d}'
    m = re.search(r'C\s*-?\s*(\d+)', s)
    if m:
        return f'CN-{int(m.group(1)):05d}'
    return s


def _style_header(ws, headers: list[str]):
    for col, h in enumerate(headers, 1):
        cell = ws.cell(1, col, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = THIN
    ws.freeze_panes = 'A2'
    ws.sheet_view.rightToLeft = True


def _autosize(ws, max_width=42):
    for col in ws.columns:
        letter = col[0].column_letter
        width = 10
        for cell in col[:80]:
            width = max(width, min(max_width, len(_str(cell.value)) + 2))
        ws.column_dimensions[letter].width = width


def load_smart_suite(path: Path) -> list[dict]:
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    headers = [_str(h) for h in rows[0]]
    ix = {h: i for i, h in enumerate(headers)}
    out = []
    for row in rows[1:]:
        if not any(row):
            continue
        code = _norm_cn(row[ix.get('رقم العقد', 1)])
        if not code.startswith('CN-'):
            continue
        name = _str(row[ix.get('العملاء', 2)])
        start = _parse_date(row[ix.get('تاريخ بداية العقد')])
        end = _parse_date(row[ix.get('تاريخ انتهاء العقد')])
        if not start or not end:
            continue
        val = _f(row[ix.get('قيمة العقد')])
        paid = _f(row[ix.get('قيمة المسدد من العقد')]) or _f(row[ix.get('المبلغ المسدد')])
        remain = _f(row[ix.get('المبلغ المتبقي')])
        if remain <= 0 and val > 0:
            remain = max(0.0, round(val - paid, 2))
        out.append({
            'code': code,
            'name': name,
            'name_key': _norm_name(name),
            'building': _str(row[ix.get('اسم المبنى')]),
            'elevators': _str(row[ix.get('رقم المصعد')]),
            'elevator_count': row[ix.get('عدد المصاعد')],
            'address': _str(row[ix.get('العنوان')]),
            'district': _str(row[ix.get('المنطقة')]),
            'phone': _str(row[ix.get('الجوال')]),
            'national_id': _str(row[ix.get('رقم الهوية')]),
            'contract_type': _str(row[ix.get('نوع العقد')]) or 'صيانة',
            'frequency': _str(row[ix.get('برنامج الصيانة')]) or 'سنوي',
            'start': start,
            'end': end,
            'renew_date': _parse_date(row[ix.get('تاريخ التجديد')]),
            'value': val,
            'paid': paid,
            'remain': remain,
            'due_date': _parse_date(row[ix.get('تاريخ الاستحقاق')]),
            'status': _str(row[ix.get('حالة العقد')]) or 'ساري',
            'notes': _str(row[ix.get('ملاحظات')]),
        })
    return out


def load_previous(path: Path) -> list[dict]:
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    # header row index 3
    headers = [_str(h) for h in rows[3]]
    ix = {h: i for i, h in enumerate(headers)}
    out = []
    for row in rows[4:]:
        if not row or row[1] is None:
            continue
        name = _str(row[ix.get('اسم العميل')])
        out.append({
            'old_code': _str(row[ix.get('رقم العقد')]),
            'name': name,
            'name_key': _norm_name(name),
            'value': _f(row[ix.get('قيمة التعاقد')]),
            'received': _f(row[ix.get('المستلم من قيمة العقد')]),
            'remain': _f(row[ix.get('المتبقي من قيمة العقد')]),
            'contract_date': _parse_date(row[ix.get('تاريخ العقد')]),
            'jama_start': _parse_date(row[ix.get('بداية جما التميز')]) or CUTOVER,
            'end': _parse_date(row[ix.get('تاريخ الانتهاء')]),
            'status': _str(row[ix.get('حالة العقد')]) or _str(row[ix.get('الحاله')]),
        })
    return out


def _name_score(a: str, b: str) -> float:
    """تشابه أسماء عربية مبسّط (توكينات مشتركة)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.92
    ta = set(a.split())
    tb = set(b.split())
    # تجاهل كلمات قصيرة شائعة
    stop = {'بن', 'ابن', 'ال', 'و', 'والدته', 'اخو', 'اخوه', 'سابقا', 'الان', 'القديم', 'فندق', 'المعرض'}
    ta = {t for t in ta if len(t) > 2 and t not in stop}
    tb = {t for t in tb if len(t) > 2 and t not in stop}
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return inter / max(len(ta), len(tb))


def classify(contracts: list[dict], previous: list[dict]) -> list[dict]:
    # index previous by normalized name (first wins; keep list for ambiguity)
    by_name: dict[str, list[dict]] = {}
    for p in previous:
        by_name.setdefault(p['name_key'], []).append(p)
    prev_all = list(previous)

    used_prev: set[int] = set()
    enriched = []
    for c in contracts:
        matches = by_name.get(c['name_key']) or []
        # fuzzy contains if exact missing
        if not matches:
            for key, items in by_name.items():
                if not key or not c['name_key']:
                    continue
                if c['name_key'] in key or key in c['name_key']:
                    matches = items
                    break
        if not matches:
            scored = []
            for cand in prev_all:
                sc = _name_score(c['name_key'], cand['name_key'])
                if sc >= 0.6:
                    scored.append((sc, cand))
            scored.sort(key=lambda x: -x[0])
            matches = [x[1] for x in scored[:3]]

        prev = None
        for cand in matches:
            oid = id(cand)
            if oid not in used_prev:
                prev = cand
                used_prev.add(oid)
                break

        prev_received = float(prev['received']) if prev else 0.0
        start = c['start']
        paid = float(c['paid'] or 0)
        remain = float(c['remain'] or 0)

        if prev:
            # عميل من محفظة الاستلام: التحصيل المسجّل عند السابقة = مالك سابق
            # أي زيادة في المسدد بسماارت فوق المستلم السابق ≈ تحصيل جما لاحقاً
            settlement_prev = min(paid, prev_received) if paid > 0 else prev_received
            if settlement_prev <= 0 and prev_received > 0:
                settlement_prev = prev_received
            jama_collected = max(0.0, round(paid - settlement_prev, 2))
            # إن بدأ العقد بعد القطع ولم يُطابق متبقٍ من السابقة بقوة — ما زال مرتبطاً بالمحفظة القديمة
            bucket = 'legacy_matched'
            if start >= CUTOVER and prev_received <= 0 and paid > 0:
                bucket = 'jama_renewal'
                settlement_prev = 0.0
                jama_collected = paid
        elif start >= CUTOVER:
            bucket = 'jama_renewal'
            settlement_prev = 0.0
            jama_collected = paid
        else:
            bucket = 'legacy_unmatched'
            settlement_prev = paid
            jama_collected = 0.0

        # حالة العرض في النظام
        status = 'نشط'
        if c['status'] in ('منتهي', 'ملغي'):
            status = c['status']
        elif c['end'] and c['end'] < date.today():
            status = 'منتهي'

        notes_bits = []
        if c['notes']:
            notes_bits.append(c['notes'])
        if prev:
            notes_bits.append(f"محفظة سابقة {prev['old_code']} | مستلم سابق {prev_received:g}")
        notes_bits.append(f'قطع جما: {CUTOVER.isoformat()} | تصنيف: {bucket}')

        enriched.append({
            **c,
            'bucket': bucket,
            'prev_code': prev['old_code'] if prev else '',
            'prev_received': prev_received,
            'settlement_prev': round(settlement_prev, 2),
            'jama_collected': round(jama_collected, 2),
            'remain': round(remain, 2),
            'status_out': status,
            'notes_out': ' | '.join(notes_bits),
            'matched_prev': bool(prev),
        })
    return enriched


def write_contracts(path: Path, rows: list[dict]):
    headers = [
        'اسم العميل ورقم العقد', 'رقم العقد', 'العملاء', 'اسم المبنى', 'رقم المصعد',
        'عدد المصاعد', 'العنوان', 'المنطقة', 'الجوال', 'رقم الهوية',
        'نوع العقد', 'برنامج الصيانة', 'تاريخ بداية العقد', 'تاريخ انتهاء العقد',
        'قيمة العقد', 'المبلغ المسدد', 'المبلغ المتبقي', 'تاريخ الاستحقاق',
        'حالة العقد', 'ملاحظات', 'تصنيف الاستلام', 'كود السابقة',
        'تسوية مالك سابق', 'تحصيل جما',
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = 'العقود'
    _style_header(ws, headers)
    for i, r in enumerate(rows, 2):
        paid_for_contract = round(r['settlement_prev'] + r['jama_collected'], 2)
        vals = [
            f"{r['code']}  {r['name']}",
            r['code'],
            r['name'],
            r['building'],
            r['elevators'],
            r['elevator_count'],
            r['address'],
            r['district'],
            r['phone'],
            r['national_id'],
            r['contract_type'],
            r['frequency'],
            r['start'],
            r['end'],
            r['value'],
            paid_for_contract,
            r['remain'],
            r['due_date'],
            r['status_out'],
            r['notes_out'],
            r['bucket'],
            r['prev_code'],
            r['settlement_prev'],
            r['jama_collected'],
        ]
        for col, val in enumerate(vals, 1):
            cell = ws.cell(i, col, val)
            cell.border = THIN
            cell.alignment = Alignment(vertical='center', wrap_text=True)
    _autosize(ws)
    wb.save(path)


def write_revenues(path: Path, rows: list[dict]):
    headers = [
        'Title', 'رقم العملية', 'العقود', 'التاريخ', 'نوع الايراد',
        'المبلغ', 'طريقة الدفع', 'ملاحظات', 'مرفقات', 'Status', 'Assigned To',
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = 'الإيرادات'
    _style_header(ws, headers)

    op = 9001
    out_i = 2
    for r in rows:
        # 1) تسوية مالك سابق
        if r['settlement_prev'] > 0:
            rev_date = min(r['start'], CUTOVER) if r['start'] else CUTOVER
            if rev_date > CUTOVER:
                rev_date = CUTOVER
            title = f"{r['code']} {r['name']}"
            vals = [
                title,
                op,
                r['code'],
                rev_date,
                'عقد صيانة',
                r['settlement_prev'],
                'تحويل ملكية',
                NOTE_PREV + (f" | السابقة {r['prev_code']}" if r['prev_code'] else ''),
                '',
                'محصّل',
                '',
            ]
            for col, val in enumerate(vals, 1):
                cell = ws.cell(out_i, col, val)
                cell.border = THIN
            out_i += 1
            op += 1

        # 2) تحصيل جما (تجديد/بعد الاستلام)
        if r['jama_collected'] > 0:
            rev_date = r['start'] if r['start'] and r['start'] >= CUTOVER else CUTOVER
            title = f"{r['code']} {r['name']}"
            rtype = 'تجديد عقد' if r['bucket'] == 'jama_renewal' else 'دفعة عقد'
            vals = [
                title,
                op,
                r['code'],
                rev_date,
                rtype,
                r['jama_collected'],
                'تحصيل',
                NOTE_JAMA,
                '',
                'محصّل',
                '',
            ]
            for col, val in enumerate(vals, 1):
                cell = ws.cell(out_i, col, val)
                cell.border = THIN
            out_i += 1
            op += 1

    _autosize(ws)
    wb.save(path)


def write_summary(path: Path, rows: list[dict], previous: list[dict]):
    lines = []
    lines.append('ملخص تحويل عقود جما — استلام الشركة')
    lines.append(f'تاريخ القطع: {CUTOVER.isoformat()}')
    lines.append('')
    buckets = {}
    for r in rows:
        buckets[r['bucket']] = buckets.get(r['bucket'], 0) + 1
    lines.append(f'عقود سمارت سويت المستوردة: {len(rows)}')
    lines.append(f'عقود سابقة في ملف المحفظة: {len(previous)}')
    lines.append(f'مطابقة مع السابقة: {sum(1 for r in rows if r["matched_prev"])}')
    lines.append('')
    lines.append('التصنيف:')
    for k, v in sorted(buckets.items()):
        lines.append(f'  - {k}: {v}')
    prev_sum = sum(r['settlement_prev'] for r in rows)
    jama_sum = sum(r['jama_collected'] for r in rows)
    remain_sum = sum(r['remain'] for r in rows)
    lines.append('')
    lines.append(f'إجمالي تسوية مالك سابق: {prev_sum:,.2f}')
    lines.append(f'إجمالي تحصيل جما (من الملف): {jama_sum:,.2f}')
    lines.append(f'إجمالي المتبقي على العملاء: {remain_sum:,.2f}')
    lines.append('')
    lines.append('الملفات:')
    lines.append('  04-العقود-معبأ.xlsx  →  python scripts/import_jama_contracts.py ...')
    lines.append('  07-الايرادات-تسوية-وتحصيل.xlsx  →  python scripts/import_jama_revenues.py ...')
    lines.append('')
    lines.append('ترتيب الرفع: عملاء → مصاعد → عقود → إيرادات')
    path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    smart = Path(r'c:\Users\HOME\Downloads\العقود 13_8_2026.xlsx')
    prev_path = Path(r'c:\Users\HOME\Downloads\عقود سابقة.xlsx')
    out_dirs = [
        Path(r'D:\elevator-app\deploy\data\jama_import'),
        Path.home() / 'Desktop' / 'استيراد جما',
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    contracts = load_smart_suite(smart)
    previous = load_previous(prev_path)
    rows = classify(contracts, previous)

    for d in out_dirs:
        write_contracts(d / '04-العقود-معبأ.xlsx', rows)
        write_revenues(d / '07-الايرادات-تسوية-وتحصيل.xlsx', rows)
        write_summary(d / '04-ملخص-العقود.txt', rows, previous)

    print('contracts', len(rows))
    print('matched_prev', sum(1 for r in rows if r['matched_prev']))
    print('settlement_prev', round(sum(r['settlement_prev'] for r in rows), 2))
    print('jama_collected', round(sum(r['jama_collected'] for r in rows), 2))
    print('remain', round(sum(r['remain'] for r in rows), 2))
    from collections import Counter
    print('buckets', dict(Counter(r['bucket'] for r in rows)))
    print('written to:')
    for d in out_dirs:
        print(' ', d)


if __name__ == '__main__':
    main()
