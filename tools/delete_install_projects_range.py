#!/usr/bin/env python3
"""حذف مشاريع تركيب بالمعرّف (لتنظيف بيانات — مثلاً 5–11)."""
from __future__ import annotations

import argparse

from flask import g

from app import app
from installation.models import InstallProject
from installation.project_card import delete_install_project
from models import Organization, db


def main() -> None:
    parser = argparse.ArgumentParser(description='Delete installation projects by id')
    parser.add_argument('--org', default='jama', help='organization slug')
    parser.add_argument('--ids', nargs='+', type=int, required=True, help='project ids')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    with app.app_context():
        org = Organization.query.filter_by(slug=args.org).one()
        g.organization = org
        g.organization_id = org.id

        for pid in args.ids:
            project = db.session.get(InstallProject, pid)
            if not project or project.organization_id != org.id:
                print(f'SKIP {pid}: not found')
                continue
            if project.execution_active:
                print(f'SKIP {pid} {project.code}: execution active')
                continue
            if args.dry_run:
                print(f'WOULD_DELETE {pid} {project.code} {project.status}')
                continue
            code = delete_install_project(project)
            db.session.commit()
            print(f'DELETED {pid} {code}')


if __name__ == '__main__':
    main()
