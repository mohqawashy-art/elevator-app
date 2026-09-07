#!/usr/bin/env python3
"""حذف مشاريع تركيب — بالكود PRJ-XXXX (وليس بالمعرّف الداخلي)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import g

from app import app
from installation.models import InstallProject
from installation.project_card import delete_install_project
from models import Organization, db
from tenant_scope import tenant_query


def expand_code_range(spec: str) -> list[str]:
    if '-' not in spec:
        raise ValueError(spec)
    start, end = spec.split('-', 1)
    lo, hi = int(start), int(end)
    return [f'PRJ-{n:04d}' for n in range(lo, hi + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description='Delete installation projects by PRJ code')
    parser.add_argument('--org', default='jama', help='organization slug')
    parser.add_argument('--codes', nargs='+', default=[], help='e.g. PRJ-0005')
    parser.add_argument(
        '--code-range',
        help='رقم المشروع في الكود: 5-11 يعني PRJ-0005 حتى PRJ-0011 (وليس id في قاعدة البيانات)',
    )
    parser.add_argument('--ids', nargs='+', type=int, help='deprecated: internal ids — avoid')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    codes = list(args.codes)
    if args.code_range:
        codes.extend(expand_code_range(args.code_range))
    if not codes and not args.ids:
        raise SystemExit('Provide --code-range (e.g. 5-11) or --codes')

    with app.app_context():
        org = Organization.query.filter_by(slug=args.org).one()
        g.organization = org
        g.organization_id = org.id

        targets: list[InstallProject] = []
        if codes:
            for code in codes:
                p = tenant_query(InstallProject).filter_by(code=code).first()
                if p:
                    targets.append(p)
                else:
                    print(f'SKIP code {code}: not found')
        if args.ids:
            print('WARNING: --ids uses internal database id, not PRJ number. Prefer --code-range.')
            for pid in args.ids:
                p = db.session.get(InstallProject, pid)
                if p and p.organization_id == org.id:
                    targets.append(p)
                else:
                    print(f'SKIP id {pid}: not found')

        seen = set()
        for project in targets:
            if project.id in seen:
                continue
            seen.add(project.id)
            if project.execution_active:
                print(f'SKIP {project.code} (id={project.id}): execution active')
                continue
            if args.dry_run:
                print(f'WOULD_DELETE id={project.id} {project.code} {project.status}')
                continue
            code = delete_install_project(project)
            db.session.commit()
            print(f'DELETED id={project.id} {code}')


if __name__ == '__main__':
    main()
