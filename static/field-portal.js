(function () {
  'use strict';

  var statusEl = document.getElementById('fp-connection-status');
  var pendingEl = document.getElementById('fp-pending-sync');

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
    return (
      '<a class="fp-card" href="' + esc(f.url) + '">' +
      '<div class="fp-card-top"><span class="fp-code">' + esc(f.code) + '</span>' +
      '<span class="fp-priority ' + pr + '">' + esc(f.priority) + '</span></div>' +
      '<div class="fp-title">' + esc(f.customer) + '</div>' +
      '<div class="fp-meta">' + esc(f.fault_type) + ' · ' + esc(f.status) + '</div>' +
      '<span class="fp-district">' + esc(f.district) + '</span></a>'
    );
  }

  function renderOfflineHome(payload) {
    var root = document.querySelector('.fp-panel[data-fp-panel="all"]');
    if (!root || !payload) return;
    var html = '';
    if (payload.show_visits) {
      html += '<div class="fp-section">زيارات اليوم <span class="fp-count">' + (payload.visits_today || []).length + '</span> <span class="fp-cache-tag">محفوظ</span></div>';
      if (payload.visits_today && payload.visits_today.length) {
        payload.visits_today.forEach(function (v) { html += visitCard(v); });
      } else {
        html += '<div class="fp-empty">لا توجد زيارات اليوم</div>';
      }
      html += '<div class="fp-section">زيارات غداً <span class="fp-count">' + (payload.visits_tomorrow || []).length + '</span></div>';
      if (payload.visits_tomorrow && payload.visits_tomorrow.length) {
        payload.visits_tomorrow.forEach(function (v) { html += visitCard(v); });
      } else {
        html += '<div class="fp-empty">لا توجد زيارات غداً</div>';
      }
    }
    if (payload.show_faults) {
      html += '<div class="fp-section" style="margin-top:8px">الأعطال المفتوحة <span class="fp-count">' + (payload.faults || []).length + '</span></div>';
      if (payload.faults && payload.faults.length) {
        payload.faults.forEach(function (f) { html += faultCard(f); });
      } else {
        html += '<div class="fp-empty">لا توجد أعطال</div>';
      }
    }
    root.innerHTML = html;
    var banner = document.getElementById('fp-offline-banner');
    if (banner) banner.hidden = false;
  }

  function refreshStatus() {
    if (!statusEl) return;
    var online = navigator.onLine;
    statusEl.classList.toggle('offline', !online);
    var pending = 0;
    var offlineApi = window.LiftCoreFieldOffline;
    var done = function (n) {
      pending = n || 0;
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

  window.addEventListener('online', refreshStatus);
  window.addEventListener('offline', refreshStatus);
  window.addEventListener('liftcore-field-synced', refreshStatus);
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

  function refreshHomeFromApi() {
    if (!document.querySelector('.fp-panel[data-fp-panel="all"]')) return;
    var offlineApi = window.LiftCoreFieldOffline;
    fetch('/api/field/me', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.ok && offlineApi) offlineApi.cacheMePayload(data);
      })
      .catch(function () {
        if (!offlineApi) return;
        offlineApi.getMePayload().then(function (p) {
          if (p) renderOfflineHome(p);
        });
      });
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

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/field/sw.js', { scope: '/field/' }).catch(function () {});
  }

  document.addEventListener('DOMContentLoaded', function () {
    refreshHomeFromApi();
    bindOfflineForms();
    if (window.LiftCoreFieldOffline) {
      window.LiftCoreFieldOffline.flushQueue();
    }
  });

  window.LiftCoreFieldPortal = {
    refreshStatus: refreshStatus,
    renderOfflineHome: renderOfflineHome,
  };
})();
