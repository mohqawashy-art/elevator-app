"""اختبارات تسعير مراحل التركيب."""
from installation.models import InstallProject, InstallQuotation, InstallQuotationLine
from installation.routes import _quote_stage_blocks
from models import Organization, db
from tests.conftest import login_as


def test_new_bom_uses_three_install_stages():
    from pathlib import Path
    import subprocess
    import sys

    # تحقق سريع من ثوابت المراحل في ملف التسعير
    js = Path('static/installation-pricing.js').read_text(encoding='utf-8')
    assert 'مرحلة 1 — سكك وأبواب' in js
    assert 'مرحلة 2 — تركيب كبينة وأحبال وماكينة' in js
    assert 'مرحلة 3 — تركيب كنترول وتشغيل' in js


def test_quote_stage_blocks_split_labor(client):
    login_as(client, role='admin')
    with client.application.app_context():
        org = Organization.query.filter_by(slug='default').first()
        project = InstallProject(
            organization_id=org.id,
            code='PRJ-STAGES',
            title='مشروع مراحل',
            status='تسعير',
        )
        db.session.add(project)
        db.session.flush()
        q = InstallQuotation(
            organization_id=org.id,
            code='QT-STAGES',
            project_id=project.id,
            quote_type='new',
            status='مسودة',
            labor=10000,
            transport=0,
            other_costs=0,
            profit_pct=0,
            before_tax=10000,
            vat_amount=1500,
            grand_total=11500,
        )
        db.session.add(q)
        db.session.flush()
        db.session.add(InstallQuotationLine(
            organization_id=org.id,
            quotation_id=q.id,
            stage='مرحلة 1 — سكك وأبواب',
            name='سكك',
            unit='متر',
            qty=10,
            unit_price=100,
            sort_order=1,
        ))
        db.session.add(InstallQuotationLine(
            organization_id=org.id,
            quotation_id=q.id,
            stage='مرحلة 2 — تركيب كبينة وأحبال وماكينة',
            name='ماكينة',
            unit='قطعة',
            qty=1,
            unit_price=20000,
            sort_order=2,
        ))
        db.session.add(InstallQuotationLine(
            organization_id=org.id,
            quotation_id=q.id,
            stage='مرحلة 3 — تركيب كنترول وتشغيل',
            name='لوحة',
            unit='قطعة',
            qty=1,
            unit_price=8000,
            sort_order=3,
        ))
        db.session.commit()
        blocks, labor_sell = _quote_stage_blocks(q)
        assert labor_sell == 10000
        assert len(blocks) == 3
        assert blocks[0]['stage'].startswith('مرحلة 1')
        assert blocks[0]['labor_amount'] == 3000
        assert blocks[1]['labor_amount'] == 4500
        assert blocks[2]['labor_amount'] == 2500
        assert blocks[0]['total'] == 1000 + 3000
        assert blocks[1]['total'] == 20000 + 4500
        assert blocks[2]['total'] == 8000 + 2500
