"""إعدادات موديول التركيب — تسجيل عالمي + تفعيل لكل مؤسسة حسب الباقة/الإضافة."""
import os


def _env_truthy(name: str) -> bool | None:
    raw = os.environ.get(name, '').strip().lower()
    if raw in ('0', 'false', 'no'):
        return False
    if raw in ('1', 'true', 'yes'):
        return True
    return None


def install_blueprint_enabled() -> bool:
    """هل يُسجَّل blueprint التركيب عند إقلاع التطبيق؟"""
    forced = _env_truthy('LIFTCORE_INSTALL_MODULE')
    if forced is False:
        return False
    if forced is True:
        return True
    # محلي: مفعّل. سيرفر HTTPS: مفعّل أيضاً الآن لأن التفعيل صار لكل مؤسسة.
    return True


def install_module_enabled(org=None) -> bool:
    """هل التركِيب متاح للمؤسسة الحالية؟"""
    forced = _env_truthy('LIFTCORE_INSTALL_MODULE')
    if forced is False:
        return False

    # فرض بيئي صريح = متاح لكل المؤسسات (توافق خلفي)
    if forced is True:
        return True

    # محلي بدون HTTPS: متاح للتجربة بدون قيود باقة
    if _env_truthy('LIFTCORE_HTTPS') is not True:
        return True

    try:
        from entitlements import has_feature
        return bool(has_feature('installation', org=org))
    except Exception:
        return False
