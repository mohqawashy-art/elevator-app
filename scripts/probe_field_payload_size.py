#!/usr/bin/env python3
"""Compare /api/field/me payload sizes per technician."""
from __future__ import annotations

from app import app
from models import Organization, Technician
from operations import field_technician_payload
import json


def main() -> int:
    with app.app_context():
        org = Organization.query.filter_by(slug='jama').first()
        if not org:
            print('no jama org')
            return 1
        techs = (
            Technician.query.execution_options(skip_tenant=True)
            .filter_by(organization_id=org.id)
            .order_by(Technician.id.asc())
            .all()
        )
        for t in techs:
            p = field_technician_payload(t.id, portal_kind='both')
            blob = {'ok': True, **p}
            raw = json.dumps(blob, ensure_ascii=False)
            print(
                f'id={t.id} {t.code} faults={len(p.get("faults") or [])} '
                f'bytes={len(raw.encode("utf-8"))}'
            )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
