/** LiftCore — اختيار عميل مع بحث بالاسم أو الكود (كل النماذج) */
(function (global) {
  'use strict';

  var mounts = {};
  var hiddenIndex = {};

  function $(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function norm(s) {
    return String(s || '').toLowerCase().trim();
  }

  function labelFor(c) {
    var code = c.code ? c.code + ' — ' : '';
    return code + (c.name || '');
  }

  function parseCustomersFromSelect(sel) {
    var customers = [];
    Array.prototype.forEach.call(sel.options, function (opt) {
      if (!opt.value) return;
      var text = (opt.textContent || '').trim();
      var parts = text.split(' — ');
      customers.push({
        id: opt.value,
        code: parts.length > 1 ? parts[0] : '',
        name: parts.length > 1 ? parts.slice(1).join(' — ') : text,
      });
    });
    return customers;
  }

  function filterCustomers(customers, q) {
    var n = norm(q);
    if (!n) return customers.slice(0, 80);
    return customers.filter(function (c) {
      return norm(c.name).indexOf(n) >= 0 ||
        norm(c.code).indexOf(n) >= 0 ||
        norm(c.city).indexOf(n) >= 0;
    }).slice(0, 80);
  }

  function syncClearBtn(state) {
    if (!state.clearBtn) return;
    var has = !!(state.hiddenEl && state.hiddenEl.value);
    state.clearBtn.hidden = !has || !!(state.inputEl && state.inputEl.disabled);
  }

  function positionList(state) {
    var list = state.listEl;
    var input = state.inputEl;
    if (!list || !input || list.hidden) return;
    var rect = input.getBoundingClientRect();
    var spaceBelow = window.innerHeight - rect.bottom;
    var maxH = 220;
    var openUp = spaceBelow < 160 && rect.top > spaceBelow;
    list.style.position = 'fixed';
    list.style.left = Math.max(8, rect.left) + 'px';
    list.style.width = Math.max(180, rect.width) + 'px';
    list.style.right = 'auto';
    list.style.zIndex = '4000';
    if (openUp) {
      list.style.top = 'auto';
      list.style.bottom = (window.innerHeight - rect.top + 4) + 'px';
      list.style.maxHeight = Math.min(maxH, Math.max(120, rect.top - 12)) + 'px';
    } else {
      list.style.bottom = 'auto';
      list.style.top = (rect.bottom + 4) + 'px';
      list.style.maxHeight = Math.min(maxH, Math.max(120, spaceBelow - 12)) + 'px';
    }
  }

  function renderList(state) {
    var list = state.listEl;
    if (!list) return;
    var q = state.inputEl ? state.inputEl.value : '';
    // عند وجود اختيار سابق، اعرض كل العملاء حتى يكتب المستخدم للتصفية
    if (state.hiddenEl && state.hiddenEl.value && norm(q) === norm(labelFor(
      state.customers.find(function (x) { return String(x.id) === String(state.hiddenEl.value); }) || {}
    ))) {
      q = '';
    }
    var rows = filterCustomers(state.customers, q);
    if (!rows.length) {
      list.innerHTML = '<li class="lc-client-select-empty">لا توجد نتائج</li>';
      list.hidden = false;
      positionList(state);
      return;
    }
    list.innerHTML = rows.map(function (c) {
      var active = String(state.hiddenEl.value) === String(c.id) ? ' active' : '';
      return '<li class="lc-client-select-item' + active + '" data-id="' + c.id + '" role="option">' +
        esc(labelFor(c)) + '</li>';
    }).join('');
    list.hidden = false;
    positionList(state);
  }

  function closeList(state) {
    if (!state.listEl) return;
    state.listEl.hidden = true;
    state.listEl.style.position = '';
    state.listEl.style.left = '';
    state.listEl.style.right = '';
    state.listEl.style.top = '';
    state.listEl.style.bottom = '';
    state.listEl.style.width = '';
    state.listEl.style.maxHeight = '';
    state.listEl.style.zIndex = '';
  }

  function pick(state, id, opts) {
    opts = opts || {};
    var c = state.customers.find(function (x) { return String(x.id) === String(id); });
    state.hiddenEl.value = c ? String(c.id) : '';
    if (state.inputEl) {
      state.inputEl.value = c ? labelFor(c) : '';
    }
    syncClearBtn(state);
    closeList(state);
    if (!opts.silent && typeof state.onChange === 'function') state.onChange();
  }

  function mount(opts) {
    var wrap = typeof opts.wrapId === 'string' ? $(opts.wrapId) : opts.wrapEl;
    if (!wrap) return null;
    var hidden = $(opts.hiddenId);
    var input = $(opts.inputId);
    var list = $(opts.listId);
    if (!hidden || !input || !list) return null;

    var clearBtn = wrap.querySelector('.lc-client-select-clear');
    if (!clearBtn) {
      clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'lc-client-select-clear';
      clearBtn.setAttribute('aria-label', 'مسح العميل');
      clearBtn.title = 'تغيير / مسح العميل';
      clearBtn.innerHTML = '&times;';
      clearBtn.hidden = true;
      wrap.appendChild(clearBtn);
    }

    var state = {
      wrap: wrap,
      hiddenEl: hidden,
      inputEl: input,
      listEl: list,
      clearBtn: clearBtn,
      customers: opts.customers || [],
      onChange: opts.onChange || null,
    };
    mounts[opts.wrapId] = state;
    hiddenIndex[opts.hiddenId] = opts.wrapId;

    input.readOnly = false;
    input.disabled = !!input.disabled;

    input.addEventListener('focus', function () {
      if (input.disabled) return;
      renderList(state);
      // سهّل التعديل: حدّد النص ليُستبدل بالبحث فوراً
      try { input.select(); } catch (e) { /* ignore */ }
    });
    input.addEventListener('input', function () {
      if (input.disabled) return;
      hidden.value = '';
      syncClearBtn(state);
      renderList(state);
    });
    input.addEventListener('keydown', function (e) {
      if (input.disabled) return;
      if (e.key === 'Escape') {
        closeList(state);
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        var first = list.querySelector('.lc-client-select-item[data-id]');
        if (first) pick(state, first.getAttribute('data-id'));
      }
    });
    list.addEventListener('mousedown', function (e) {
      var item = e.target.closest('.lc-client-select-item[data-id]');
      if (!item) return;
      e.preventDefault();
      pick(state, item.getAttribute('data-id'));
    });
    clearBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (input.disabled) return;
      hidden.value = '';
      input.value = '';
      syncClearBtn(state);
      input.focus();
      renderList(state);
      if (typeof state.onChange === 'function') state.onChange();
    });
    document.addEventListener('click', function (e) {
      if (!wrap.contains(e.target) && e.target !== list && !list.contains(e.target)) {
        closeList(state);
      }
    });
    window.addEventListener('resize', function () {
      if (!list.hidden) positionList(state);
    });
    document.addEventListener('scroll', function () {
      if (!list.hidden) positionList(state);
    }, true);

    if (opts.selectedId) setValue(opts.wrapId, opts.selectedId, { silent: true });
    syncClearBtn(state);
    return state;
  }

  function setValue(wrapId, selectedId, opts) {
    opts = opts || {};
    var state = mounts[wrapId];
    if (!state) return;
    if (!selectedId) {
      state.hiddenEl.value = '';
      state.inputEl.value = '';
      syncClearBtn(state);
      closeList(state);
      if (!opts.silent && typeof state.onChange === 'function') state.onChange();
      return;
    }
    pick(state, selectedId, opts);
  }

  function reset(wrapId) {
    setValue(wrapId, '', { silent: true });
  }

  function setDisabled(hiddenId, disabled) {
    var wrapId = hiddenIndex[hiddenId];
    var state = wrapId ? mounts[wrapId] : null;
    var input = state ? state.inputEl : null;
    var sel = $(hiddenId);
    if (input) {
      input.disabled = !!disabled;
      input.readOnly = false;
    }
    if (sel && sel.tagName === 'SELECT') sel.disabled = !!disabled;
    if (state) syncClearBtn(state);
  }

  function isUpgraded(hiddenId) {
    var el = $(hiddenId);
    return !!(el && el.type === 'hidden' && hiddenIndex[hiddenId]);
  }

  function upgradeSelect(selectId, opts) {
    opts = opts || {};
    var sel = $(selectId);
    if (!sel) return null;
    if (sel.tagName !== 'SELECT') {
      if (isUpgraded(selectId)) {
        var existing = mounts[hiddenIndex[selectId]];
        if (existing && opts.onChange) existing.onChange = opts.onChange;
        if (opts.customers) setCustomers(selectId, opts.customers, opts.selectedId);
        setDisabled(selectId, false);
        return existing;
      }
      return null;
    }

    var customers = opts.customers && opts.customers.length ? opts.customers : parseCustomersFromSelect(sel);
    var wrapId = selectId + '-wrap';
    if ($(wrapId)) wrapId = selectId + '-lc-wrap';

    var wrap = document.createElement('div');
    wrap.className = 'lc-client-select';
    wrap.id = wrapId;
    if (sel.style.flex) wrap.style.flex = sel.style.flex;
    if (sel.style.minWidth) wrap.style.minWidth = sel.style.minWidth;

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'lc-client-select-input';
    input.id = selectId + '-input';
    input.placeholder = opts.placeholder || 'ابحث بالاسم أو الكود...';
    input.autocomplete = 'off';
    input.readOnly = false;
    // لا تنقل disabled من select الأصلي في وضع التعديل — الحقل يجب أن يبقى قابلاً للتغيير
    input.disabled = false;

    var hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.id = selectId;
    if (sel.name) hidden.name = sel.name;
    hidden.value = sel.value || '';

    var list = document.createElement('ul');
    list.className = 'lc-client-select-list';
    list.id = selectId + '-list';
    list.hidden = true;
    list.setAttribute('role', 'listbox');

    var onChange = opts.onChange;
    var attrChange = sel.getAttribute('onchange');
    if (!onChange && attrChange) {
      onChange = function () {
        try { (new Function(attrChange)).call(hidden); } catch (e) { /* ignore */ }
      };
    }

    var required = sel.required;
    var form = sel.closest('form');

    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(input);
    wrap.appendChild(hidden);
    wrap.appendChild(list);
    sel.remove();

    if (required && form) {
      form.addEventListener('submit', function (e) {
        if (!hidden.value) {
          e.preventDefault();
          input.focus();
          alert(opts.requiredMessage || 'اختر العميل');
        }
      });
    }

    return mount({
      wrapId: wrapId,
      hiddenId: selectId,
      inputId: input.id,
      listId: list.id,
      customers: customers,
      onChange: onChange,
      selectedId: hidden.value || opts.selectedId || null,
    });
  }

  function setCustomers(hiddenId, customers, selectedId) {
    var wrapId = hiddenIndex[hiddenId];
    if (!wrapId) {
      upgradeSelect(hiddenId, { customers: customers, selectedId: selectedId });
      return;
    }
    var state = mounts[wrapId];
    if (!state) return;
    state.customers = customers || [];
    setDisabled(hiddenId, false);
    if (selectedId !== undefined) {
      if (selectedId === null || selectedId === '') setValue(wrapId, '', { silent: true });
      else setValue(wrapId, selectedId, { silent: true });
    }
    syncClearBtn(state);
  }

  function clearSelection(hiddenId) {
    var wrapId = hiddenIndex[hiddenId];
    if (wrapId) setValue(wrapId, '', { silent: true });
    else {
      var h = $(hiddenId);
      if (h) h.value = '';
    }
  }

  global.LcClientSelect = {
    mount: mount,
    setValue: setValue,
    reset: reset,
    upgradeSelect: upgradeSelect,
    setCustomers: setCustomers,
    setDisabled: setDisabled,
    isUpgraded: isUpgraded,
    clearSelection: clearSelection,
  };
})(typeof window !== 'undefined' ? window : this);
