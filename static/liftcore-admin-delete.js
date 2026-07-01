/**
 * حذف محمي — مسؤول فقط + كلمة مرور.
 * window.__LC_IS_ADMIN يُعرَّف من liftcore_head.
 */
(function (global) {
  'use strict';

  function isAdmin() {
    return !!global.__LC_IS_ADMIN;
  }

  function msg(ar, en) {
    if (global.LC_I18N && LC_I18N.t) return LC_I18N.t(ar, en);
    return (global.__LC_LANG === 'en' ? en : ar);
  }

  function passwordFromModal(modal) {
    if (!modal) return '';
    var inp = modal.querySelector('.lc-admin-delete-password');
    return inp ? String(inp.value || '').trim() : '';
  }

  function clearPassword(modal) {
    if (!modal) return;
    var inp = modal.querySelector('.lc-admin-delete-password');
    if (inp) inp.value = '';
  }

  function postDelete(url, password) {
    var isJson = url.indexOf('/api/') !== -1;
    var opts = {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-LC-Admin-Delete': '1' },
    };
    if (isJson) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify({ admin_password: password });
    } else {
      var fd = new FormData();
      fd.append('admin_password', password);
      opts.body = fd;
    }
    return fetch(url, opts).then(function (res) {
      if (res.status === 403 || res.status === 401) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          throw new Error(data.message || msg('غير مصرح أو كلمة المرور خاطئة', 'Not allowed or wrong password'));
        });
      }
      if (!res.ok && !res.redirected) {
        throw new Error(msg('تعذّر الحذف', 'Delete failed'));
      }
      return res;
    });
  }

  function openModal(modal) {
    if (!modal) return;
    modal.classList.add('open');
    var inp = modal.querySelector('.lc-admin-delete-password');
    if (inp) {
      setTimeout(function () { inp.focus(); }, 80);
    }
  }

  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('open');
    clearPassword(modal);
  }

  function guardAdmin() {
    if (!isAdmin()) {
      alert(msg('الحذف متاح للمسؤول فقط.', 'Delete is restricted to administrators.'));
      return false;
    }
    return true;
  }

  /** تأكيد من نافذة محلية (#modal-delete) مع حقل كلمة المرور */
  function confirmFromOpenModal(url, opts) {
    opts = opts || {};
    if (!guardAdmin()) return Promise.reject();
    var modal = document.getElementById('modal-delete');
    if (!modal || !modal.classList.contains('open')) {
      modal = document.querySelector('.modal-overlay.open');
    }
    var pwd = passwordFromModal(modal);
    if (!pwd) {
      alert(msg('أدخل كلمة مرور المسؤول للتأكيد.', 'Enter your admin password to confirm.'));
      return Promise.reject();
    }
    var btn = modal && modal.querySelector('.btn-danger, [data-lc-delete-confirm]');
    var btnHtml = btn ? btn.innerHTML : '';
    if (btn) {
      btn.disabled = true;
      btn.textContent = msg('جاري الحذف...', 'Deleting...');
    }
    return postDelete(url, pwd)
      .then(function (res) {
        closeModal(modal);
        if (typeof opts.onSuccess === 'function') opts.onSuccess(res);
        else if (res.redirected) global.location.href = res.url;
        else global.location.reload();
      })
      .catch(function (err) {
        alert(err.message || msg('تعذّر الحذف', 'Delete failed'));
        throw err;
      })
      .finally(function () {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = btnHtml;
        }
      });
  }

  /** حوار كامل (رسالة + كلمة مرور) */
  function confirm(opts) {
    opts = opts || {};
    if (!guardAdmin()) return Promise.reject();
    var modal = document.getElementById('lc-admin-delete-modal');
    if (!modal) {
      if (!opts.url) return Promise.reject();
      var pwd = global.prompt(msg('كلمة مرور المسؤول للحذف:', 'Admin password to delete:'));
      if (!pwd) return Promise.reject();
      return postDelete(opts.url, pwd).then(opts.onSuccess || function () { global.location.reload(); });
    }
    var msgEl = modal.querySelector('[data-lc-delete-message]');
    if (msgEl) msgEl.textContent = opts.message || msg('هل أنت متأكد من الحذف؟', 'Are you sure you want to delete?');
    modal.dataset.lcDeleteUrl = opts.url || '';
    openModal(modal);
    return new Promise(function (resolve, reject) {
      modal._lcResolve = resolve;
      modal._lcReject = reject;
    });
  }

  function submitGlobalModal() {
    var modal = document.getElementById('lc-admin-delete-modal');
    if (!modal) return;
    var url = modal.dataset.lcDeleteUrl;
    var pwd = passwordFromModal(modal);
    if (!url) return;
    if (!pwd) {
      alert(msg('أدخل كلمة مرور المسؤول.', 'Enter admin password.'));
      return;
    }
    var btn = modal.querySelector('[data-lc-delete-confirm]');
    if (btn) btn.disabled = true;
    postDelete(url, pwd)
      .then(function (res) {
        closeModal(modal);
        if (modal._lcResolve) modal._lcResolve(res);
        else global.location.reload();
      })
      .catch(function (err) {
        alert(err.message || msg('تعذّر الحذف', 'Delete failed'));
        if (modal._lcReject) modal._lcReject(err);
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  }

  function submitForm(ev, form) {
    if (ev) ev.preventDefault();
    if (!guardAdmin()) return false;
    var modal = document.getElementById('lc-admin-delete-modal');
    var url = form ? form.action : '';
    if (!url) return false;
    confirm({ url: url, message: form.getAttribute('data-delete-message') || '' })
      .then(function () { global.location.reload(); });
    return false;
  }

  function hideNonAdminControls() {
    if (isAdmin()) return;
    document.querySelectorAll('.lc-admin-delete').forEach(function (el) {
      el.style.display = 'none';
    });
  }

  global.LiftCoreAdminDelete = {
    isAdmin: isAdmin,
    confirm: confirm,
    confirmFromOpenModal: confirmFromOpenModal,
    submitGlobalModal: submitGlobalModal,
    submitForm: submitForm,
    post: function (url, opts) {
      opts = opts || {};
      return confirm({ url: url, message: opts.message || '' }).then(
        opts.onSuccess || function () { global.location.reload(); }
      );
    },
  };

  document.addEventListener('DOMContentLoaded', function () {
    hideNonAdminControls();
    var modal = document.getElementById('lc-admin-delete-modal');
    if (modal) {
      modal.querySelectorAll('[data-lc-delete-cancel]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          closeModal(modal);
          if (modal._lcReject) modal._lcReject(new Error('cancelled'));
        });
      });
      var ok = modal.querySelector('[data-lc-delete-confirm]');
      if (ok) ok.addEventListener('click', submitGlobalModal);
    }
  });
})(window);
