/**
 * LiftCore — تهيئة التوقيعات على أي مستند (محضر صيانة، تقرير عطل، …)
 */
(function (global) {
  'use strict';

  function collectSignatures() {
    const checklist = global.LiftCoreChecklist;
    const techMeta = global.LiftCoreDigitalSign
      ? global.LiftCoreDigitalSign.getTechSignMeta()
      : { method: '', signed_by: '', signed_at: '' };
    return {
      tech: checklist ? checklist.canvasDataUrl('sig-tech') : '',
      client: checklist ? checklist.canvasDataUrl('sig-client') : '',
      tech_method: techMeta.method || '',
      tech_signed_by: techMeta.signed_by || '',
      tech_signed_at: techMeta.signed_at || '',
    };
  }

  function applySaved(reportData) {
    const sig = (reportData && reportData.signatures) || {};
    if (global.LiftCoreChecklist) {
      global.LiftCoreChecklist.applySignatures(sig);
    }
    if (global.LiftCoreDigitalSign && sig.tech_method === 'pin') {
      global.LiftCoreDigitalSign.applyTechSignMeta(sig);
    }
    if (sig.tech_method === 'pin' && sig.tech_signed_by) {
      const el = document.getElementById('sig-tech-pin-meta');
      if (el) el.textContent = 'وقّع رقمياً: ' + sig.tech_signed_by;
    }
  }

  function initEditable(opts) {
    opts = opts || {};
    if (!opts.editable || !global.LiftCoreChecklist) return;
    global.LiftCoreChecklist.setupSignature('sig-client', true);
    const signConfig = opts.signConfig || {};
    const method = signConfig.default_method || 'both';
    if (!global.LiftCoreDigitalSign) {
      global.LiftCoreChecklist.setupSignature('sig-tech', true);
      return;
    }
    global.LiftCoreDigitalSign.initTechSignSlot({
      editable: true,
      visitId: opts.visitId || null,
      faultId: opts.faultId || null,
      defaultMethod: method,
      prefillNationalId: opts.techNationalId || '',
      onSuccess: function (meta) {
        const el = document.getElementById('sig-tech-pin-meta');
        if (el && meta && meta.signed_by) {
          el.textContent = 'وقّع رقمياً: ' + meta.signed_by;
        }
      },
    });
    if (method !== 'pin') {
      global.LiftCoreChecklist.setupSignature('sig-tech', true);
    }
  }

  global.LiftCoreDocSign = {
    collectSignatures: collectSignatures,
    applySaved: applySaved,
    initEditable: initEditable,
  };
})(window);
