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

  function renderList(state) {
    var list = state.listEl;
    if (!list) return;
    var rows = filterCustomers(state.customers, state.inputEl ? state.inputEl.value : '');
    if (!rows.length) {
      list.innerHTML = '<li class="lc-client-select-empty">لا توجد نتائج</li>';
      list.hidden = false;
      return;
    }
    list.innerHTML = rows.map(function (c) {
      var active = String(state.hiddenEl.value) === String(c.id) ? ' active' : '';
      return '<li class="lc-client-select-item' + active + '" data-id="' + c.id + '" role="option">' +
        esc(labelFor(c)) + '</li>';
    }).join('');
    list.hidden = false;
  }

  function closeList(state) {
    if (state.listEl) state.listEl.hidden = true;
  }

  function pick(state, id) {
    var c = state.customers.find(function (x) { return String(x.id) === String(id); });
    state.hiddenEl.value = c ? String(c.id) : '';
    if (state.inputEl) {
      state.inputEl.value = c ? labelFor(c) : '';
    }
    closeList(state);
    if (typeof state.onChange === 'function') state.onChange();
  }

  function mount(opts) {
    var wrap = typeof opts.wrapId === 'string' ? $(opts.wrapId) : opts.wrapEl;
    if (!wrap) return null;
    var hidden = $(opts.hiddenId);
    var input = $(opts.inputId);
    var list = $(opts.listId);
    if (!hidden || !input || !list) return null;

    var state = {
      wrap: wrap,
      hiddenEl: hidden,
      inputEl: input,
      listEl: list,
      customers: opts.customers || [],
      onChange: opts.onChange || null,
    };
    mounts[opts.wrapId] = state;
    hiddenIndex[opts.hiddenId] = opts.wrapId;

    input.addEventListener('focus', function () { renderList(state); });
    input.addEventListener('input', function () {
      hidden.value = '';
      renderList(state);
    });
    input.addEventListener('keydown', function (e) {
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
    document.addEventListener('click', function (e) {
      if (!wrap.contains(e.target)) closeList(state);
    });

    if (opts.selectedId) setValue(opts.wrapId, opts.selectedId);
    return state;
  }

  function setValue(wrapId, selectedId) {
    var state = mounts[wrapId];
    if (!state) return;
    if (!selectedId) {
      state.hiddenEl.value = '';
      state.inputEl.value = '';
      closeList(state);
      return;
    }
    pick(state, selectedId);
  }

  function reset(wrapId) {
    setValue(wrapId, '');
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
    if (sel.disabled) input.disabled = true;

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
    if (selectedId !== undefined) {
      if (selectedId === null || selectedId === '') setValue(wrapId, '');
      else setValue(wrapId, selectedId);
    }
  }

  function clearSelection(hiddenId) {
    var wrapId = hiddenIndex[hiddenId];
    if (wrapId) setValue(wrapId, '');
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
    isUpgraded: isUpgraded,
    clearSelection: clearSelection,
  };
})(typeof window !== 'undefined' ? window : this);
