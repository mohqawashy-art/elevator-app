/* Force-allow saving contracts with value 0 — overrides any stale inline saveContract. */
(function () {
  'use strict';

  var BAD_ALERT = 'قيمة العقد يجب أن تكون أكبر من صفر';

  // امنع الرسالة القديمة حتى لو نُودي alert من سكربت قديم
  var _alert = window.alert;
  window.alert = function (msg) {
    var s = String(msg == null ? '' : msg);
    if (s.indexOf(BAD_ALERT) !== -1) {
      console.warn('[LiftCore] ignored obsolete contract-value alert');
      return;
    }
    return _alert.apply(window, arguments);
  };

  function money0() {
    var rawValue = (document.getElementById('f-value') || {}).value;
    var rawCtax = (document.getElementById('ctax-input') || {}).value;
    var valueNum = parseFloat(rawValue);
    if (!isFinite(valueNum)) valueNum = parseFloat(rawCtax);
    if (!isFinite(valueNum) || valueNum < 0) valueNum = 0;
    var fValue = document.getElementById('f-value');
    var fTotal = document.getElementById('f-total');
    var ctax = document.getElementById('ctax-input');
    if (fValue) fValue.value = String(valueNum);
    if (ctax && (!ctax.value || !isFinite(parseFloat(ctax.value)))) ctax.value = String(valueNum);
    if (fTotal && (!fTotal.value || !isFinite(parseFloat(fTotal.value)) || parseFloat(fTotal.value) < 0)) {
      fTotal.value = String(valueNum);
    }
    return valueNum;
  }

  function cleanSave() {
    // لا ترفض القيمة 0 أبداً
    if (window.contractSaving) return;
    var clientSel = document.getElementById('f-client-sel');
    if (!clientSel || !clientSel.value) {
      _alert('يرجى اختيار العميل');
      return;
    }
    var startEl = document.getElementById('f-start');
    var endEl = document.getElementById('f-end');
    if (!startEl || !startEl.value || !endEl || !endEl.value) {
      _alert('يرجى إدخال تاريخ البداية والانتهاء');
      return;
    }
    if (new Date(endEl.value) < new Date(startEl.value)) {
      _alert('تاريخ النهاية يجب أن يكون بعد تاريخ البداية');
      return;
    }

    money0();
    var taxBlock = document.querySelector('#modal-add .lc-tax-block');
    if (taxBlock && taxBlock._lcTaxCalc) taxBlock._lcTaxCalc.update();
    money0();

    var modalAdd = document.getElementById('modal-add');
    if (!modalAdd) return;
    var editId = modalAdd.dataset.editId;
    var saveBtn = document.getElementById('btn-save-contract');
    var saveBtnHtml = saveBtn ? saveBtn.innerHTML : '';

    if (typeof window.buildContractFormData !== 'function' || typeof window.postContractSave !== 'function') {
      // الصفحة لم تُحمّل دوال الحفظ بعد — أعد المحاولة بلطف
      _alert('الصفحة لم تكتمل تحميلها — حدّث الصفحة ثم أعد المحاولة');
      return;
    }

    // تغيير العميل (إن وُجدت الدوال المساعدة)
    try {
      if (typeof window.getOriginalContractCustomerId === 'function') {
        var originalCustomerId = window.getOriginalContractCustomerId(editId);
        var customerChanged = !!(editId && originalCustomerId && String(clientSel.value) !== String(originalCustomerId));
        if (customerChanged) {
          if (!window.__LC_IS_ADMIN) {
            _alert('تغيير عميل العقد متاح لمدير النظام فقط');
            if (typeof window.revertContractClientToOriginal === 'function') window.revertContractClientToOriginal();
            return;
          }
          if (typeof window.isContractClientChangeUnlocked === 'function' && !window.isContractClientChangeUnlocked()) {
            _alert('اضغط «تغيير العميل» وأدخل كلمة مرور مدير النظام قبل الحفظ');
            if (typeof window.revertContractClientToOriginal === 'function') window.revertContractClientToOriginal();
            return;
          }
          window.postContractSave(editId, window.buildContractFormData(window.contractClientChangePassword || ''), saveBtn, saveBtnHtml);
          return;
        }
      }
    } catch (e) {
      console.warn(e);
    }

    window.postContractSave(editId, window.buildContractFormData(''), saveBtn, saveBtnHtml);
  }

  function install() {
    if (!document.getElementById('btn-save-contract')) return;

    // اجعل الدوال متاحة عالمياً (تستبدل أي نسخة قديمة)
    window.saveContract = cleanSave;
    window.saveContractAllowZero = cleanSave;

    var btn = document.getElementById('btn-save-contract');
    if (!btn || btn.dataset.lcZeroPatched === '1') return;
    btn.dataset.lcZeroPatched = '1';
    btn.setAttribute('onclick', 'saveContractAllowZero()');

    // التقاط النقر قبل أي onclick قديم
    btn.addEventListener(
      'click',
      function (e) {
        e.preventDefault();
        e.stopImmediatePropagation();
        cleanSave();
      },
      true
    );
  }

  // function declarations في الصفحة تُعرَّف أثناء التحليل؛ نثبّت بعد load
  window.addEventListener('load', install);
  document.addEventListener('DOMContentLoaded', function () {
    install();
    var n = 0;
    var t = setInterval(function () {
      install();
      n += 1;
      if (n >= 20) clearInterval(t);
    }, 100);
  });
})();
