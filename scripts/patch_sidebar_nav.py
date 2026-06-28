"""استبدال القائمة الجانبية المكررة بـ partial موحّد."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'templates'
REPLACEMENT = """<nav class="sidebar-nav">
{% include 'partials/app_sidebar_nav.html' %}
</nav>"""

SKIP_PARTS = (
    'installation/', 'field', 'login', 'welcome', 'print', 'partials/',
    'invoice-print', 'contract-print', 'purchase-order-print',
    'elevator-estimate-print', 'visit-report', 'fault-report',
)


def should_skip(path: Path) -> bool:
    rel = path.as_posix().replace(str(ROOT.as_posix()) + '/', '')
    return any(part in rel for part in SKIP_PARTS)


def patch_text(text: str) -> tuple[str, bool]:
    if "partials/app_sidebar_nav.html" in text:
        return text, False

    pat_nav = re.compile(r'<nav class="sidebar-nav">.*?</nav>', re.DOTALL)
    if pat_nav.search(text):
        return pat_nav.sub(REPLACEMENT, text, count=1), True

    pat_loose = re.compile(
        r'<div class="nav-section"[^>]*>\s*الرئيسية\s*</div>.*?</nav>',
        re.DOTALL,
    )
    if pat_loose.search(text):
        return pat_loose.sub(REPLACEMENT, text, count=1), True

    return text, False


def main() -> None:
    changed = []
    skipped = []
    for path in sorted(ROOT.rglob('*.html')):
        if should_skip(path):
            skipped.append(path.relative_to(ROOT))
            continue
        text = path.read_text(encoding='utf-8')
        if 'nav-section' not in text and 'sidebar-nav' not in text:
            continue
        new_text, ok = patch_text(text)
        if ok:
            path.write_text(new_text, encoding='utf-8')
            changed.append(path.relative_to(ROOT))
    print(f'Patched {len(changed)} files')
    for p in changed:
        print(f'  + {p}')
    if skipped:
        print(f'Skipped {len(skipped)} (field/install/print)')


if __name__ == '__main__':
    main()
