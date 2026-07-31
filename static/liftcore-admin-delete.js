/**
 * حذف/إجراء محمي — مسؤول فقط + كلمة مرور.
 * window.__LC_IS_ADMIN يُعرَّف من liftcore_head.
 */
(function (global) {
  'use strict';

  var DEFAULT_TITLE = 'تأكيد الحذف';
  var DEFAULT_CONFIRM = 'حذف نهائي';
  var DEFAULT_TITLE_COLOR = 'var(--danger)';
  var DEFAULT_CONFIRM_CLASS = 'btn btn-danger';

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

  function resetModalChrome(modal) {
    if (!modal) return;
    var title = modal.querySelector('[data-lc-delete-title]');
    var btn = modal.querySelector('[data-lc-delete-confirm]');
    if (title) {
      title.textContent = DEFAULT_TITLE;
      title.style.color = DEFAULT_TITLE_COLOR;
    }
    if (btn) {
      btn.textContent = DEFAULT_CONFIRM;
      btn.className = DEFAULT_CONFIRM_CLASS;
    }
  }

  function applyModalChrome(modal, opts) {
    opts = opts || {};
    var title = modal.querySelector('[data-lc-delete-title]');
    var btn = modal.querySelector('[data-lc-delete-confirm]');
    if (title) {
      title.textContent = opts.title || DEFAULT_TITLE;
      title.style.color = opts.titleColor || DEFAULT_TITLE_COLOR;
    }
    if (btn) {
      btn.textContent = opts.confirmLabel || DEFAULT_CONFIRM;
      btn.className = opts.confirmClass || DEFAULT_CONFIRM_CLASS;
    }
  }

  function postDelete(url, password) {
    var opts = {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-LC-Admin-Delete': '1',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ admin_password: password }),
    };
    return fetch(url, opts).then(function (res) {
      if (res.status === 403 || res.status === 401) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          throw new Error(data.message || msg('غير مصرح أو كلمة المرور خاطئة', 'Not allowed or wrong password'));
        });
      }
      if (!res.ok && !res.redirected) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          throw new Error(data.message || msg('تعذّر الحذف', 'Delete failed'));
        });
      }
      return res;
    });
  }

  function openModal(modal) {
    if (!modal) return;
    /* اجعل نافذة التأكيد فوق أي modal مفتوح (مثل تعديل الفني) */
    if (modal.parentNode) modal.parentNode.appendChild(modal);
    modal.style.zIndex = '9500';
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    var inp = modal.querySelector('.lc-admin-delete-password');
    if (inp) {
      inp.value = '';
      setTimeout(function () { inp.focus(); }, 80);
    }
  }

  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    clearPassword(modal);
    resetModalChrome(modal);
  }

  function guardAdmin() {
    if (!isAdmin()) {
      alert(msg('هذا الإجراء متاح للمسؤول فقط.', 'This action is restricted to administrators.'));
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

  /**
   * يطلب كلمة مرور المسؤول فقط (بدون إرسال طلب).
   * resolve(password) عند التأكيد، reject عند الإلغاء.
   */
  function confirmPassword(opts) {
    opts = opts || {};
    if (!guardAdmin()) return Promise.reject(new Error('not admin'));
    var modal = document.getElementById('lc-admin-delete-modal');
    if (!modal) {
      var pwd = global.prompt(
        opts.prompt || msg('كلمة مرور المسؤول للتأكيد:', 'Admin password to confirm:')
      );
      if (!pwd) return Promise.reject(new Error('cancelled'));
      return Promise.resolve(String(pwd).trim());
    }
    var msgEl = modal.querySelector('[data-lc-delete-message]');
    if (msgEl) {
      msgEl.textContent = opts.message || msg(
        'أدخل كلمة مرور مدير النظام للمتابعة.',
        'Enter the system admin password to continue.'
      );
    }
    applyModalChrome(modal, {
      title: opts.title || msg('موافقة مدير النظام', 'Admin approval'),
      titleColor: opts.titleColor || 'var(--accent)',
      confirmLabel: opts.confirmLabel || msg('تأكيد', 'Confirm'),
      confirmClass: opts.confirmClass || 'btn btn-primary',
    });
    modal.dataset.lcDeleteUrl = '';
    modal.dataset.lcPasswordOnly = '1';
    modal._lcOnSuccess = null;
    openModal(modal);
    return new Promise(function (resolve, reject) {
      modal._lcResolve = function (password) { resolve(password); };
      modal._lcReject = reject;
    });
  }

  /** حوار كامل (رسالة + كلمة مرور) ثم POST للحذف */
  function confirm(opts) {
    opts = opts || {};
    if (!guardAdmin()) return Promise.reject(new Error('not admin'));
    var modal = document.getElementById('lc-admin-delete-modal');
    if (!modal) {
      if (!opts.url) return Promise.reject(new Error('no url'));
      var pwd = global.prompt(msg('كلمة مرور المسؤول للحذف:', 'Admin password to delete:'));
      if (!pwd) return Promise.reject(new Error('cancelled'));
      return postDelete(opts.url, pwd);
    }
    var msgEl = modal.querySelector('[data-lc-delete-message]');
    if (msgEl) msgEl.textContent = opts.message || msg('هل أنت متأكد من الحذف؟', 'Are you sure you want to delete?');
    applyModalChrome(modal, {
      title: opts.title || DEFAULT_TITLE,
      titleColor: opts.titleColor || DEFAULT_TITLE_COLOR,
      confirmLabel: opts.confirmLabel || DEFAULT_CONFIRM,
      confirmClass: opts.confirmClass || DEFAULT_CONFIRM_CLASS,
    });
    modal.dataset.lcDeleteUrl = opts.url || '';
    modal.dataset.lcPasswordOnly = '';
    modal._lcOnSuccess = typeof opts.onSuccess === 'function' ? opts.onSuccess : null;
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
    if (!pwd) {
      alert(msg('أدخل كلمة مرور المسؤول.', 'Enter admin password.'));
      return;
    }
    if (modal.dataset.lcPasswordOnly === '1') {
      var resolvePwd = modal._lcResolve;
      modal._lcResolve = null;
      modal._lcReject = null;
      modal.dataset.lcPasswordOnly = '';
      closeModal(modal);
      if (resolvePwd) resolvePwd(pwd);
      return;
    }
    if (!url) return;
    var btn = modal.querySelector('[data-lc-delete-confirm]');
    if (btn) btn.disabled = true;
    postDelete(url, pwd)
      .then(function (res) {
        var onSuccess = modal._lcOnSuccess;
        var resolve = modal._lcResolve;
        modal._lcOnSuccess = null;
        modal._lcResolve = null;
        modal._lcReject = null;
        closeModal(modal);
        if (typeof onSuccess === 'function') onSuccess(res);
        else if (res.redirected) global.location.href = res.url;
        else global.location.reload();
        if (resolve) resolve(res);
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
    confirmPassword: confirmPassword,
    confirmFromOpenModal: confirmFromOpenModal,
    submitGlobalModal: submitGlobalModal,
    submitForm: submitForm,
    post: function (url, opts) {
      opts = opts || {};
      return confirm({
        url: url,
        message: opts.message || '',
        onSuccess: opts.onSuccess || function () { global.location.reload(); },
      });
    },
  };

  document.addEventListener('DOMContentLoaded', function () {
    hideNonAdminControls();
    var modal = document.getElementById('lc-admin-delete-modal');
    if (modal) {
      modal.querySelectorAll('[data-lc-delete-cancel]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var reject = modal._lcReject;
          modal._lcResolve = null;
          modal._lcReject = null;
          modal.dataset.lcPasswordOnly = '';
          closeModal(modal);
          if (reject) reject(new Error('cancelled'));
        });
      });
      var ok = modal.querySelector('[data-lc-delete-confirm]');
      if (ok) ok.addEventListener('click', submitGlobalModal);
    }
  });
})(window);
