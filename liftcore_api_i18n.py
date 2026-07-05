"""LiftCore — رسائل API ثنائية اللغة (P2 J2)."""

from __future__ import annotations

from flask import jsonify, request, session

# code → (ar, en)
API_ERRORS: dict[str, tuple[str, str]] = {
    'login_required': ('يجب تسجيل الدخول', 'Please sign in'),
    'admin_required': ('صلاحية المسؤول مطلوبة', 'Administrator access required'),
    'forbidden': ('غير مصرح', 'Not allowed'),
    'invalid_password': ('كلمة المرور غير صحيحة', 'Incorrect password'),
    'password_change_required': ('يجب تغيير كلمة المرور أولاً', 'You must change your password first'),
    'session_locked': ('الجلسة مقفلة', 'Session is locked'),
    'not_found': ('غير موجود', 'Not found'),
    'validation_error': ('بيانات غير صالحة', 'Invalid data'),
    'field_login_required': ('يجب تسجيل دخول الفني', 'Technician sign-in required'),
    'field_forbidden': ('غير مصرح لهذا الحساب', 'Not authorized for this account'),
}


def request_lang() -> str:
    lang = session.get('lang') or request.headers.get('X-LC-Lang') or 'ar'
    return 'en' if lang == 'en' else 'ar'


def api_error_payload(
    code: str,
    *,
    message_ar: str | None = None,
    message_en: str | None = None,
    extra: dict | None = None,
) -> dict:
    pair = API_ERRORS.get(code)
    ar = message_ar or (pair[0] if pair else code)
    en = message_en or (pair[1] if pair else code)
    lang = request_lang()
    body = {
        'ok': False,
        'error': code,
        'message': en if lang == 'en' else ar,
        'message_ar': ar,
        'message_en': en,
    }
    if extra:
        body.update(extra)
    return body


def api_json_error(
    code: str,
    status: int = 400,
    *,
    message_ar: str | None = None,
    message_en: str | None = None,
    extra: dict | None = None,
):
    return jsonify(api_error_payload(
        code,
        message_ar=message_ar,
        message_en=message_en,
        extra=extra,
    )), status
