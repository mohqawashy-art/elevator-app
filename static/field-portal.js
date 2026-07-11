(function () {
  'use strict';

  var POLL_MS = 12000;
  var statusEl = document.getElementById('fp-connection-status');
  var pendingEl = document.getElementById('fp-pending-sync');
  var lastStamp = null;
  var knownKeys = null;
  var audioCtx = null;
  var audioUnlocked = false;
  var pollTimer = null;
  var polling = false;

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function visitCard(v) {
    return (
      '<a class="fp-card" href="' + esc(v.url) + '">' +
      '<div class="fp-card-top"><span class="fp-code">' + esc(v.code) + '</span>' +
      '<span style="font-size:11px;color:var(--fp-muted)">' + esc(v.status) + '</span></div>' +
      '<div class="fp-title">' + esc(v.customer) + '</div>' +
      '<div class="fp-meta">' + esc(v.visit_date) + ' · ' + esc(v.elevator) + '</div>' +
      '<span class="fp-district">' + esc(v.district) + '</span></a>'
    );
  }

  function faultCard(f) {
    var pr = f.priority === 'حرجة' ? 'fp-p-critical' : (f.priority === 'عالية' || f.priority === 'عاجلة' ? 'fp-p-high' : 'fp-p-normal');
    var un = f.unassigned ? ' <span style="font-size:11px;color:var(--fp-warning)">(غير معيّن)</span>' : '';
    return (
      '<a class="fp-card" href="' + esc(f.url) + '">' +
      '<div class="fp-card-top"><span class="fp-code">' + esc(f.code) + '</span>' +
      '<span class="fp-priority ' + pr + '">' + esc(f.priority) + '</span></div>' +
      '<div class="fp-title">' + esc(f.customer) + un + '</div>' +
      '<div class="fp-meta">' + esc(f.fault_type) + ' · ' + esc(f.status) + '</div>' +
      '<span class="fp-district">' + esc(f.district) + '</span></a>'
    );
  }

  function collectKeys(payload) {
    var keys = {};
    function add(kind, items) {
      (items || []).forEach(function (item) {
        keys[kind + ':' + item.id] = {
          kind: kind,
          id: item.id,
          code: item.code,
          customer: item.customer,
          status: item.status,
          dispatched_at: item.dispatched_at || '',
          url: item.url,
        };
      });
    }
    add('visit', payload.visits || []);
    add('visit', payload.visits_today || []);
    add('visit', payload.visits_tomorrow || []);
    add('fault', payload.faults || []);
    return keys;
  }

  function renderHome(payload) {
    var root = document.querySelector('.fp-panel[data-fp-panel="all"]');
    if (!root || !payload) return;
    var html = '';
    if (payload.show_visits) {
      html += '<div id="visits"><div class="fp-section">زيارات اليوم <span class="fp-count">' + (payload.visits_today || []).length + '</span></div>';
      if (payload.visits_today && payload.visits_today.length) {
        payload.visits_today.forEach(function (v) { html += visitCard(v); });
      } else {
        html += '<div class="fp-empty">لا توجد زيارات صيانة اليوم</div>';
      }
      html += '<div class="fp-section">زيارات غداً <span class="fp-count">' + (payload.visits_tomorrow || []).length + '</span></div>';
      if (payload.visits_tomorrow && payload.visits_tomorrow.length) {
        payload.visits_tomorrow.forEach(function (v) { html += visitCard(v); });
      } else {
        html += '<div class="fp-empty">لا توجد زيارات غداً</div>';
      }
      html += '</div>';
    }
    if (payload.show_faults) {
      html += '<div id="faults" style="' + (payload.show_visits ? 'margin-top:8px' : '') + '">';
      html += '<div class="fp-section">الأعطال المفتوحة <span class="fp-count">' + (payload.faults || []).length + '</span></div>';
      if (payload.faults && payload.faults.length) {
        payload.faults.forEach(function (f) { html += faultCard(f); });
      } else {
        html += '<div class="fp-empty">لا توجد أعطال مكلفة لك حالياً</div>';
      }
      html += '</div>';
    }
    root.innerHTML = html;
  }

  function renderOfflineHome(payload) {
    renderHome(payload);
    var banner = document.getElementById('fp-offline-banner');
    if (banner) banner.hidden = false;
  }

  function ensureToastHost() {
    var el = document.getElementById('fp-alert-toast');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'fp-alert-toast';
    el.className = 'fp-alert-toast';
    el.hidden = true;
    el.setAttribute('role', 'alert');
    document.body.appendChild(el);
    return el;
  }

  function showToast(items) {
    var el = ensureToastHost();
    var lines = items.map(function (it) {
      var label = it.kind === 'fault' ? 'عطل' : 'زيارة';
      return '<strong>' + esc(label) + '</strong> ' + esc(it.code) + ' — ' + esc(it.customer);
    });
    var firstUrl = items[0] && items[0].url ? items[0].url : '/field';
    el.innerHTML =
      '<div class="fp-alert-toast-inner">' +
      '<div class="fp-alert-toast-title">مهمة جديدة</div>' +
      '<div class="fp-alert-toast-body">' + lines.join('<br>') + '</div>' +
      '<a class="fp-alert-toast-btn" href="' + esc(firstUrl) + '">فتح</a>' +
      '</div>';
    el.hidden = false;
    clearTimeout(el._hideTimer);
    el._hideTimer = setTimeout(function () { el.hidden = true; }, 20000);
  }

  function unlockAudio() {
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      if (!audioCtx) audioCtx = new AC();
      if (audioCtx.state === 'suspended') audioCtx.resume();
      // نغمة صامتة قصيرة لفتح القفل على iOS
      var osc = audioCtx.createOscillator();
      var gain = audioCtx.createGain();
      gain.gain.value = 0.0001;
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.01);
      audioUnlocked = true;
      var tip = document.getElementById('fp-sound-tip');
      if (tip) tip.hidden = true;
    } catch (e) { /* ignore */ }
  }

  function beep(freq, start, dur, vol) {
    if (!audioCtx) return;
    var osc = audioCtx.createOscillator();
    var gain = audioCtx.createGain();
    osc.type = 'sine';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(vol, start + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start(start);
    osc.stop(start + dur + 0.02);
  }

  function playAlertSound() {
    try {
      unlockAudio();
      if (!audioCtx) return;
      var t = audioCtx.currentTime;
      beep(880, t, 0.18, 0.22);
      beep(1175, t + 0.22, 0.18, 0.22);
      beep(880, t + 0.44, 0.28, 0.25);
    } catch (e) { /* ignore */ }
  }

  function vibrateAlert() {
    try {
      if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 400]);
    } catch (e) { /* ignore */ }
  }

  function browserNotify(items) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    try {
      var first = items[0];
      var title = first.kind === 'fault' ? 'عطل جديد' : 'زيارة جديدة';
      var body = (first.code || '') + ' — ' + (first.customer || '');
      var n = new Notification('LiftCore · ' + title, {
        body: body,
        tag: 'liftcore-field-' + first.kind + '-' + first.id,
        renotify: true,
        lang: 'ar',
      });
      n.onclick = function () {
        window.focus();
        if (first.url) window.location.href = first.url;
        n.close();
      };
    } catch (e) { /* ignore */ }
  }

  function detectNewTasks(payload) {
    var nextKeys = collectKeys(payload);
    var stamp = payload.alert_stamp || '';
    if (knownKeys === null) {
      knownKeys = nextKeys;
      lastStamp = stamp;
      return [];
    }
    if (stamp && stamp === lastStamp) {
      knownKeys = nextKeys;
      return [];
    }
    var added = [];
    Object.keys(nextKeys).forEach(function (k) {
      var cur = nextKeys[k];
      var prev = knownKeys[k];
      if (!prev) {
        added.push(cur);
        return;
      }
      // إعادة إرسال: تغيّر dispatched_at أو الحالة إلى مُرسلة
      if (cur.dispatched_at && cur.dispatched_at !== prev.dispatched_at) {
        added.push(cur);
      } else if (cur.status === 'مُرسلة للفني' && prev.status !== 'مُرسلة للفني') {
        added.push(cur);
      }
    });
    knownKeys = nextKeys;
    lastStamp = stamp;
    return added;
  }

  function handleNewTasks(items) {
    if (!items || !items.length) return;
    playAlertSound();
    vibrateAlert();
    showToast(items);
    browserNotify(items);
  }

  function refreshStatus() {
    if (!statusEl) return;
    var online = navigator.onLine;
    statusEl.classList.toggle('offline', !online);
    var offlineApi = window.LiftCoreFieldOffline;
    var done = function (n) {
      var pending = n || 0;
      var pendingText = pending > 0 ? ' · ' + pending + ' معلّق' : '';
      statusEl.innerHTML = online
        ? '<i></i> متصل' + pendingText
        : '<i></i> بدون إنترنت' + pendingText;
      if (pendingEl) {
        pendingEl.hidden = pending === 0;
        pendingEl.textContent = pending + ' محضر بانتظار الرفع';
      }
    };
    if (offlineApi && offlineApi.getPendingCount) {
      offlineApi.getPendingCount().then(done).catch(function () { done(0); });
    } else {
      done(0);
    }
  }

  function pollFieldTasks(opts) {
    opts = opts || {};
    if (polling) return;
    if (!navigator.onLine) return;
    // يعمل على كل صفحات البوابة بعد تسجيل الدخول
    if (!document.getElementById('fp-connection-status') && !document.querySelector('.fp-panel')) return;
    polling = true;
    var offlineApi = window.LiftCoreFieldOffline;
    fetch('/api/field/me', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) {
        if (r.status === 401) throw new Error('auth');
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.ok) return;
        if (offlineApi) offlineApi.cacheMePayload(data);
        var added = detectNewTasks(data);
        if (document.querySelector('.fp-panel[data-fp-panel="all"]')) {
          renderHome(data);
          var banner = document.getElementById('fp-offline-banner');
          if (banner) banner.hidden = true;
        }
        if (!opts.silentBootstrap) handleNewTasks(added);
      })
      .catch(function () {
        if (!offlineApi) return;
        offlineApi.getMePayload().then(function (p) {
          if (p) renderOfflineHome(p);
        });
      })
      .finally(function () {
        polling = false;
        refreshStatus();
      });
  }

  function startPolling() {
    if (pollTimer) return;
    pollFieldTasks({ silentBootstrap: true });
    pollTimer = setInterval(function () {
      if (document.visibilityState === 'hidden') return;
      pollFieldTasks();
    }, POLL_MS);
  }

  function ensureSoundTip() {
    if (!document.getElementById('fp-connection-status')) return;
    if (document.getElementById('fp-sound-tip')) return;
    var tip = document.createElement('button');
    tip.type = 'button';
    tip.id = 'fp-sound-tip';
    tip.className = 'fp-sound-tip';
    tip.textContent = 'تفعيل التنبيه الصوتي';
    tip.addEventListener('click', function () {
      unlockAudio();
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission().catch(function () {});
      }
      playAlertSound();
      tip.hidden = true;
    });
    var header = document.querySelector('.fp-top');
    if (header) header.appendChild(tip);
    else document.body.appendChild(tip);
  }

  function bindOfflineForms() {
    var offlineApi = window.LiftCoreFieldOffline;
    if (!offlineApi) return;
    document.querySelectorAll('form[action*="/field/fault/"]').forEach(function (form) {
      if (form.dataset.fpOfflineBound) return;
      form.dataset.fpOfflineBound = '1';
      form.addEventListener('submit', function (e) {
        if (navigator.onLine) return;
        e.preventDefault();
        var fields = {};
        new FormData(form).forEach(function (val, key) { fields[key] = val; });
        offlineApi.enqueueForm(form.action, fields, { label: form.action }).then(function () {
          alert('📴 حُفظ محلياً — سيُرفع عند عودة الإنترنت');
        });
      });
    });
  }

  window.addEventListener('online', function () {
    refreshStatus();
    pollFieldTasks();
  });
  window.addEventListener('offline', refreshStatus);
  window.addEventListener('liftcore-field-synced', refreshStatus);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') pollFieldTasks();
  });
  // أول لمسة تفتح الصوت على الجوال
  ['touchstart', 'click'].forEach(function (ev) {
    document.addEventListener(ev, function () {
      if (!audioUnlocked) unlockAudio();
    }, { once: false, passive: true });
  });

  refreshStatus();

  document.querySelectorAll('[data-fp-tab]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var tab = btn.getAttribute('data-fp-tab');
      document.querySelectorAll('[data-fp-tab]').forEach(function (b) {
        b.classList.toggle('on', b.getAttribute('data-fp-tab') === tab);
      });
      document.querySelectorAll('[data-fp-panel]').forEach(function (p) {
        p.classList.toggle('on', p.getAttribute('data-fp-panel') === tab);
      });
    });
  });

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/field/sw.js', { scope: '/field/' }).catch(function () {});
  }

  document.addEventListener('DOMContentLoaded', function () {
    ensureSoundTip();
    bindOfflineForms();
    startPolling();
    if (window.LiftCoreFieldOffline) {
      window.LiftCoreFieldOffline.flushQueue();
    }
  });

  window.LiftCoreFieldPortal = {
    refreshStatus: refreshStatus,
    renderOfflineHome: renderOfflineHome,
    pollFieldTasks: pollFieldTasks,
    unlockAudio: unlockAudio,
    playAlertSound: playAlertSound,
  };
})();
