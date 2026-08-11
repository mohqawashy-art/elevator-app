/* LiftCore — دعم المنصة: فتح/إغلاق لوحة واتساب + بريد */
(function () {
  'use strict';

  function closestSupport(el) {
    while (el && el !== document) {
      if (el.classList && el.classList.contains('lc-support')) return el;
      el = el.parentNode;
    }
    return null;
  }

  function closeAll(except) {
    document.querySelectorAll('.lc-support.is-open').forEach(function (node) {
      if (except && node === except) return;
      node.classList.remove('is-open');
      var btn = node.querySelector('.lc-support__btn');
      if (btn) btn.setAttribute('aria-expanded', 'false');
    });
  }

  document.addEventListener('click', function (e) {
    var root = closestSupport(e.target);
    var btn = e.target.closest ? e.target.closest('.lc-support__btn') : null;
    if (btn && root) {
      e.preventDefault();
      var open = !root.classList.contains('is-open');
      closeAll(root);
      root.classList.toggle('is-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      return;
    }
    if (!root) closeAll();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll();
  });
})();
