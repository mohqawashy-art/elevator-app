"""موديول إدارة مشاريع تركيب المصاعد (تجريبي — محلي فقط)."""

import sys

from installation.config import install_blueprint_enabled


def register_install_module(app):
    if not install_blueprint_enabled():
        return
    # إجبار تحميل أحدث نسخة من المسارات (تجنّب كاش قديم)
    for name in list(sys.modules):
        if name == 'installation.routes' or name.startswith('installation.routes.'):
            del sys.modules[name]
    from installation.routes import install_bp
    app.register_blueprint(install_bp)
