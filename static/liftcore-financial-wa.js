/**
 * طلب سداد واتساب + رابط تسجيل سداد (إيرادات) للعمليات المالية.
 */
(function (global) {
  'use strict';

  var ICON = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/></svg>';

  var PAY_ICON = '<svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3" aria-hidden="true"><rect x="1.5" y="3.5" width="11" height="7.5" rx="1.2"/><path d="M1.5 6h11"/><circle cx="9.5" cy="8.6" r="1.1"/></svg>';

  var SOURCE_BY_DOC = {
    contract: 'contract',
    parts: 'parts_billing',
    parts_billing: 'parts_billing',
    invoice: 'invoice',
  };

  function msg(ar, en) {
    return (global.__LC_LANG === 'en' ? en : ar);
  }

  function request(docType, id) {
    if (!docType || !id) return Promise.reject();
    return fetch('/api/financial/whatsapp/' + encodeURIComponent(docType) + '/' + id, {
      credentials: 'same-origin',
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (res) {
        if (!res.ok || !res.data.whatsapp_url) {
          alert(res.data.error || res.data.message || msg('تعذّر تجهيز رسالة واتساب', 'Could not prepare WhatsApp message'));
          return Promise.reject(res.data);
        }
        global.open(res.data.whatsapp_url, '_blank');
        return res.data;
      })
      .catch(function (err) {
        if (err && err.error) throw err;
        alert(msg('تعذّر الاتصال بالخادم', 'Server connection failed'));
        throw err;
      });
  }

  function buttonHtml(docType, id, opts) {
    opts = opts || {};
    var title = opts.title || msg('طلب سداد واتساب', 'WhatsApp payment request');
    var cls = 'lc-wa-btn' + (opts.text ? ' lc-wa-btn-text' : '');
    var label = opts.text ? escHtml(opts.text) : ICON;
    return '<button type="button" class="' + cls + '" title="' + escAttr(title) + '" onclick="event.stopPropagation();LiftCoreFinancialWa.request(\'' + escAttr(docType) + '\',' + Number(id) + ')">' + label + '</button>';
  }

  function collectHref(docType, id, customerId) {
    var st = SOURCE_BY_DOC[docType] || docType;
    var q = 'action=add&source_type=' + encodeURIComponent(st) +
      '&source_id=' + encodeURIComponent(id);
    if (customerId) q += '&customer_id=' + encodeURIComponent(customerId);
    return '/revenues?' + q;
  }

  /** زر تسجيل سداد — يفتح الإيرادات مع المصدر محدداً مسبقاً */
  function collectButtonHtml(docType, id, customerId, opts) {
    opts = opts || {};
    var title = opts.title || msg('تسجيل سداد', 'Record payment');
    var href = collectHref(docType, id, customerId);
    if (opts.text) {
      return '<a class="btn btn-primary btn-sm lc-collect-btn" href="' + escAttr(href) + '" title="' + escAttr(title) + '" onclick="event.stopPropagation()">' +
        PAY_ICON + ' ' + escHtml(opts.text) + '</a>';
    }
    return '<a class="btn btn-secondary btn-sm btn-icon lc-collect-btn" href="' + escAttr(href) + '" title="' + escAttr(title) + '" style="color:var(--success)" onclick="event.stopPropagation()">' + PAY_ICON + '</a>';
  }

  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function escAttr(s) {
    return escHtml(s).replace(/"/g, '&quot;');
  }

  global.LiftCoreFinancialWa = {
    ICON: ICON,
    request: request,
    buttonHtml: buttonHtml,
    collectHref: collectHref,
    collectButtonHtml: collectButtonHtml,
  };
})(window);
