"""
LiftCore — Role-Based Access Control (مصدر واحد للصلاحيات).

admin   : كامل — إعدادات، مستخدمون، حذف
manager : تشغيل يومي — بدون إعدادات الشركة/المستخدمين/التوقيعات
viewer  : قراءة فقط — بدون أي تعديل
"""

from __future__ import annotations

MUTATING_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})

ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'manager'
ROLE_VIEWER = 'viewer'
ROLES = (ROLE_ADMIN, ROLE_MANAGER, ROLE_VIEWER)

# POST مسموح لأي مستخدم مسجّل (بما فيهم viewer) — حسابه الشخصي فقط
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

# GET مسموح عند إجبار تغيير كلمة المرور
PASSWORD_CHANGE_ALLOWED_ENDPOINTS = frozenset({
    'login',
    'logout',
    'static',
    'settings',
    'settings_change_password',
    'web_manifest',
})

# admin فقط — إعدادات النظام والمستخدمين
ADMIN_ONLY_ENDPOINTS = frozenset({
    'settings_save',
    'settings_field_portal_pin',
    'settings_signatory_add',
    'settings_signatory_delete',
    'settings_signatures_prefs',
    'settings_screensaver_save',
    'settings_user_add',
    'settings_user_edit',
    'settings_user_toggle',
})

# مسارات CSRF / RBAC معفاة (بوابة الفني منفصلة)
EXEMPT_PATH_PREFIXES = (
    '/static/',
    '/field/',
    '/api/field/',
)


def is_exempt_path(path: str) -> bool:
    path = path or ''
    return any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES)


def role_can_write(role: str | None) -> bool:
    return role in (ROLE_ADMIN, ROLE_MANAGER)


def role_is_admin(role: str | None) -> bool:
    return role == ROLE_ADMIN


def mutation_denied_response(*, as_json: bool, message_ar: str, message_en: str, lang: str = 'ar'):
    """يرجع (response, status_code) أو None إذا مسموح."""
    from flask import jsonify, flash, redirect, url_for, request

    msg = message_en if lang == 'en' else message_ar
    if as_json or (request.path or '').startswith('/api/'):
        from liftcore_api_i18n import api_error_payload
        return jsonify(api_error_payload(
            'forbidden',
            message_ar=message_ar,
            message_en=message_en,
        )), 403
    flash(msg, 'error')
    return redirect(request.referrer or url_for('dashboard')), 403


def check_rbac(user, *, method: str, endpoint: str | None, path: str, lang: str = 'ar', settings=None):
    """
    يتحقق من صلاحية الطلب.
    يرجع None إذا مسموح، أو (response, status) إذا مرفوض.
    """
    if is_exempt_path(path):
        return None
    if not user:
        return None

    from liftcore_permissions import (
        ADMIN_ONLY_ENDPOINTS_PERMISSION,
        check_path_permission,
        custom_permissions_enabled,
        permissions_for_path,
        user_has_permission,
    )

    custom_on = custom_permissions_enabled(settings)

    if custom_on:
        missing = check_path_permission(user, path=path, method=method, settings=settings)
        if missing:
            return mutation_denied_response(
                as_json=False,
                message_ar='ليس لديك صلاحية لهذا القسم.',
                message_en='You do not have permission for this area.',
                lang=lang,
            )
        if method in MUTATING_METHODS and endpoint in ADMIN_ONLY_ENDPOINTS:
            if not user_has_permission(user, ADMIN_ONLY_ENDPOINTS_PERMISSION, settings):
                return mutation_denied_response(
                    as_json=False,
                    message_ar='هذا الإجراء متاح للمسؤول فقط.',
                    message_en='This action is restricted to administrators.',
                    lang=lang,
                )
        if method not in MUTATING_METHODS:
            return None
    elif method not in MUTATING_METHODS:
        return None

    role = user.role or ROLE_VIEWER
    ep = endpoint or ''

    if role == ROLE_VIEWER:
        if ep not in SELF_SERVICE_POST_ENDPOINTS:
            if custom_on:
                _, write_p = permissions_for_path(path, method)
                if write_p and user_has_permission(user, write_p, settings):
                    return None
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
