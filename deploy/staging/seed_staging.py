#!/usr/bin/env python3
"""Ensure staging has tenant slug `test` so test.liftcoreapp.com/login resolves."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("LIFTCORE_ENV_FILE", "/etc/liftcore/staging.env")
os.environ.setdefault("LIFTCORE_ALEMBIC", "1")

root = Path.cwd()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from app import app, db, hash_password  # noqa: E402
from models import Organization, Settings, User  # noqa: E402


def main() -> None:
    with app.app_context():
        org = Organization.query.filter_by(slug="test").first()
        if not org:
            org = Organization.query.filter_by(slug="default").first()
            if org:
                org.slug = "test"
                org.name = org.name or "LiftCore Test"
            else:
                org = Organization(slug="test", name="LiftCore Test", status="active")
                db.session.add(org)
                db.session.flush()
        org.status = "active"
        if not org.name:
            org.name = "LiftCore Test"

        admin = User.query.filter_by(username="admin", organization_id=org.id).first()
        if not admin:
            admin = User.query.filter_by(username="admin").first()
            if admin:
                admin.organization_id = org.id
                admin.is_active = True
            else:
                admin = User(
                    username="admin",
                    password_hash=hash_password("admin123"),
                    full_name="مدير التجربة",
                    email="admin@test.liftcoreapp.com",
                    role="admin",
                    is_active=True,
                    organization_id=org.id,
                )
                db.session.add(admin)

        if not Settings.query.filter_by(organization_id=org.id).first():
            db.session.add(
                Settings(
                    company_name="بيئة التجربة",
                    company_name_en="LiftCore Test",
                    phone="0500000000",
                    email="info@liftcoreapp.com",
                    city="مكة المكرمة",
                    tax_pct=15,
                    currency="ر.س",
                    language="ar",
                    organization_id=org.id,
                )
            )
        db.session.commit()

        with app.test_client() as client:
            response = client.get("/login", base_url="https://test.liftcoreapp.com")
        print(f"org_slug={org.slug} login_http={response.status_code}")


if __name__ == "__main__":
    main()
