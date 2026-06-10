/**
 * LiftCore — تنسيق التاريخ العربي والأكواد (RTL / bidi)
 */
(function (global) {
  'use strict';

  var AR_MONTHS = [
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
  ];

  var EN_MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];

  function isEn() {
    var lang = global.__LC_LANG;
    if (!lang) {
      try { lang = localStorage.getItem('liftcore_lang'); } catch (e) { lang = null; }
    }
    return lang === 'en';
  }

  function MONTHS() {
    return isEn() ? EN_MONTHS : AR_MONTHS;
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  /** تاريخ الهيدر — يمنع انعكاس «يوم» و«يونيو» */
  function headerDateHTML(date, suffix) {
    date = date || new Date();
    suffix = suffix == null ? ' — ' : suffix;
    var html = '';
    if (isEn()) {
      try {
        var enTxt = new Intl.DateTimeFormat('en-US', {
          weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
        }).format(date);
        html = '<span class="ar-header-date" dir="ltr">' + esc(enTxt) + '</span>';
      } catch (e2) {
        html = '<span class="ar-header-date" dir="ltr">' +
          esc(EN_MONTHS[date.getMonth()]) + ' ' + date.getFullYear() + '</span>';
      }
      if (suffix) html += '<span class="ar-header-suffix">' + suffix + '</span>';
      return html;
    }
    try {
      var parts = new Intl.DateTimeFormat('ar-EG', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      }).formatToParts(date);
      html = '<span class="ar-header-date">';
      parts.forEach(function (p) {
        if (p.type === 'literal') {
          html += p.value;
        } else if (p.type === 'day' || p.type === 'year') {
          html += '<bdi dir="ltr" class="lc-num">' + esc(p.value) + '</bdi>';
        } else {
          html += '<bdi dir="rtl">' + esc(p.value) + '</bdi>';
        }
      });
      html += '</span>';
    } catch (e) {
      html = '<span class="ar-header-date"><bdi dir="rtl">' +
        esc(AR_MONTHS[date.getMonth()]) + '</bdi> <bdi dir="ltr" class="lc-num">' +
        date.getFullYear() + '</bdi></span>';
    }
    if (suffix) html += '<span class="ar-header-suffix">' + suffix + '</span>';
    return html;
  }

  function setHeaderDate(el, date, suffix) {
    if (!el) return;
    el.innerHTML = headerDateHTML(date, suffix);
  }

  function monthLabel(ym) {
    if (!ym) return '';
    var p = String(ym).split('-').map(Number);
    if (!p[0] || !p[1]) return ym;
    if (isEn()) return '<bdi dir="ltr">' + esc(EN_MONTHS[p[1] - 1]) + ' ' + p[0] + '</bdi>';
    return '<bdi dir="rtl">' + esc(AR_MONTHS[p[1] - 1]) + '</bdi> <bdi dir="ltr" class="lc-num">' + p[0] + '</bdi>';
  }

  function monthLabelText(ym) {
    if (!ym) return '';
    var p = String(ym).split('-').map(Number);
    return MONTHS()[p[1] - 1] + ' ' + p[0];
  }

  function dateISO(d) {
    if (!d) return '';
    if (typeof d === 'string') return d.slice(0, 10);
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function wrapCode(text) {
    return '<span class="lc-code">' + esc(text) + '</span>';
  }

  function wrapDate(text) {
    return '<span class="lc-date">' + esc(text) + '</span>';
  }

  function initHeaderDates() {
    document.querySelectorAll('#h-date').forEach(function (el) {
      var suffix = el.getAttribute('data-suffix');
      if (suffix == null) suffix = ' — ';
      setHeaderDate(el, new Date(), suffix);
    });
  }

  global.LiftCoreFormat = {
    headerDateHTML: headerDateHTML,
    setHeaderDate: setHeaderDate,
    monthLabel: monthLabel,
    monthLabelText: monthLabelText,
    monthLabelHTML: monthLabel,
    dateISO: dateISO,
    wrapCode: wrapCode,
    wrapDate: wrapDate,
    initHeaderDates: initHeaderDates,
    AR_MONTHS: AR_MONTHS,
    EN_MONTHS: EN_MONTHS,
    MONTHS: MONTHS,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHeaderDates);
  } else {
    initHeaderDates();
  }

  /* عند تبديل اللغة: إعادة رسم تاريخ الهيدر باللغة الجديدة */
  document.addEventListener('liftcore:lang', initHeaderDates);
})(window);
