#!/usr/bin/env python3
"""ملفات Excel جاهزة لاستيراد سيناريو مكة الوهمي من شاشات البرنامج.

  python scripts/build_demo_makkah_xlsx.py

المخرجات: deploy/data/demo_makkah/
  1) العملاء ثم 2) المصاعد ثم 3) العقود ثم 4) المخزن
لا تستورد على مستأجر jama الحقيقي — استخدم demo أو حساب تجربة.
"""
from __future__ import annotations

import os
import zipfile
from datetime import date, timedelta
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, 'deploy', 'data', 'demo_makkah')
TODAY = date.today()


def d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


CLIENTS = [
    ('DEMO-01', 'برج زمزم', 'العزيزية', 'شارع إبراهيم الخليل، برج زمزم', '0501111001', '21.4038', '39.8765', 'مشرف المبنى'),
    ('DEMO-02', 'مجمع النخيل', 'الرصيفة', 'طريق مكة المدينة، مجمع النخيل', '0501111002', '21.4368', '39.8085', 'مدير العقار'),
    ('DEMO-03', 'فندق الأندلس', 'العابدية', 'حي العبدية، شارع إبراهيم الخليل', '0501111003', '21.3889', '39.8217', 'مهندس الصيانة'),
    ('DEMO-04', 'مستشفى السلام', 'النزهة', 'شارع النزهة، مستشفى السلام الطبي', '0501111004', '21.4256', '39.8522', 'مدير الخدمات'),
    ('DEMO-05', 'برج المملكة', 'الروضة', 'حي الروضة، برج المملكة التجاري', '0501111005', '21.3925', '39.8843', 'مسؤول العقود'),
    ('DEMO-06', 'مجمع التجارة', 'أجياد', 'أجياد، مجمع التجارة، المدخل الشرقي', '0501111006', '21.4188', '39.8274', 'مشرف الأمن'),
    ('DEMO-07', 'مركز الملك عبدالله الطبي', 'العوالي', 'حي العوالي، مركز الملك عبدالله الطبي', '0501111007', '21.3688', '39.8680', 'رئيس الصيانة'),
    ('DEMO-08', 'برج الفيصلية', 'الزاهر', 'حي الزاهر، برج الفيصلية', '0501111008', '21.4442', '39.8228', 'مدير البرج'),
    ('DEMO-09', 'مجمع الروضة', 'الروضة', 'حي الروضة، مجمع الروضة السكني', '0501111009', '21.3974', '39.8725', 'حارس المجمع'),
    ('DEMO-10', 'فندق مكة كلوك', 'أجياد', 'أجياد، فندق مكة كلوك تاور', '0501111010', '21.4186', '39.8255', 'مدير الهندسة'),
    ('DEMO-11', 'أبراج الصفا', 'الشوقية', 'حي الشوقية، أبراج الصفا', '0501111011', '21.3654', '39.8248', 'مشرف المبنى'),
    ('DEMO-12', 'مجمع الكعكية', 'الكعكية', 'حي الكعكية، مجمع الكعكية', '0501111012', '21.3782', '39.7968', 'مدير الأملاك'),
    ('DEMO-13', 'مستشفى النور', 'الشهداء', 'حي الشهداء، مستشفى النور التخصصي', '0501111013', '21.4528', '39.8465', 'مهندس الأجهزة'),
    ('DEMO-14', 'برج الصفا التجاري', 'الشوقية', 'حي الشوقية، برج الصفا التجاري', '0501111014', '21.3712', '39.8310', 'مدير التشغيل'),
    ('DEMO-15', 'إسكان العتيبية', 'العتيبية', 'حي العتيبية، إسكان العتيبية', '0501111015', '21.4386', '39.7988', 'مشرف الإسكان'),
    ('DEMO-16', 'فندق جرول بلازا', 'جرول', 'حي جرول، فندق جرول بلازا', '0501111016', '21.4308', '39.8142', 'مدير الفندق'),
    ('DEMO-17', 'مجمع الهنداوية', 'الهنداوية', 'حي الهنداوية، مجمع الهنداوية', '0501111017', '21.4235', '39.8048', 'مسؤول الصيانة'),
    ('DEMO-18', 'إسكان جامعة أم القرى', 'العابدية', 'العابدية، إسكان جامعة أم القرى', '0501111018', '21.3298', '39.9522', 'إدارة الإسكان'),
    ('DEMO-19', 'أبراج البيت — إقامة', 'أجياد', 'أجياد، أبراج البيت', '0501111019', '21.4197', '39.8262', 'مهندس المصاعد'),
    ('DEMO-20', 'مجمع التنعيم', 'التنعيم', 'حي التنعيم، مجمع التنعيم', '0501111020', '21.4846', '39.8018', 'حارس المجمع'),
    ('DEMO-21', 'برج ولي العهد', 'ولي العهد', 'حي ولي العهد، برج ولي العهد', '0501111021', '21.3724', '39.8496', 'مشرف البرج'),
    ('DEMO-22', 'مجمع العدل', 'العدل', 'حي العدل، مجمع العدل', '0501111022', '21.4418', '39.8784', 'مدير المجمع'),
]

# (customer_index, code, building, type, brand, kg, floors)
ELEVATORS = [
    (0, 'EL-D124', 'برج زمزم — ركاب 1', 'مصعد ركاب', 'Otis', 1000, 15),
    (0, 'EL-D125', 'برج زمزم — خدمة', 'مصعد بضائع', 'Schindler', 2000, 8),
    (1, 'EL-D087', 'مجمع النخيل A', 'مصعد ركاب', 'Kone', 800, 10),
    (1, 'EL-D088', 'مجمع النخيل B', 'مصعد ركاب', 'Otis', 800, 10),
    (2, 'EL-D201', 'فندق الأندلس — ركاب', 'مصعد ركاب', 'Mitsubishi', 630, 12),
    (3, 'EL-D033', 'مستشفى السلام — طبي', 'مصعد مستشفى', 'Otis', 1600, 8),
    (3, 'EL-D034', 'مستشفى السلام — ركاب', 'مصعد ركاب', 'Otis', 1000, 8),
    (4, 'EL-D156', 'برج المملكة', 'مصعد ركاب', 'Kone', 1000, 20),
    (5, 'EL-D091', 'مجمع التجارة', 'مصعد ركاب', 'Schindler', 1000, 6),
    (6, 'EL-D044', 'الملك عبدالله — ركاب', 'مصعد ركاب', 'Otis', 630, 7),
    (6, 'EL-D045', 'الملك عبدالله — طبي', 'مصعد مستشفى', 'Kone', 1600, 10),
    (7, 'EL-D178', 'برج الفيصلية', 'مصعد ركاب', 'Kone', 1000, 18),
    (8, 'EL-D220', 'مجمع الروضة', 'مصعد ركاب', 'Otis', 800, 9),
    (9, 'EL-D305', 'مكة كلوك — ركاب 1', 'مصعد ركاب', 'Mitsubishi', 1000, 14),
    (9, 'EL-D306', 'مكة كلوك — ركاب 2', 'مصعد ركاب', 'Mitsubishi', 1000, 14),
    (10, 'EL-D310', 'أبراج الصفا A', 'مصعد ركاب', 'Schindler', 800, 11),
    (11, 'EL-D314', 'مجمع الكعكية', 'مصعد ركاب', 'Otis', 630, 7),
    (12, 'EL-D318', 'مستشفى النور', 'مصعد مستشفى', 'Kone', 1600, 9),
    (13, 'EL-D322', 'برج الصفا — خدمة', 'مصعد بضائع', 'Otis', 2000, 8),
    (14, 'EL-D326', 'إسكان العتيبية 1', 'مصعد ركاب', 'Kone', 630, 6),
    (14, 'EL-D327', 'إسكان العتيبية 2', 'مصعد ركاب', 'Kone', 630, 6),
    (15, 'EL-D330', 'جرول بلازا', 'مصعد ركاب', 'Mitsubishi', 800, 10),
    (16, 'EL-D334', 'مجمع الهنداوية', 'مصعد ركاب', 'Schindler', 800, 8),
    (17, 'EL-D338', 'إسكان الجامعة', 'مصعد ركاب', 'Otis', 1000, 12),
    (18, 'EL-D342', 'أبراج البيت — ركاب', 'مصعد ركاب', 'Kone', 1600, 18),
    (19, 'EL-D346', 'مجمع التنعيم', 'مصعد ركاب', 'Otis', 630, 5),
    (20, 'EL-D350', 'برج ولي العهد', 'مصعد ركاب', 'Schindler', 800, 14),
    (21, 'EL-D354', 'مجمع العدل', 'مصعد ركاب', 'Mitsubishi', 1000, 9),
]

# (code, client_idx, start_off, end_off, value, status, elev_codes)
CONTRACTS = [
    ('CN-D0001', 0, -300, 65, 48000, 'نشط', 'EL-D124، EL-D125'),
    ('CN-D0002', 1, -200, 165, 36000, 'نشط', 'EL-D087، EL-D088'),
    ('CN-D0003', 2, -400, 330, 72000, 'نشط', 'EL-D201'),
    ('CN-D0004', 3, -150, 215, 96000, 'نشط', 'EL-D033، EL-D034'),
    ('CN-D0005', 4, -100, 265, 54000, 'نشط', 'EL-D156'),
    ('CN-D0006', 0, -335, 7, 42000, 'نشط', 'EL-D124'),
    ('CN-D0007', 1, -358, 12, 38000, 'نشط', 'EL-D087'),
    ('CN-D0008', 2, -340, 18, 55000, 'نشط', 'EL-D201'),
    ('CN-D0009', 5, -360, 28, 32000, 'نشط', 'EL-D091'),
    ('CN-D0010', 6, -355, 15, 41000, 'نشط', 'EL-D044، EL-D045'),
    ('CN-D0011', 8, -500, -30, 28000, 'منتهي', 'EL-D220'),
    ('CN-D0012', 9, -480, -60, 35000, 'منتهي', 'EL-D305'),
]

INVENTORY = [
    ('DEM-001', 'حبل فولاذ 8مم', 'ميكانيكا', 'قطعة', 25, 10, 120, 180, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-002', 'لوحة تحكم Otis', 'كهرباء', 'قطعة', 3, 5, 2800, 4200, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-003', 'باب مصعد ستانلس', 'أبواب', 'قطعة', 1, 3, 4500, 6500, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-004', 'زيت تشحيم 20L', 'تشحيم', 'عبوة', 8, 15, 350, 500, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-005', 'مستشعر مستوى', 'كهرباء', 'قطعة', 2, 8, 180, 280, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-006', 'سلك طوارئ', 'كهرباء', 'قطعة', 12, 10, 95, 150, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-007', 'بكرة باب علوية', 'ميكانيكا', 'قطعة', 0, 4, 620, 950, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-008', 'فلتر هواء', 'ميكانيكا', 'قطعة', 4, 10, 45, 75, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-009', 'مفتاح أمان', 'كهرباء', 'قطعة', 6, 12, 55, 90, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
    ('DEM-010', 'كابل طوارئ 4×16', 'كهرباء', 'قطعة', 1, 5, 220, 340, 'مستودع مكة — العزيزية', 'مورد المصاعد المتحدة'),
]


def col_letter(n: int) -> str:
    s = ''
    while n >= 0:
        s = chr(65 + (n % 26)) + s
        n = n // 26 - 1
    return s


def sheet_xml(rows: list[list]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>',
    ]
    for ri, row in enumerate(rows, start=1):
        lines.append(f'<row r="{ri}">')
        for ci, val in enumerate(row):
            ref = f'{col_letter(ci)}{ri}'
            text = escape(str(val))
            lines.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        lines.append('</row>')
    lines.append('</sheetData></worksheet>')
    return ''.join(lines)


def write_xlsx(path: str, sheet_name: str, rows: list[list]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    name = escape(sheet_name)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>''')
        z.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
        z.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>''')
        z.writestr('xl/workbook.xml', f'''<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="{name}" sheetId="1" r:id="rId1"/></sheets>
</workbook>''')
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml(rows))
    print('[OK]', path, len(rows) - 1, 'rows')


def main() -> None:
    client_rows = [[
        'رقم العميل', 'الاسم (عربي)', 'المدينة', 'الحي', 'العنوان',
        'رقم الهاتف', 'البريد الإلكتروني', 'اسم المسؤول', 'نوع المتعاقد',
        'رقم هوية المتعاقد', 'رقم السجل التجاري',
    ]]
    for code, name, district, address, phone, _lat, _lng, contact in CLIENTS:
        client_rows.append([
            code, name, 'مكة المكرمة', district, address, phone,
            '', contact, 'شركة', '', '',
        ])
    write_xlsx(os.path.join(OUT_DIR, '01-clients.xlsx'), 'العملاء', client_rows)

    elev_rows = [[
        'كود العميل', 'اسم العميل', 'كود المصعد', 'المبنى', 'المدينة', 'الحي',
        'نوع المصعد', 'الماركة', 'الموديل', 'الحمولة (كجم)', 'عدد الطوابق',
        'الرقم التسلسلي', 'نوع الآلة', 'نوع النظام', 'نوع المحرك',
        'طريقة التشغيل', 'تفاصيل التحكم', 'تاريخ التركيب', 'آخر صيانة',
        'الصيانة القادمة', 'الحالة', 'ملاحظات',
    ]]
    for ci, code, building, etype, brand, kg, floors in ELEVATORS:
        cust = CLIENTS[ci]
        elev_rows.append([
            cust[0], cust[1], code, building, 'مكة المكرمة', cust[2],
            etype, brand, '', str(kg), str(floors),
            '', '', '', '',
            '', '', d(-365 * 3), d(-30),
            d(30), 'نشط', 'بيانات تجريبية — مكة',
        ])
    write_xlsx(os.path.join(OUT_DIR, '02-elevators.xlsx'), 'المصاعد', elev_rows)

    contract_rows = [[
        'رقم العقد', 'كود العميل', 'اسم العميل', 'نوع العقد', 'تاريخ البداية', 'تاريخ الانتهاء',
        'تكرار الصيانة', 'قيمة العقد قبل الضريبة', 'نسبة الضريبة %',
        'الإجمالي شامل الضريبة', 'شروط الدفع', 'حالة العقد', 'أكواد المصاعد', 'ملاحظات',
    ]]
    for code, ci, start, end, value, status, elevs in CONTRACTS:
        cust = CLIENTS[ci]
        tax = round(value * 0.15, 2)
        contract_rows.append([
            code, cust[0], cust[1], 'عقد صيانة', d(start), d(end),
            'شهري', str(value), '15',
            str(value + tax), 'ربع سنوي', status, elevs, 'بيانات تجريبية — مكة',
        ])
    write_xlsx(os.path.join(OUT_DIR, '03-contracts.xlsx'), 'العقود', contract_rows)

    inv_rows = [[
        'كود الصنف', 'اسم الصنف', 'التصنيف', 'الوحدة', 'الرصيد الحالي',
        'الحد الأدنى', 'سعر الشراء', 'سعر البيع', 'موقع التخزين', 'المورد', 'ملاحظات',
    ]]
    for row in INVENTORY:
        inv_rows.append([*row, 'بيانات تجريبية — مكة'])
    write_xlsx(os.path.join(OUT_DIR, '04-inventory.xlsx'), 'المخزن', inv_rows)


if __name__ == '__main__':
    main()
