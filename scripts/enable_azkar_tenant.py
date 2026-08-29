"""Enable azkar ticker for a tenant by slug (run on server)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Organization, Settings


def main():
    slug = (sys.argv[1] if len(sys.argv) > 1 else 'jama').strip()
    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if not org:
            print(f'ERROR: org slug={slug!r} not found')
            return 1
        s = Settings.query.filter_by(organization_id=org.id).first()
        if not s:
            print(f'ERROR: settings missing for org {slug}')
            return 1
        s.azkar_ticker_enabled = True
        db.session.commit()
        print(f'OK: azkar_ticker_enabled=True for {slug} (org_id={org.id})')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
