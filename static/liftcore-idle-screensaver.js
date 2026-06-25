/* LiftCore — شاشة حفظ بالفيديو عند الخمول (دقيقة بدون نشاط) */
(function (global) {
  'use strict';

  var IDLE_MS = 60 * 1000;
  var VIDEO_SRC = '/static/videos/idle-screensaver.mp4';
  var timer = null;
  var overlay = null;
  var video = null;
  var active = false;

  function L(ar, en) {
    if (global.LiftCoreDisplay && global.LiftCoreDisplay.isEn()) return en;
    return ar;
  }

  function ensureOverlay() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.id = 'lc-idle-screensaver';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-label', L('شاشة الحفظ', 'Screensaver'));
    overlay.innerHTML =
      '<video id="lc-idle-screensaver-video" playsinline muted loop preload="auto"></video>'
      + '<div class="lc-idle-hint">' + L('حرّك الماوس أو اضغط أي مفتاح للعودة', 'Move mouse or press any key to return') + '</div>';
    document.body.appendChild(overlay);
    video = overlay.querySelector('video');
    video.src = VIDEO_SRC;
    overlay.addEventListener('click', hide);
    overlay.addEventListener('touchstart', hide, { passive: true });
  }

  function show() {
    if (active) return;
    if (document.body.getAttribute('data-lc-idle-screensaver') === 'off') return;
    ensureOverlay();
    active = true;
    overlay.classList.add('open');
    video.currentTime = 0;
    var playPromise = video.play();
    if (playPromise && typeof playPromise.catch === 'function') {
      playPromise.catch(function () {});
    }
  }

  function hide() {
    if (!active) return;
    active = false;
    overlay.classList.remove('open');
    video.pause();
    schedule();
  }

  function onActivity() {
    if (active) {
      hide();
      return;
    }
    schedule();
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(show, IDLE_MS);
  }

  function init() {
    if (!document.body || document.body.getAttribute('data-lc-idle-screensaver') === 'off') return;

    var events = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'wheel', 'click'];
    events.forEach(function (name) {
      document.addEventListener(name, onActivity, { passive: true });
    });

    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) onActivity();
    });

    schedule();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  global.LiftCoreIdleScreensaver = {
    show: show,
    hide: hide,
    reset: onActivity,
    IDLE_MS: IDLE_MS,
  };
})(typeof window !== 'undefined' ? window : this);
