(function () {
  'use strict';

  function isoToDMY(iso) {
    if (!iso) return '—';
    var s = String(iso).slice(0, 10);
    var p = s.split('-');
    if (p.length !== 3 || p[0].length !== 4) return iso;
    return p[2] + '/' + p[1] + '/' + p[0];
  }

  window.fmtDateDMY = isoToDMY;

  function initDateInputs(root) {
    (root || document).querySelectorAll('input[type="date"], input[type="month"]').forEach(function (el) {
      if (!el.getAttribute('lang')) el.setAttribute('lang', 'en-GB');
      el.classList.add('lc-date-input');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initDateInputs(); });
  } else {
    initDateInputs();
  }
})();
