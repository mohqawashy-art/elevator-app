/**
 * إرسال تقرير عطل للعميل — واتساب (الرابط داخل الرسالة).
 */
(function (global) {
  'use strict';

  function send(faultId, opts) {
    opts = opts || {};
    if (!faultId) return Promise.resolve();
    return fetch('/api/faults/' + faultId + '/customer-report-send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (res) {
        var data = res.data || {};
        if (!res.ok || !data.ok) {
          alert(data.error || 'تعذّر تجهيز إرسال التقرير');
          return;
        }
        openWhatsApp(data.url);
        if (opts.onPrintPage) {
          global.setTimeout(function () {
            if (global.confirm('لإرفاق PDF في واتساب: اضغط موافق لطباعة/حفظ هذا التقرير الآن.')) {
              global.print();
            }
          }, 500);
          return;
        }
        global.setTimeout(function () {
          if (global.confirm('لإرفاق PDF يدوياً: اضغط موافق لفتح التقرير للطباعة (اختياري — الرابط موجود في رسالة واتساب).')) {
            var printPath = data.report_print_path || ('/faults/' + faultId + '/report?print=1');
            global.open(printPath, '_blank', 'noopener');
          }
        }, 400);
      })
      .catch(function () {
        alert('تعذّر إرسال التقرير للعميل');
      });
  }

  function openWhatsApp(url) {
    if (!url) {
      alert('لا يوجد رابط واتساب');
      return;
    }
    var wa = global.open(url, '_blank', 'noopener');
    if (!wa) {
      var go = global.confirm('رسالة واتساب جاهزة للعميل.\nاضغط موافق لفتح واتساب وإرسال الرسالة.');
      if (go) global.location.href = url;
    }
  }

  global.LiftCoreFaultReportSend = { send: send };
})(window);
