(function () {
  'use strict';

  function isPopupContext() {
    if (document.body && document.body.getAttribute('data-lc-popup') === '1') return true;
    var q = window.location.search || '';
    return /(?:^|[?&])(popup|print)=1(?:&|$)/.test(q);
  }

  function withPopupParam(url) {
    if (!url || url === '#') return url;
    try {
      var u = new URL(url, window.location.origin);
      if (!u.searchParams.has('popup')) u.searchParams.set('popup', '1');
      return u.pathname + u.search + u.hash;
    } catch (e) {
      return url + (url.indexOf('?') >= 0 ? '&' : '?') + 'popup=1';
    }
  }

  function openTab(url, e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (!url || url === '#') return false;
    window.open(withPopupParam(url), '_blank');
    return false;
  }

  function goBack(url) {
    var popup = isPopupContext();

    if (popup || (window.opener && !window.opener.closed)) {
      try {
        if (window.opener && !window.opener.closed) window.opener.focus();
      } catch (e) { /* ignore */ }
      window.close();
      setTimeout(function () {
        if (window.closed) return;
        if (window.history.length > 1) {
          window.history.back();
          return;
        }
        if (url) window.location.href = url;
      }, 120);
      return;
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
        var href = a.getAttribute('data-lc-back') || a.getAttribute('href');
        if (!href || href === '#') return;
        e.preventDefault();
        // نافذة منبثقة / طباعة: أغلق أو ارجع
        if (isPopupContext() || (window.opener && !window.opener.closed)) {
          goBack(href);
          return;
        }
        // صفحة عادية (مثل الإعدادات): اذهب للوجهة صراحةً — لا history.back()
        // وإلا قد يعود المستخدم لصفحة الدخول ويظن أن لوحة التحكم لا تفتح.
        window.location.href = href;
      });
    });
  }

  function bindOpenTabLinks(root) {
    (root || document).querySelectorAll('a.lc-open-tab, a[data-lc-open-tab]').forEach(function (a) {
      if (a.dataset.lcOpenTabBound) return;
      a.dataset.lcOpenTabBound = '1';
      a.removeAttribute('target');
      a.addEventListener('click', function (e) {
        openTab(a.getAttribute('href'), e);
      });
    });
  }

  function init() {
    bindBackLinks();
    bindOpenTabLinks();
  }

  window.LiftCoreNav = {
    goBack: goBack,
    openTab: openTab,
    bindBackLinks: bindBackLinks,
    bindOpenTabLinks: bindOpenTabLinks,
    isPopupContext: isPopupContext,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
