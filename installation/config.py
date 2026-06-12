"""إعدادات موديول التركيب — مفعّل محلياً، معطّل على السيرفر افتراضياً."""
import os


def install_module_enabled():
    """
    محلي (بدون LIFTCORE_HTTPS): مفعّل تلقائياً — لا تحتاج run.bat.
    السيرفر (LIFTCORE_HTTPS=1): معطّل إلا إذا ضبطت LIFTCORE_INSTALL_MODULE=1 صراحة.
    للإيقاف محلياً: LIFTCORE_INSTALL_MODULE=0
    """
    flag = os.environ.get('LIFTCORE_INSTALL_MODULE', '').strip().lower()
    if flag in ('0', 'false', 'no'):
        return False
    if flag in ('1', 'true', 'yes'):
        return True
    if os.environ.get('LIFTCORE_HTTPS', '').strip().lower() in ('1', 'true', 'yes'):
        return False
    return True
