"""تحديث القوالب: اسم المستخدم، الإعدادات، زر الترس."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1] / "templates"

SETTINGS_OLD = re.compile(
    r'<a class="nav-item" href="#"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">'
    r'<circle cx="8" cy="8" r="6.5"/><path d="M8 5v3l2 1.5"/></svg><span>الإعدادات</span></a>'
)
SETTINGS_NEW = (
    '<a class="nav-item" href="/settings">'
    '<svg viewBox="0 0 24 24" stroke="currentColor" fill="none" stroke-width="1.7" width="16" height="16">'
    '<circle cx="12" cy="12" r="3"/>'
    '<path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>'
    '</svg><span>الإعدادات</span></a>'
)

GEAR_BTN = (
    '<a class="icon-btn" href="/settings" title="الإعدادات">'
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="16" height="16">'
    '<circle cx="12" cy="12" r="3"/>'
    '<path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>'
    '</svg></a>\n      '
)

LOGOUT_BLOCK = (
    '\n    <a href="/logout" class="nav-item" style="margin-top:8px;color:var(--danger,#e04848)">'
    '<svg viewBox="0 0 24 24" stroke="currentColor" fill="none" stroke-width="1.7" width="16" height="16">'
    '<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>'
    '</svg>تسجيل خروج</a>'
)


def patch_file(path: pathlib.Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    text = SETTINGS_OLD.sub(SETTINGS_NEW, text)
    text = text.replace(
        '<div class="sidebar-user-name">محمد القواشي</div><div class="sidebar-user-role">مدير النظام</div>',
        '<div class="sidebar-user-name">{{ current_user_name or "مستخدم" }}</div>'
        '<div class="sidebar-user-role">{{ current_user_role or "" }}</div>',
    )
    text = text.replace('<div class="sidebar-avatar">م</div>', '<div class="sidebar-avatar">{{ current_user_initials }}</div>')
    text = text.replace('<div class="header-avatar">م</div>', '<div class="header-avatar">{{ current_user_initials }}</div>')

    if 'href="/settings" title="الإعدادات"' not in text and '<div class="header-actions">' in text:
        text = text.replace(
            '<div class="header-avatar">{{ current_user_initials }}</div>',
            GEAR_BTN + '<div class="header-avatar">{{ current_user_initials }}</div>',
            1,
        )

    if 'href="/logout"' not in text and '</nav>' in text and 'sidebar-footer' in text:
        text = text.replace('</nav>', LOGOUT_BLOCK + '\n         </nav>', 1)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    count = sum(1 for p in ROOT.rglob("*.html") if patch_file(p))
    print(f"patched {count} templates")


if __name__ == "__main__":
    main()
