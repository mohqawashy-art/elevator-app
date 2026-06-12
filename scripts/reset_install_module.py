"""
مسح بيانات موديول التركيب فقط — يبدأ مشروعاً من الصفر.
لا يمس جدول العملاء أو باقي LiftCore.

شغّل: python scripts/reset_install_module.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app import app, db
import installation.models  # noqa: F401
from installation.models import (
    InstallLead,
    InstallProject,
    InstallQuotation,
    InstallQuotationLine,
    InstallTimelineStep,
)


def reset_install_data():
    counts = {
        'timeline': InstallTimelineStep.query.count(),
        'lines': InstallQuotationLine.query.count(),
        'quotations': InstallQuotation.query.count(),
        'projects': InstallProject.query.count(),
        'leads': InstallLead.query.count(),
    }
    if not any(counts.values()):
        print('[OK] installation module already empty')
        return

    InstallTimelineStep.query.delete()
    InstallQuotationLine.query.delete()
    db.session.execute(text(
        'UPDATE installation_projects SET accepted_quotation_id = NULL, execution_started_at = NULL'
    ))
    InstallQuotation.query.delete()
    InstallProject.query.delete()
    InstallLead.query.delete()
    db.session.commit()

    print('[OK] installation module data cleared:')
    print(f'     leads: {counts["leads"]}')
    print(f'     projects: {counts["projects"]}')
    print(f'     quotations: {counts["quotations"]}')
    print(f'     quote lines: {counts["lines"]}')
    print(f'     timeline steps: {counts["timeline"]}')
    print('     LiftCore customers were NOT touched.')


with app.app_context():
    reset_install_data()
