/** LiftCore — اختيار متعدد لفلاتر الجداول (حالة، نوع، عميل، …) */
(function (global) {
  'use strict';

  var nativeValue = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
  var openState = null;
  var SEARCH_MIN = 8;

  function $(id) {
    return typeof id === 'string' ? document.getElementById(id) : id;
  }

  function lang() {
    return global.__LC_LANG || document.documentElement.getAttribute('lang') || 'ar';
  }

  function isEn() {
    return lang() === 'en';
  }

  function optionVal(opt) {
    if (!opt) return '';
    return String(opt.value != null ? opt.value : '').trim();
  }

  function optionLabel(opt) {
    return String((opt && (opt.textContent || opt.label)) || '').replace(/\s+/g, ' ').trim();
  }

  function realOptions(sel) {
    return Array.prototype.filter.call(sel.options || [], function (o) {
      return optionVal(o) !== '';
    });
  }

  function emptyOption(sel) {
    return Array.prototype.find.call(sel.options || [], function (o) {
      return optionVal(o) === '';
    }) || null;
  }

  function optionExists(sel, value) {
    return Array.prototype.some.call(sel.options || [], function (o) {
      return optionVal(o) === String(value);
    });
  }

  function labelFor(sel, value) {
    var found = Array.prototype.find.call(sel.options || [], function (o) {
      return optionVal(o) === String(value);
    });
    return found ? optionLabel(found) : String(value);
  }

  function unique(arr) {
    var seen = {};
    return arr.filter(function (v) {
      v = String(v);
      if (!v || seen[v]) return false;
      seen[v] = 1;
      return true;
    });
  }

  function values(el) {
    el = $(el);
    if (!el) return [];
    if (el._lcMulti) return (el._lcSelected || []).slice();
    var v = nativeValue && nativeValue.get ? nativeValue.get.call(el) : el.value;
    return v ? [String(v)] : [];
  }

  function summary(el) {
    el = $(el);
    if (!el) return '';
    var vals = values(el);
    if (!vals.length) return '';
    return vals.map(function (v) { return labelFor(el, v); }).join('، ');
  }

  function allows(el, actual, opts) {
    el = $(el);
    if (!el) return true;
    var vals = values(el);
    if (!vals.length) return true;
    opts = opts || {};
    if (typeof opts === 'function') opts = { test: opts };
    return vals.some(function (v) {
      if (opts.test) return !!opts.test(v);
      if (String(actual) === String(v)) return true;
      var extra = opts.aliases && opts.aliases[v];
      if (!extra) return false;
      if (typeof extra === 'string') extra = [extra];
      return extra.indexOf(String(actual)) >= 0;
    });
  }

  function shouldUpgrade(sel) {
    if (!sel || sel.tagName !== 'SELECT' || sel._lcMulti) return false;
    if (sel.dataset.lcNoMulti === '1' || sel.classList.contains('plan-team-sel')) return false;
    if (sel.closest('.modal-overlay, .modal, .lc-client-select, .client-card, .lc-filter-multi-panel')) return false;
    var id = sel.id || '';
    if (id === 'sel-year' || id === 'sel-month') return false;
    if (/-sel$/.test(id)) return false;
    if (sel.classList.contains('filter-select')) {
      if (sel.name && !sel.closest('.filters-bar, .filter-group, .filter-row, .filter-card')) return false;
      return true;
    }
    return !!sel.closest('.filters-bar, .filter-row, .filter-group, .filter-card');
  }

  function allLabel(sel) {
    var empty = emptyOption(sel);
    var text = empty ? optionLabel(empty) : '';
    return text || (isEn() ? 'All' : 'الكل');
  }

  function buttonText(sel) {
    var vals = values(sel);
    if (!vals.length) return allLabel(sel);
    if (vals.length === 1) return labelFor(sel, vals[0]);
    if (vals.length === 2) return labelFor(sel, vals[0]) + ' + ' + labelFor(sel, vals[1]);
    return labelFor(sel, vals[0]) + ' +' + (vals.length - 1);
  }

  function refreshButton(sel) {
    var state = sel._lcMulti;
    if (!state || !state.btn) return;
    var n = (sel._lcSelected || []).length;
    state.btn.classList.toggle('has-values', n > 0);
    state.labelEl.textContent = buttonText(sel);
    if (state.countEl) state.countEl.textContent = String(n);
    state.btn.title = n ? summary(sel) : '';
    state.btn.setAttribute('aria-expanded', state.panel && state.panel.classList.contains('open') ? 'true' : 'false');
  }

  function setSelected(sel, vals, fire) {
    vals = unique((vals || []).map(String).filter(function (v) {
      return v !== '' && optionExists(sel, v);
    }));
    sel._lcSelected = vals;
    Array.prototype.forEach.call(sel.options || [], function (o) {
      o.selected = vals.indexOf(optionVal(o)) >= 0;
    });
    refreshButton(sel);
    syncChecks(sel);
    if (fire) {
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  function syncChecks(sel) {
    var state = sel._lcMulti;
    if (!state || !state.panel) return;
    var selected = sel._lcSelected || [];
    state.panel.querySelectorAll('.lc-filter-multi-item[data-value]').forEach(function (row) {
      var box = row.querySelector('input[type="checkbox"]');
      if (box) box.checked = selected.indexOf(row.getAttribute('data-value')) >= 0;
    });
    var allBox = state.panel.querySelector('input[data-all]');
    if (allBox) allBox.checked = selected.length === 0;
  }

  function rebuildPanel(sel) {
    var state = sel._lcMulti;
    if (!state || !state.list) return;
    var opts = realOptions(sel);
    var html = '<label class="lc-filter-multi-item is-all"><input type="checkbox" data-all="1"> <span></span></label>';
    if (!opts.length) {
      html += '<div class="lc-filter-multi-empty">' + (isEn() ? 'No options' : 'لا خيارات') + '</div>';
    } else {
      html += opts.map(function (o) {
        var v = optionVal(o);
        var lab = optionLabel(o);
        return '<label class="lc-filter-multi-item" data-value="' + escapeAttr(v) + '">' +
          '<input type="checkbox" value="' + escapeAttr(v) + '"> <span></span></label>';
      }).join('');
    }
    state.list.innerHTML = html;
    var allSpan = state.list.querySelector('.is-all span');
    if (allSpan) allSpan.textContent = allLabel(sel);
    Array.prototype.forEach.call(state.list.querySelectorAll('.lc-filter-multi-item[data-value]'), function (row, i) {
      var span = row.querySelector('span');
      if (span && opts[i]) span.textContent = optionLabel(opts[i]);
    });
    var showSearch = opts.length >= SEARCH_MIN;
    if (state.searchWrap) state.searchWrap.hidden = !showSearch;
    if (state.searchInput && !showSearch) state.searchInput.value = '';
    filterPanelSearch(sel);
    syncChecks(sel);
  }

  function escapeAttr(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;');
  }

  function filterPanelSearch(sel) {
    var state = sel._lcMulti;
    if (!state || !state.searchInput) return;
    var q = String(state.searchInput.value || '').trim().toLowerCase();
    state.list.querySelectorAll('.lc-filter-multi-item[data-value]').forEach(function (row) {
      var t = (row.textContent || '').toLowerCase();
      row.style.display = !q || t.indexOf(q) >= 0 ? '' : 'none';
    });
  }

  function closePanel() {
    if (!openState) return;
    openState.panel.classList.remove('open');
    openState.btn.setAttribute('aria-expanded', 'false');
    openState = null;
  }

  function positionPanel(state) {
    var r = state.btn.getBoundingClientRect();
    var panel = state.panel;
    var rtl = document.documentElement.getAttribute('dir') === 'rtl';
    panel.style.minWidth = Math.max(r.width, 180) + 'px';
    panel.style.top = (r.bottom + 4) + 'px';
    if (rtl) {
      panel.style.right = (window.innerWidth - r.right) + 'px';
      panel.style.left = 'auto';
    } else {
      panel.style.left = r.left + 'px';
      panel.style.right = 'auto';
    }
    var ph = panel.offsetHeight;
    if (r.bottom + 4 + ph > window.innerHeight - 8 && r.top > ph + 8) {
      panel.style.top = (r.top - 4 - ph) + 'px';
    }
  }

  function openPanel(sel) {
    var state = sel._lcMulti;
    if (!state) return;
    if (openState && openState !== state) closePanel();
    if (state.panel.classList.contains('open')) {
      closePanel();
      return;
    }
    rebuildPanel(sel);
    state.panel.classList.add('open');
    openState = state;
    positionPanel(state);
    refreshButton(sel);
    if (state.searchInput && !state.searchWrap.hidden) {
      try { state.searchInput.focus(); } catch (e) { /* ignore */ }
    }
  }

  function onPanelClick(sel, e) {
    var allBox = e.target.closest && e.target.closest('input[data-all]');
    var row = e.target.closest && e.target.closest('.lc-filter-multi-item[data-value]');
    if (allBox || (e.target.closest && e.target.closest('.is-all'))) {
      e.preventDefault();
      setSelected(sel, [], true);
      return;
    }
    if (!row) return;
    e.preventDefault();
    var v = row.getAttribute('data-value');
    var cur = values(sel);
    var idx = cur.indexOf(v);
    if (idx >= 0) cur.splice(idx, 1);
    else cur.push(v);
    setSelected(sel, cur, true);
  }

  function patchSelectApi(sel) {
    Object.defineProperty(sel, 'value', {
      configurable: true,
      enumerable: true,
      get: function () {
        var vals = sel._lcSelected || [];
        return vals.length ? vals[0] : '';
      },
      set: function (v) {
        if (v == null || v === '') setSelected(sel, [], false);
        else setSelected(sel, [String(v)], false);
      }
    });
    Object.defineProperty(sel, 'selectedIndex', {
      configurable: true,
      enumerable: true,
      get: function () {
        var vals = sel._lcSelected || [];
        if (!vals.length) return 0;
        for (var i = 0; i < sel.options.length; i++) {
          if (optionVal(sel.options[i]) === vals[0]) return i;
        }
        return 0;
      },
      set: function (i) {
        i = parseInt(i, 10) || 0;
        var o = sel.options[i];
        if (i <= 0 || !o || !optionVal(o)) setSelected(sel, [], false);
        else setSelected(sel, [optionVal(o)], false);
      }
    });
  }

  function upgrade(sel) {
    sel = $(sel);
    if (!sel || sel._lcMulti) return sel;
    if (!shouldUpgrade(sel) || !sel.parentNode) return sel;

    var wrap = document.createElement('div');
    wrap.className = 'lc-filter-multi';
    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);
    sel.classList.add('lc-filter-multi-src');

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'filter-select lc-filter-multi-btn';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = '<span class="lc-filter-multi-label"></span>' +
      '<span class="lc-filter-multi-meta">' +
      '<span class="lc-filter-multi-count">0</span>' +
      '<svg class="lc-filter-multi-caret" viewBox="0 0 12 10" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M2 3l4 4 4-4"/></svg>' +
      '</span>';

    var panel = document.createElement('div');
    panel.className = 'lc-filter-multi-panel';
    panel.innerHTML = '<div class="lc-filter-multi-search" hidden><input type="search" autocomplete="off"></div>' +
      '<div class="lc-filter-multi-list" role="listbox"></div>';
    document.body.appendChild(panel);

    var state = {
      sel: sel,
      wrap: wrap,
      btn: btn,
      panel: panel,
      labelEl: btn.querySelector('.lc-filter-multi-label'),
      countEl: btn.querySelector('.lc-filter-multi-count'),
      searchWrap: panel.querySelector('.lc-filter-multi-search'),
      searchInput: panel.querySelector('input[type="search"]'),
      list: panel.querySelector('.lc-filter-multi-list')
    };
    sel._lcMulti = state;
    sel._lcSelected = [];
    wrap.appendChild(btn);

    if (state.searchInput) {
      state.searchInput.placeholder = isEn() ? 'Search…' : 'بحث…';
      state.searchInput.addEventListener('input', function () { filterPanelSearch(sel); });
      state.searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { closePanel(); state.btn.focus(); }
      });
    }

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      openPanel(sel);
    });
    panel.addEventListener('mousedown', function (e) {
      e.stopPropagation();
    });
    panel.addEventListener('click', function (e) { onPanelClick(sel, e); });

    patchSelectApi(sel);
    var initial = nativeValue && nativeValue.get ? nativeValue.get.call(sel) : '';
    if (initial) sel._lcSelected = [String(initial)];
    rebuildPanel(sel);
    refreshButton(sel);

    var obs = new MutationObserver(function () {
      var kept = (sel._lcSelected || []).filter(function (v) { return optionExists(sel, v); });
      sel._lcSelected = kept;
      rebuildPanel(sel);
      refreshButton(sel);
    });
    obs.observe(sel, { childList: true, subtree: true });
    state.obs = obs;
    return sel;
  }

  function refresh(sel) {
    sel = $(sel);
    if (!sel) return;
    if (!sel._lcMulti) {
      upgrade(sel);
      return;
    }
    var kept = (sel._lcSelected || []).filter(function (v) { return optionExists(sel, v); });
    sel._lcSelected = kept;
    rebuildPanel(sel);
    refreshButton(sel);
  }

  function scan(root) {
    root = root || document;
    if (!root.querySelectorAll) return;
    Array.prototype.forEach.call(root.querySelectorAll('select'), function (sel) {
      if (shouldUpgrade(sel)) upgrade(sel);
    });
  }

  function set(el, vals) {
    el = $(el);
    if (!el) return;
    if (!el._lcMulti) upgrade(el);
    if (!Array.isArray(vals)) vals = vals == null || vals === '' ? [] : [vals];
    setSelected(el, vals, false);
  }

  document.addEventListener('mousedown', function (e) {
    if (!openState) return;
    if (openState.panel.contains(e.target) || openState.btn.contains(e.target)) return;
    closePanel();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && openState) closePanel();
  });
  window.addEventListener('scroll', function () {
    if (openState) positionPanel(openState);
  }, true);
  window.addEventListener('resize', closePanel);

  function boot() {
    try { scan(document); } catch (err) {
      if (typeof console !== 'undefined' && console.error) console.error('LiftCoreFilter', err);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  global.LiftCoreFilter = {
    allows: allows,
    values: values,
    summary: summary,
    set: set,
    upgrade: upgrade,
    refresh: refresh,
    scan: scan,
    close: closePanel
  };
  global.lcAllows = allows;
  global.lcFilterValues = values;
  global.lcFilterSummary = summary;
})(window);
