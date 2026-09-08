"""موديول الحضور والانصراف — ADMS + API عام + إدخال يدوي."""

from __future__ import annotations

from attendance.routes import adms_bp, attendance_bp


def register_attendance_module(app):
    app.register_blueprint(attendance_bp)
    app.register_blueprint(adms_bp)
