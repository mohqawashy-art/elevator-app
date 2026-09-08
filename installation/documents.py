"""مرفقات مشاريع التركيب — رفع وحذف."""
from __future__ import annotations

import os
import shutil

from flask import current_app
from sqlalchemy import inspect

from installation.models import InstallContract, InstallContractDocument, InstallProject, InstallProjectDocument
from models import db
from tenant_scope import assign_organization, tenant_query

ALLOWED_PROJECT_DOC_EXT = frozenset({
    'pdf', 'png', 'jpg', 'jpeg', 'webp', 'gif', 'doc', 'docx', 'xls', 'xlsx',
})


def ensure_project_documents_schema() -> None:
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())
    if 'installation_project_documents' not in tables:
        InstallProjectDocument.__table__.create(bind=db.engine, checkfirst=True)


def _project_docs_dir(project_id: int) -> str:
    root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
    folder = os.path.join(root, 'uploads', 'installation', 'projects', str(project_id), 'docs')
    os.makedirs(folder, exist_ok=True)
    return folder


def save_project_document(project: InstallProject, file_storage, *, label: str | None = None, step_key: str | None = None):
    from app import _safe_stored_upload_name, _upload_ok

    if not file_storage or not file_storage.filename:
        raise ValueError('لم يُرفَع ملف')
    ok, err = _upload_ok(file_storage, ALLOWED_PROJECT_DOC_EXT)
    if not ok:
        raise ValueError(err or 'نوع الملف غير مسموح')
    stored = _safe_stored_upload_name(
        file_storage.filename,
        allowed=ALLOWED_PROJECT_DOC_EXT,
        default_stem='document',
    )
    folder = _project_docs_dir(project.id)
    abs_path = os.path.join(folder, stored)
    file_storage.save(abs_path)
    display = (label or '').strip() or (file_storage.filename or stored).replace('\\', '/').split('/')[-1]
    doc = InstallProjectDocument(
        project_id=project.id,
        step_key=(step_key or '').strip() or None,
        label=display,
        file_path=f'uploads/installation/projects/{project.id}/docs/{stored}',
        file_name=stored,
        mime_type=getattr(file_storage, 'mimetype', None) or '',
    )
    assign_organization(doc)
    db.session.add(doc)
    return doc


def delete_project_document(project: InstallProject, doc_id: int) -> bool:
    doc = tenant_query(InstallProjectDocument).filter_by(id=doc_id, project_id=project.id).first()
    if not doc:
        return False
    rel = (doc.file_path or '').replace('\\', '/').lstrip('/')
    if rel.startswith('uploads/'):
        root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
        abs_path = os.path.join(root, rel)
        if os.path.isfile(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass
    db.session.delete(doc)
    return True


def group_project_documents_by_step(documents) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for doc in documents or []:
        key = (getattr(doc, 'step_key', None) or '').strip() or '_legacy'
        grouped.setdefault(key, []).append(doc)
    return grouped


def remove_project_documents_folder(project_id: int) -> None:
    root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
    folder = os.path.join(root, 'uploads', 'installation', 'projects', str(project_id))
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


def ensure_contract_documents_schema() -> None:
    insp = inspect(db.engine)
    try:
        insp.clear_cache()
    except Exception:
        pass
    tables = set(insp.get_table_names())
    if 'installation_contract_documents' not in tables:
        InstallContractDocument.__table__.create(bind=db.engine, checkfirst=True)


def _contract_docs_dir(contract_id: int) -> str:
    root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
    folder = os.path.join(root, 'uploads', 'installation', 'contracts', str(contract_id), 'docs')
    os.makedirs(folder, exist_ok=True)
    return folder


def save_contract_document(contract: InstallContract, file_storage, *, label: str | None = None):
    from app import _safe_stored_upload_name, _upload_ok

    if not file_storage or not file_storage.filename:
        raise ValueError('لم يُرفَع ملف')
    ok, err = _upload_ok(file_storage, ALLOWED_PROJECT_DOC_EXT)
    if not ok:
        raise ValueError(err or 'نوع الملف غير مسموح')
    stored = _safe_stored_upload_name(
        file_storage.filename,
        allowed=ALLOWED_PROJECT_DOC_EXT,
        default_stem='document',
    )
    folder = _contract_docs_dir(contract.id)
    abs_path = os.path.join(folder, stored)
    file_storage.save(abs_path)
    display = (label or '').strip() or (file_storage.filename or stored).replace('\\', '/').split('/')[-1]
    doc = InstallContractDocument(
        contract_id=contract.id,
        label=display,
        file_path=f'uploads/installation/contracts/{contract.id}/docs/{stored}',
        file_name=stored,
        mime_type=getattr(file_storage, 'mimetype', None) or '',
    )
    assign_organization(doc)
    db.session.add(doc)
    return doc


def delete_contract_document(contract: InstallContract, doc_id: int) -> bool:
    doc = tenant_query(InstallContractDocument).filter_by(id=doc_id, contract_id=contract.id).first()
    if not doc:
        return False
    rel = (doc.file_path or '').replace('\\', '/').lstrip('/')
    if rel.startswith('uploads/'):
        root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
        abs_path = os.path.join(root, rel)
        if os.path.isfile(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass
    db.session.delete(doc)
    return True


def remove_contract_documents_folder(contract_id: int) -> None:
    root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
    folder = os.path.join(root, 'uploads', 'installation', 'contracts', str(contract_id))
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
