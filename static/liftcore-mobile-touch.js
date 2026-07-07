/**
 * LiftCore — إصلاح تمرير/لمس الجوال والتابلت (PWA + iOS)
 * يفرض تمرير الصفحة الطبيعي ويزيل أي حبس overflow.
 */
(function (global) {
  'use strict';

  var MOBILE_MQ = '(max-width: 1100px)';

  function isMobile() {
    return !!(global.matchMedia && global.matchMedia(MOBILE_MQ).matches);
  }

  function unfreezeAll() {
    document.querySelectorAll('.content.lc-frozen-layout').forEach(function (el) {
      el.classList.remove('lc-frozen-layout');
    });
    document.querySelectorAll('.lc-table-scroll-host').forEach(function (el) {
      el.style.removeProperty('overflow');
      el.style.removeProperty('max-height');
    });
  }

  function applyNativeScroll() {
    if (!isMobile()) {
      document.documentElement.classList.remove('lc-mobile-scroll', 'lc-mobile-native');
      document.body && document.body.classList.remove('lc-mobile-native');
      return;
    }

    var root = document.documentElement;
    var body = document.body;
    if (!body) return;

    root.classList.add('lc-mobile-scroll', 'lc-mobile-native');
    body.classList.add('lc-mobile-native');

    var standalone = !!(global.matchMedia && global.matchMedia('(display-mode: standalone)').matches);
    root.classList.toggle('lc-pwa-standalone', standalone);

    unfreezeAll();

    /* تجاوز inline/CSS المتبقي — آخر خط دفاع */
    body.style.setProperty('overflow-x', 'hidden', 'important');
    body.style.setProperty('overflow-y', 'auto', 'important');
    body.style.setProperty('height', 'auto', 'important');
    body.style.setProperty('max-height', 'none', 'important');
    body.style.setProperty('min-height', '100dvh', 'important');
    body.style.setProperty('-webkit-overflow-scrolling', 'touch', 'important');
    body.style.setProperty('touch-action', 'pan-y', 'important');

    if (!standalone) {
      body.style.setProperty(
        'padding-bottom',
        'max(80px, calc(env(safe-area-inset-bottom, 0px) + 56px))',
        'important'
      );
    } else {
      body.style.removeProperty('padding-bottom');
    }

    root.style.setProperty('overflow-y', 'auto', 'important');
    root.style.setProperty('height', 'auto', 'important');

    var main = document.querySelector('.main');
    if (main) {
      main.style.setProperty('overflow', 'visible', 'important');
      main.style.setProperty('height', 'auto', 'important');
      main.style.setProperty('display', 'block', 'important');
    }

    document.querySelectorAll('.main > .content, .content').forEach(function (el) {
      if (!el.closest('.modal-overlay') && !el.closest('#lc-idle-screensaver')) {
        el.style.setProperty('overflow', 'visible', 'important');
        el.style.setProperty('height', 'auto', 'important');
        el.style.setProperty('max-height', 'none', 'important');
        el.style.setProperty('flex', 'none', 'important');
      }
    });

    var header = document.querySelector('.lc-header, header.lc-header');
    if (header) {
      header.style.setProperty('height', 'auto', 'important');
      header.style.setProperty('max-height', 'none', 'important');
      header.style.setProperty('position', 'sticky', 'important');
      header.style.setProperty('top', '0', 'important');
    }
  }

  function boot() {
    applyNativeScroll();
    unfreezeAll();
    requestAnimationFrame(function () {
      applyNativeScroll();
      unfreezeAll();
    });
    setTimeout(function () {
      applyNativeScroll();
      unfreezeAll();
    }, 120);
    setTimeout(unfreezeAll, 600);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  global.addEventListener('resize', boot);
  global.addEventListener('orientationchange', function () {
    setTimeout(boot, 100);
  });

  document.addEventListener('liftcore:live-sync', boot);

  if (global.MutationObserver) {
    var obs = new MutationObserver(function (mutations) {
      if (!isMobile()) return;
      for (var i = 0; i < mutations.length; i++) {
        var m = mutations[i];
        if (m.type === 'attributes' && m.attributeName === 'class') {
          var t = m.target;
          if (t && t.classList && t.classList.contains('lc-frozen-layout')) {
            t.classList.remove('lc-frozen-layout');
          }
        }
      }
    });
    obs.observe(document.documentElement, { subtree: true, attributes: true, attributeFilter: ['class'] });
  }

  global.LiftCoreMobileTouch = { refresh: boot, unfreeze: unfreezeAll };
})(typeof window !== 'undefined' ? window : this);
