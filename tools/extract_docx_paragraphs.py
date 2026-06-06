"""Extract paragraphs from CN0000.docx for exact HTML reproduction."""
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
path = Path(r'c:\Users\Mohqawashy\Downloads\CN0000_extracted\word\document.xml')
root = ET.parse(path).getroot()
body = root.find('w:body', NS)

for i, p in enumerate(body.findall('w:p', NS)):
    if p.find('w:pPr/' + W + 'sectPr', NS) is not None:
        continue
    ppr = p.find('w:pPr', NS)
    jc = ''
    if ppr is not None:
        j = ppr.find('w:jc', NS)
        if j is not None:
            jc = j.get(W + 'val', '')
        ind = ppr.find('w:ind', NS)
        num = ppr.find('w:numPr', NS)
    else:
        ind = num = None

    runs = []
    for r in p.findall('w:r', NS):
        rpr = r.find('w:rPr', NS)
        bold = rpr is not None and rpr.find('w:b', NS) is not None
        sz = None
        if rpr is not None:
            s = rpr.find('w:sz', NS)
            if s is not None:
                sz = s.get(W + 'val')
        texts = []
        for node in r.iter():
            if node.tag == W + 't' and node.text:
                texts.append(node.text)
            elif node.tag == W + 'tab':
                texts.append('\t')
        if texts:
            runs.append({'bold': bold, 'sz': sz, 'text': ''.join(texts)})

    full = ''.join(x['text'] for x in runs)
    if not full.strip() and not runs:
        print(f'{i:3d}| EMPTY | align={jc}')
        continue
    print(f'{i:3d}| align={jc:5} | {full}')
