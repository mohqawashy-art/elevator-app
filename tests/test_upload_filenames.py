# -*- coding: utf-8 -*-
from app import (
    _guess_upload_mimetype,
    _original_upload_ext,
    _safe_stored_upload_name,
    _upload_download_name,
    ALLOWED_FIN_PROOF_EXT,
)


def test_arabic_pdf_keeps_dot_extension():
    name = _safe_stored_upload_name(
        'سند قبض — فرج.pdf',
        allowed=ALLOWED_FIN_PROOF_EXT,
        default_stem='proof',
    )
    assert name.endswith('.pdf'), name
    assert '_pdf' not in name.split('.')[0] or name.count('.') == 1
    assert '.' in name


def test_upload_download_name_repairs_legacy_underscore_ext():
    assert _upload_download_name('ed1dcaddd4_pdf') == 'ed1dcaddd4.pdf'
    assert _upload_download_name('663d65ea23_png') == '663d65ea23.png'
    assert _upload_download_name('ok_file.pdf') == 'ok_file.pdf'


def test_guess_mimetype_for_legacy_names():
    assert _guess_upload_mimetype('/tmp/ed1dcaddd4_pdf') == 'application/pdf'
    assert _guess_upload_mimetype('/tmp/x.png') == 'image/png'


def test_original_ext_from_arabic_name():
    assert _original_upload_ext('إيصال.pdf', ALLOWED_FIN_PROOF_EXT) == 'pdf'
    assert _original_upload_ext('photo.JPEG', ALLOWED_FIN_PROOF_EXT) == 'jpeg'
