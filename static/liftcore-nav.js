(function () {
  'use strict';

  function goBack(url) {
    if (window.opener && !window.opener.closed) {
      try {
        window.opener.focus();
        window.close();
        return;
      } catch (e) { /* ignore */ }
    }
    if (window.history.length > 1) {
      var ref = document.referrer || '';
      try {
        if (!url || (ref && new URL(ref, window.location.origin).origin === window.location.origin)) {
          window.history.back();
          return;
        }
      } catch (e2) { /* ignore */ }
    }
    if (url) window.location.href = url;
  }

  function bindBackLinks(root) {
    (root || document).querySelectorAll('a[data-lc-back], a.lc-back-link, a.back-btn, a.btn-back, a.back').forEach(function (a) {
      if (a.dataset.lcBackBound) return;
      a.dataset.lcBackBound = '1';
      a.addEventListener('click', function (e) {
        var url = a.getAttribute('data-lc-back') || a.getAttribute('href');
        if (!url || url === '#') return;
        e.preventDefault();
        goBack(url);
      });
    });
  }

  window.LiftCoreNav = { goBack: goBack, bindBackLinks: bindBackLinks };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { bindBackLinks(); });
  } else {
    bindBackLinks();
  }
})();
