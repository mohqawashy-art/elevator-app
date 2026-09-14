"""تمييز عروض المبيعات (تسعير بدون موافقة عميل) عن مشاريع التركيب الفعلية."""
from __future__ import annotations

from sqlalchemy import exists, or_, select

from installation.models import InstallContract, InstallProject, InstallQuotation
from models import db

# قبل قبول العميل — تبقى في المبيعات فقط
SALES_STAGE_STATUSES = (
    'استفسار',
    'معاينة',
    'هندسة',
    'تسعير',
    'عرض سعر',
)


def is_sales_stage_install_project(project: InstallProject) -> bool:
    """عرض/تسعير لم تُقبل بعد — لا يُعرض في قائمة مشاريع التركيب."""
    if project.accepted_quotation_id:
        return False
    if project.execution_started_at:
        return False
    if project.contract_id:
        return False
    if getattr(project, 'install_contract', None):
        return False
    if hasattr(project, 'quotations'):
        try:
            if project.quotations.filter_by(status='مقبول').first():
                return False
        except Exception:
            pass
    status = (project.status or '').strip()
    return status in SALES_STAGE_STATUSES


def ensure_operational_install_project(project: InstallProject) -> bool:
    """إذا وُجد عرض مقبول دون ربط على المشروع — يُحدَّث المشروع ليصبح تشغيلياً."""
    if project.accepted_quotation_id:
        return False
    if not hasattr(project, 'quotations'):
        return False
    accepted = (
        project.quotations.filter_by(status='مقبول')
        .order_by(InstallQuotation.approved_at.desc(), InstallQuotation.id.desc())
        .first()
    )
    if not accepted:
        return False
    project.accepted_quotation_id = accepted.id
    if (project.status or '').strip() in SALES_STAGE_STATUSES:
        project.status = 'عقد'
    if not project.customer_id and accepted.customer_id:
        project.customer_id = accepted.customer_id
    db.session.flush()
    return True


def operational_install_projects_query(base_query=None):
    """استعلام مشاريع التركيب بعد موافقة العميل أو دخول التنفيذ/العقد."""
    from tenant_scope import tenant_query

    q = base_query if base_query is not None else tenant_query(InstallProject)
    has_install_contract = exists(
        select(InstallContract.id).where(InstallContract.project_id == InstallProject.id)
    )
    has_accepted_quote = exists(
        select(InstallQuotation.id).where(
            InstallQuotation.project_id == InstallProject.id,
            InstallQuotation.status == 'مقبول',
        )
    )
    return q.filter(
        or_(
            InstallProject.accepted_quotation_id.isnot(None),
            InstallProject.execution_started_at.isnot(None),
            InstallProject.contract_id.isnot(None),
            InstallProject.status.notin_(SALES_STAGE_STATUSES),
            has_install_contract,
            has_accepted_quote,
        )
    )


def sales_stage_project_redirect(project):
    """رابط تحرير العرض في المبيعات."""
    from flask import url_for

    quotation = (
        project.quotations.order_by(InstallQuotation.created_at.desc()).first()
        if hasattr(project, 'quotations')
        else None
    )
    if quotation:
        return url_for(
            'installation.project_quote',
            project_id=project.id,
            quotation_id=quotation.id,
            **{'from': 'sales'},
        )
    return url_for('sales.quotes_inbox', kind='install')


def redirect_if_sales_stage_project(project):
    """يُرجع redirect إذا كان المشروع لا يزال في المبيعات."""
    from flask import flash, redirect

    ensure_operational_install_project(project)
    if not is_sales_stage_install_project(project):
        return None
    flash(
        'هذا العرض لا يزال في المبيعات — يظهر كمشروع تركيب بعد موافقة العميل على العرض.',
        'info',
    )
    return redirect(sales_stage_project_redirect(project))
