/* LiftCore — شاشة حفظ بالفيديو + قفل بكلمة المرور عند الخروج */
(function (global) {
  'use strict';

  var IDLE_MS = 60 * 1000;
  var VIDEO_SRC = '/static/videos/idle-screensaver.mp4';
  var timer = null;
  var overlay = null;
  var video = null;
  var unlockPanel = null;
  var passwordInput = null;
  var unlockBtn = null;
  var errorEl = null;
  var LOGO_SRC = '/static/images/liftcore-brand-logo.png?v=3';
  var active = false;
  var unlockVisible = false;
  var unlocking = false;

  function L(ar, en) {
    if (global.LiftCoreDisplay && global.LiftCoreDisplay.isEn()) return en;
    return ar;
  }

  function userLabel() {
    return global.__LC_USER_NAME || global.__LC_USER || '';
  }

  function ensureOverlay() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.id = 'lc-idle-screensaver';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', L('شاشة الحفظ', 'Screensaver'));
    overlay.innerHTML =
      '<video id="lc-idle-screensaver-video" playsinline muted loop preload="auto"></video>'
      + '<div class="lc-idle-hint">' + L('حرّك الماوس أو اضغط أي مفتاح لإدخال كلمة المرور', 'Move mouse or press a key to unlock') + '</div>'
      + '<div class="lc-idle-unlock" hidden>'
      + '  <div class="lc-idle-unlock-card">'
      + '    <div class="lc-idle-track" aria-hidden="true"><div class="rail"></div><div class="trace"></div><div class="pulse"></div></div>'
      + '    <img class="lc-idle-logo" src="' + (global.__LC_BRAND_LOGO || LOGO_SRC) + '" alt="LiftCore">'
      + '    <div class="lc-idle-unlock-title">' + L('الجلسة مقفلة', 'Session locked') + '</div>'
      + '    <div class="lc-idle-unlock-user" id="lc-idle-unlock-user"></div>'
      + '    <div class="lc-idle-field">'
      + '      <label for="lc-idle-unlock-pw">' + L('كلمة المرور', 'Password') + '</label>'
      + '      <div class="lc-idle-input-wrap">'
      + '        <input type="password" id="lc-idle-unlock-pw" class="lc-idle-unlock-input" autocomplete="current-password" placeholder="••••••••" />'
      + '        <span class="lc-idle-ic" aria-hidden="true">⚿</span>'
      + '      </div>'
      + '    </div>'
      + '    <button type="button" id="lc-idle-unlock-btn" class="lc-idle-unlock-btn">'
      + '      <span class="lc-idle-spin" aria-hidden="true"></span><span>' + L('فتح البرنامج', 'Unlock') + '</span>'
      + '    </button>'
      + '    <div class="lc-idle-unlock-err" id="lc-idle-unlock-err" role="alert"></div>'
      + '    <div class="lc-idle-footer">LIFTCORE · 2026</div>'
      + '  </div>'
      + '</div>';
    document.body.appendChild(overlay);

    video = overlay.querySelector('video');
    video.src = VIDEO_SRC;
    unlockPanel = overlay.querySelector('.lc-idle-unlock');
    passwordInput = overlay.querySelector('#lc-idle-unlock-pw');
    unlockBtn = overlay.querySelector('#lc-idle-unlock-btn');
    errorEl = overlay.querySelector('#lc-idle-unlock-err');

    refreshUnlockUser();

    unlockBtn.addEventListener('click', tryUnlock);
    passwordInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        tryUnlock();
      }
    });

    overlay.addEventListener('mousedown', onOverlayInteract);
    overlay.addEventListener('touchstart', onOverlayInteract, { passive: true });
    overlay.addEventListener('keydown', onOverlayKey);
  }

  function onOverlayInteract(e) {
    if (!active) return;
    if (unlockPanel && unlockPanel.contains(e.target)) return;
    if (!unlockVisible) showUnlock();
  }

  function onOverlayKey(e) {
    if (!active) return;
    if (unlockVisible && unlockPanel && unlockPanel.contains(e.target)) return;
    if (!unlockVisible) {
      e.preventDefault();
      showUnlock();
    }
  }

  function refreshUnlockUser() {
    var userEl = overlay && overlay.querySelector('#lc-idle-unlock-user');
    if (userEl) userEl.textContent = userLabel();
  }

  function setUnlockLoading(on) {
    if (unlockBtn) unlockBtn.classList.toggle('loading', !!on);
  }

  function showUnlock() {
    if (!active || unlockVisible) return;
    unlockVisible = true;
    overlay.classList.add('unlock');
    if (unlockPanel) unlockPanel.hidden = false;
    refreshUnlockUser();
    if (errorEl) errorEl.textContent = '';
    setUnlockLoading(false);
    if (passwordInput) {
      passwordInput.value = '';
      setTimeout(function () { passwordInput.focus(); }, 50);
    }
  }

  function show() {
    if (active) return;
    if (document.body.getAttribute('data-lc-idle-screensaver') === 'off') return;
    ensureOverlay();
    active = true;
    unlockVisible = false;
    document.body.classList.add('lc-idle-locked');
    overlay.classList.remove('unlock');
    if (unlockPanel) unlockPanel.hidden = true;
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
    unlockVisible = false;
    unlocking = false;
    setUnlockLoading(false);
    document.body.classList.remove('lc-idle-locked');
    overlay.classList.remove('open', 'unlock');
    if (unlockPanel) unlockPanel.hidden = true;
    if (passwordInput) passwordInput.value = '';
    if (errorEl) errorEl.textContent = '';
    video.pause();
    schedule();
  }

  function tryUnlock() {
    if (!active || unlocking || !passwordInput) return;
    var pw = passwordInput.value || '';
    if (!pw) {
      if (errorEl) errorEl.textContent = L('أدخل كلمة المرور', 'Enter your password');
      passwordInput.focus();
      return;
    }
    unlocking = true;
    setUnlockLoading(true);
    if (errorEl) errorEl.textContent = '';
    fetch('/api/session/unlock', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pw }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        unlocking = false;
        setUnlockLoading(false);
        if (result.ok && result.data && result.data.ok) {
          hide();
          return;
        }
        var msg = (result.data && result.data.error)
          || L('كلمة المرور غير صحيحة', 'Incorrect password');
        if (errorEl) errorEl.textContent = msg;
        if (passwordInput) {
          passwordInput.select();
          passwordInput.focus();
        }
        var card = unlockPanel && unlockPanel.querySelector('.lc-idle-unlock-card');
        if (card) card.classList.add('shake');
        setTimeout(function () {
          if (card) card.classList.remove('shake');
        }, 450);
      })
      .catch(function () {
        unlocking = false;
        setUnlockLoading(false);
        if (errorEl) errorEl.textContent = L('تعذّر التحقق — حاول مرة أخرى', 'Unlock failed — try again');
      });
  }

  function onActivity(e) {
    if (active) {
      if (e && e.type === 'keydown' && unlockVisible) return;
      if (!unlockVisible) showUnlock();
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
      document.addEventListener(name, onActivity, { passive: name !== 'keydown' });
    });

    document.addEventListener('visibilitychange', function () {
      if (!document.hidden && !active) schedule();
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
    reset: schedule,
    IDLE_MS: IDLE_MS,
  };
})(typeof window !== 'undefined' ? window : this);
