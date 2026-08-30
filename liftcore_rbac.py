"""
LiftCore — Role-Based Access Control (مصدر واحد للصلاحيات).

admin   : كامل — إعدادات، مستخدمون، حذف
manager : تشغيل يومي — بدون إعدادات الشركة/المستخدمين/التوقيعات
viewer  : قراءة فقط — بدون أي تعديل
custom  : مخصص — المسؤول يحدد الصلاحيات من قائمة
"""

from __future__ import annotations

MUTATING_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})

ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'manager'
ROLE_VIEWER = 'viewer'
ROLE_CUSTOM = 'custom'
ROLES = (ROLE_ADMIN, ROLE_MANAGER, ROLE_VIEWER, ROLE_CUSTOM)

SELF_SERVICE_POST_ENDPOINTS = frozenset({
    'logout',
    'settings_profile_save',
    'settings_theme_save',
    'settings_change_password',
    'api_user_language',
    'api_user_theme',
    'api_session_lock',
    'api_session_unlock',
})

ADMIN_ONLY_ENDPOINTS = frozenset({
    'settings_save',
    'settings_field_portal_pin',
    'settings_signatory_add',
    'settings_signatory_delete',
    'settings_signatures_prefs',
    'settings_screensaver_save',
    'settings_azkar_save',
    'settings_user_add',
    'settings_user_edit',
    'settings_user_toggle',
})

PASSWORD_CHANGE_ALLOWED_ENDPOINTS = frozenset({
    'login',
    'logout',
    'static',
    'settings',
    'settings_change_password',
    'web_manifest',
})

EXEMPT_PATH_PREFIXES = (
    '/static/',
    '/field/',
    '/api/field/',
)


def is_exempt_path(path: str) -> bool:
    path = path or ''
    return any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES)


def role_can_write(role: str | None) -> bool:
    return role in (ROLE_ADMIN, ROLE_MANAGER, ROLE_CUSTOM)


def role_is_admin(role: str | None) -> bool:
    return role == ROLE_ADMIN


def mutation_denied_response(*, as_json: bool, message_ar: str, message_en: str, lang: str = 'ar'):
    from flask import flash, render_template, request

    msg = message_en if lang == 'en' else message_ar
    if as_json or (request.path or '').startswith('/api/'):
        from liftcore_api_i18n import api_error_payload
        from flask import jsonify
        return jsonify(api_error_payload(
            'forbidden',
            message_ar=message_ar,
            message_en=message_en,
        )), 403
    flash(msg, 'error')
    # لا نُرجع redirect مع status 403 — المتصفح يعرض صفحة Werkzeug
    # «Redirecting...» ولا يتبع التحويل تلقائياً.
    return render_template(
        'permission_denied.html',
        message=msg,
        home_url=_safe_home_path(),
    ), 403


def _safe_home_path() -> str:
    """أول صفحة مسموحة للمستخدم الحالي، أو لوحة التحكم."""
    try:
        from flask import g, url_for
        from liftcore_permissions import first_allowed_path_for_user

        user = getattr(g, 'user', None)
        path = first_allowed_path_for_user(user)
        return path or url_for('dashboard')
    except Exception:
        return '/dashboard'


def check_rbac(user, *, method: str, endpoint: str | None, path: str, lang: str = 'ar', settings=None):
    if is_exempt_path(path):
        return None
    if not user:
        return None

    ep = endpoint or ''
    role = user.role or ROLE_VIEWER
    path = path or ''

    # شاشة الترحيب ولوحة التحكم متاحتان لأي مستخدم مسجّل (هيكل التطبيق)
    if path == '/welcome' or path == '/dashboard' or path.startswith('/api/dashboard'):
        return None

    if method in MUTATING_METHODS and ep in SELF_SERVICE_POST_ENDPOINTS:
        return None

    from liftcore_permissions import (
        check_path_permission,
    )

    if role == ROLE_CUSTOM:
        missing = check_path_permission(user, path=path, method=method, settings=settings)
        if missing:
            return mutation_denied_response(
                as_json=False,
                message_ar='ليس لديك صلاحية لهذا القسم.',
                message_en='You do not have permission for this area.',
                lang=lang,
            )
        if method in MUTATING_METHODS and ep in ADMIN_ONLY_ENDPOINTS:
            return mutation_denied_response(
                as_json=False,
                message_ar='هذا الإجراء متاح للمسؤول فقط.',
                message_en='This action is restricted to administrators.',
                lang=lang,
            )
        if method not in MUTATING_METHODS:
            return None
        return None

    if method not in MUTATING_METHODS:
        return None

    if role == ROLE_VIEWER:
        if ep not in SELF_SERVICE_POST_ENDPOINTS:
            return mutation_denied_response(
                as_json=False,
                message_ar='حساب «عرض فقط» — لا يمكنك تعديل البيانات.',
                message_en='View-only account — you cannot modify data.',
                lang=lang,
            )

    if role == ROLE_MANAGER and ep in ADMIN_ONLY_ENDPOINTS:
        return mutation_denied_response(
            as_json=False,
            message_ar='هذا الإجراء متاح للمسؤول فقط.',
            message_en='This action is restricted to administrators.',
            lang=lang,
        )

    return None
