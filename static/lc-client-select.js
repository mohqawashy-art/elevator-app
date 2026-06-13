/** LiftCore — اختيار عميل مع بحث بالاسم أو الكود */
(function (global) {
  'use strict';

  var mounts = {};

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

  global.LcClientSelect = {
    mount: mount,
    setValue: setValue,
    reset: reset,
  };
})(typeof window !== 'undefined' ? window : this);
