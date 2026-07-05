"""
LiftCore — سجل تدقيق للعمليات الحساسة.
"""

from __future__ import annotations

from datetime import datetime

from flask import request


def _client_ip() -> str:
    forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return forwarded or (request.remote_addr or '')


def log_audit(
    action: str,
    *,
    user=None,
    entity_type: str | None = None,
    entity_id=None,
    details: dict | None = None,
) -> None:
    """يسجّل حدثاً — يتجاهل الأخطاء حتى لا يكسر الطلب الأساسي."""
    try:
        from models import AuditLog, db

        username = ''
        user_id = None
        if user is not None:
            user_id = getattr(user, 'id', None)
            username = getattr(user, 'username', None) or getattr(user, 'full_name', None) or ''

        row = AuditLog(
            created_at=datetime.utcnow(),
            user_id=user_id,
            username=username or None,
            action=(action or '')[:80],
            entity_type=(entity_type or '')[:60] or None,
            entity_id=str(entity_id)[:40] if entity_id is not None else None,
            details_json=_details_to_json(details),
            ip_address=_client_ip()[:45] or None,
        )
        db.session.add(row)
        db.session.commit()
    except Exception:
        try:
            from models import db
            db.session.rollback()
        except Exception:
            pass


def _details_to_json(details: dict | None) -> str | None:
    if not details:
        return None
    import json
    try:
        return json.dumps(details, ensure_ascii=False, default=str)[:4000]
    except (TypeError, ValueError):
        return str(details)[:4000]
