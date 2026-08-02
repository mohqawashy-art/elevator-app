/** LiftCore — اختيار عميل مع بحث بالاسم أو الكود (كل النماذج) */
(function (global) {
  'use strict';

  var mounts = {};
  var hiddenIndex = {};
  var openState = null;
  var MAX_LIST_H = 220;
  var GAP = 4;
  var EDGE = 8;

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

  /* القائمة تُنقل إلى <body> وتُثبّت بالإحداثيات حتى لا يفسدها transform/overflow
     على النوافذ المنبثقة أو الحاويات الأب. */
  function detach(state) {
    var list = state.listEl;
    if (list && list.parentNode !== document.body) {
      list.classList.add('lc-client-select-floating');
      if (state.inputEl) {
        list.style.direction = getComputedStyle(state.inputEl).direction;
      }
      document.body.appendChild(list);
    }
  }

  function isVisible(el) {
    var node = el;
    while (node && node.nodeType === 1) {
      var cs = getComputedStyle(node);
      if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
      node = node.parentElement;
    }
    return true;
  }

  function positionList(state) {
    var list = state.listEl;
    var anchor = state.inputEl;
    if (!list || !anchor || list.hidden) return;
    var r = anchor.getBoundingClientRect();
    /* أثناء أنيمشن فتح النافذة تكون visibility/opacity غير مستقرة، فلا نحكم
       باختفاء الحقل إلا بعد استقرارها. */
    var settled = Date.now() - (state.openedAt || 0) > 400;
    var gone = !document.body.contains(anchor) ||
      (settled && ((!r.width && !r.height) || !isVisible(anchor)));
    if (gone) {
      closeList(state);
      return;
    }
    var key = [r.left, r.top, r.width, r.height, window.innerWidth, window.innerHeight].join(',');
    if (key === state.rectKey) return;
    state.rectKey = key;

    var left = Math.max(EDGE, Math.min(r.left, window.innerWidth - r.width - EDGE));
    list.style.position = 'fixed';
    list.style.width = Math.max(180, r.width) + 'px';
    list.style.left = left + 'px';
    list.style.right = 'auto';
    list.style.zIndex = '9100';
    list.style.maxHeight = MAX_LIST_H + 'px';

    var needed = Math.min(MAX_LIST_H, list.offsetHeight || MAX_LIST_H);
    var below = window.innerHeight - r.bottom - GAP - EDGE;
    var above = r.top - GAP - EDGE;
    if (below < needed && above > below) {
      var h = Math.min(needed, Math.max(120, above));
      list.style.maxHeight = h + 'px';
      list.style.bottom = (window.innerHeight - r.top + GAP) + 'px';
      list.style.top = 'auto';
    } else {
      list.style.maxHeight = Math.min(MAX_LIST_H, Math.max(120, below)) + 'px';
      list.style.top = (r.bottom + GAP) + 'px';
      list.style.bottom = 'auto';
    }
  }

  function openList(state) {
    detach(state);
    state.listEl.hidden = false;
    state.rectKey = null;
    state.openedAt = Date.now();
    openState = state;
    positionList(state);
    startTracking();
  }

  var tracking = false;
  function startTracking() {
    if (tracking || typeof requestAnimationFrame !== 'function') return;
    tracking = true;
    (function step() {
      if (!openState) {
        tracking = false;
        return;
      }
      positionList(openState);
      requestAnimationFrame(step);
    })();
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
      openList(state);
      return;
    }
    list.innerHTML = rows.map(function (c) {
      var active = String(state.hiddenEl.value) === String(c.id) ? ' active' : '';
      return '<li class="lc-client-select-item' + active + '" data-id="' + c.id + '" role="option">' +
        esc(labelFor(c)) + '</li>';
    }).join('');
    openList(state);
  }

  function closeList(state) {
    var list = state.listEl;
    if (list) {
      list.hidden = true;
      list.style.position = '';
      list.style.left = '';
      list.style.right = '';
      list.style.top = '';
      list.style.bottom = '';
      list.style.width = '';
      list.style.maxHeight = '';
      list.style.zIndex = '';
      var orphan = state.inputEl && !document.body.contains(state.inputEl);
      if (orphan && list.parentNode === document.body) list.remove();
    }
    if (openState === state) openState = null;
  }

  function reposition() {
    if (openState) positionList(openState);
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
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
    var stale = mounts[opts.wrapId];
    if (stale && stale.listEl && stale.listEl.parentNode === document.body) {
      closeList(stale);
      stale.listEl.remove();
    }
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
      try { input.select(); } catch (e) { /* ignore */ }
    });
    list.addEventListener('mouseenter', function () { state.hover = true; });
    list.addEventListener('mouseleave', function () { state.hover = false; });
    input.addEventListener('blur', function () {
      setTimeout(function () {
        if (!state.hover && document.activeElement !== input) closeList(state);
      }, 120);
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
