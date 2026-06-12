#!/usr/bin/env python3
"""إنشاء static/templates/clients_template.xlsx — نموذج استيراد العملاء."""
import os
import zipfile
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'static', 'templates', 'clients_template.xlsx')

HEADERS = [
    'الاسم (عربي)',
    'المدينة',
    'الحي',
    'رقم الهاتف',
    'البريد الإلكتروني',
    'اسم المسؤول',
    'نوع المتعاقد',
    'رقم هوية المتعاقد',
    'رقم السجل التجاري',
]
EXAMPLE = []  # صف العناوين فقط — المستخدم يضيف بياناته


def col_letter(n):
    s = ''
    while n >= 0:
        s = chr(65 + (n % 26)) + s
        n = n // 26 - 1
    return s


def sheet_xml(rows):
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    lines.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
    lines.append('<sheetData>')
    for ri, row in enumerate(rows, start=1):
        lines.append(f'<row r="{ri}">')
        for ci, val in enumerate(row):
            ref = f'{col_letter(ci)}{ri}'
            text = escape(str(val))
            lines.append(
                f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'
            )
        lines.append('</row>')
    lines.append('</sheetData></worksheet>')
    return ''.join(lines)


def build_xlsx(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = [HEADERS]
    if EXAMPLE:
        rows.append(EXAMPLE)
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
        z.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Clients" sheetId="1" r:id="rId1"/></sheets>
</workbook>''')
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml(rows))
    print(f'[OK] {path}')


if __name__ == '__main__':
    build_xlsx(OUT)
