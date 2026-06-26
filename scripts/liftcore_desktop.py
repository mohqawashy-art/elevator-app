"""
LiftCore — تشغيل كتطبيق سطح مكتب (نافذة واحدة، ملء الشاشة فوق شريط المهام).
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get('LIFTCORE_PORT', '5000'))
HOST = '127.0.0.1'
START_URL = os.environ.get('LIFTCORE_URL', f'http://{HOST}:{PORT}/login')
TITLE = 'LiftCore'
ICON = ROOT / 'static' / 'images' / 'liftcore.ico'
MUTEX_NAME = 'Global\\LiftCoreDesktopSingleton_v1'


def _win_message(text: str, title: str = TITLE) -> None:
    if sys.platform != 'win32':
        print(text)
        return
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)


def ensure_single_instance() -> bool:
    """True = المثيل الأول. False = البرنامج يعمل مسبقاً."""
    if sys.platform != 'win32':
        return True
    import ctypes
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        _win_message('البرنامج يعمل بالفعل.\nتحقق من شريط المهام.')
        return False
    return True


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((HOST, port)) == 0


def wait_for_server(timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(PORT):
            return True
        time.sleep(0.25)
    return False


def start_flask_server() -> None:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault('LIFTCORE_DESKTOP', '1')
    from app import app
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


def run_webview() -> None:
    import webview

    webview.settings.OPEN_EXTERNAL_LINKS_IN_BROWSER = False
    webview.settings.ALLOW_DOWNLOADS = False

    window = webview.create_window(
        TITLE,
        START_URL,
        width=1366,
        height=768,
        resizable=True,
        maximized=True,
        min_size=(1024, 640),
        confirm_close=True,
        text_select=True,
    )

    icon = str(ICON) if ICON.exists() else None
    webview.start(icon=icon, gui='edgechromium')


def main() -> int:
    if not ensure_single_instance():
        return 0

    if not ICON.exists():
        try:
            import subprocess
            subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_desktop_icon.py')], check=False)
        except Exception:
            pass

    server_thread = None
    if not port_open(PORT):
        server_thread = threading.Thread(target=start_flask_server, daemon=True)
        server_thread.start()
        if not wait_for_server():
            _win_message('تعذّر تشغيل الخادم المحلي.\nجرّب إغلاق أي نسخة أخرى ثم أعد المحاولة.')
            return 1

    try:
        run_webview()
    except ImportError:
        _win_message(
            'مكوّن سطح المكتب غير مثبت.\n'
            'شغّل: pip install -r requirements-desktop.txt'
        )
        return 1
    except Exception as exc:
        _win_message(f'تعذّر فتح النافذة:\n{exc}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
