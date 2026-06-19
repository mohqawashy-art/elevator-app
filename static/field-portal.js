(function () {
  'use strict';

  var statusEl = document.getElementById('fp-connection-status');

  function updateStatus() {
    if (!statusEl) return;
    var online = navigator.onLine;
    statusEl.classList.toggle('offline', !online);
    statusEl.innerHTML = online
      ? '<i></i> متصل'
      : '<i></i> بدون إنترنت — يعمل محلياً قريباً';
  }

  window.addEventListener('online', updateStatus);
  window.addEventListener('offline', updateStatus);
  updateStatus();

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
})();
