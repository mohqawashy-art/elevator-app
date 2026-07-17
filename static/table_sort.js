/**
 * LiftCore — ترتيب جداول (كل الأعمدة) تصاعدي وتنازلي
 */
(function (global) {
  'use strict';

  function parseCode(code) {
    if (code == null || code === '') return 0;
    var parts = String(code).match(/\d+/g);
    if (!parts || !parts.length) return String(code).toLowerCase();
    return parseInt(parts[parts.length - 1], 10) || 0;
  }

  function parseDate(d) {
    if (!d) return 0;
    var s = String(d).trim();
    if (!s) return 0;
    var t = Date.parse(s.length <= 10 ? s + 'T00:00:00' : s);
    return isNaN(t) ? 0 : t;
  }

  function parseNumber(val) {
    if (typeof val === 'number') return val;
    if (val == null || val === '') return 0;
    var n = parseFloat(String(val).replace(/,/g, ''));
    return isNaN(n) ? 0 : n;
  }

  function isCodeCol(col, opts) {
    if (opts.codeCols && opts.codeCols.indexOf(col) >= 0) return true;
    return col === 'code' || col === (opts.codeCol || 'code');
  }

  function isDateCol(col, opts) {
    if (opts.dateCols && opts.dateCols.indexOf(col) >= 0) return true;
    if (col === 'date' || col === opts.dateField) return true;
    return /(_date|_at|Date)$/.test(col);
  }

  function isNumberCol(col, opts) {
    return opts.numberCols && opts.numberCols.indexOf(col) >= 0;
  }

  function defaultDirForCol(col, opts) {
    if (isDateCol(col, opts) || isCodeCol(col, opts) || isNumberCol(col, opts)) return 'desc';
    return 'asc';
  }

  function create(options) {
    options = options || {};
    var getters = options.getters || {};
    var state = {
      col: options.defaultCol || 'code',
      dir: options.defaultDir || 'desc',
    };

    function getValue(row, col) {
      if (getters[col]) return getters[col](row);
      if (isDateCol(col, options) && options.dateField && (col === 'date' || col === options.dateField)) {
        return row[options.dateField];
      }
      if (row[col] !== undefined) return row[col];
      return '';
    }

    function normalize(col, val) {
      if (isCodeCol(col, options)) return parseCode(val);
      if (isDateCol(col, options)) return parseDate(val);
      if (isNumberCol(col, options) || typeof val === 'number') return parseNumber(val);
      if (val == null) return '';
      return String(val);
    }

    function toggle(col) {
      if (state.col === col) {
        state.dir = state.dir === 'asc' ? 'desc' : 'asc';
      } else {
        state.col = col;
        state.dir = defaultDirForCol(col, options);
      }
      if (options.onChange) options.onChange();
    }

    function apply(list) {
      if (!list || !list.length) return list || [];
      var mul = state.dir === 'asc' ? 1 : -1;
      var col = state.col;
      return list.slice().sort(function (a, b) {
        var va = normalize(col, getValue(a, col));
        var vb = normalize(col, getValue(b, col));
        if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * mul;
        return String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: 'base' }) * mul;
      });
    }

    function updateIndicators(root) {
      (root || document).querySelectorAll('th.th-sort[data-sort-col]').forEach(function (th) {
        var col = th.getAttribute('data-sort-col');
        var ind = th.querySelector('.sort-ind');
        if (!ind) return;
        if (state.col === col) ind.textContent = state.dir === 'asc' ? '▲' : '▼';
        else ind.textContent = '';
      });
    }

    function bindHeaders(root) {
      (root || document).querySelectorAll('th.th-sort[data-sort-col]').forEach(function (th) {
        if (th._lcSortBound) return;
        th._lcSortBound = true;
        th.addEventListener('click', function (e) {
          e.stopPropagation();
          toggle(th.getAttribute('data-sort-col'));
        });
      });
    }

    return {
      toggle: toggle,
      apply: apply,
      bindHeaders: bindHeaders,
      updateIndicators: updateIndicators,
      getState: function () { return { col: state.col, dir: state.dir }; },
    };
  }

  function lazy(options) {
    var inst = null;
    function ensure() {
      if (!inst) {
        inst = create(options);
        inst.bindHeaders();
      }
      return inst;
    }
    function boot() { ensure(); }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }
    return {
      apply: function (list) {
        return ensure().apply(list);
      },
      updateIndicators: function () {
        if (inst) inst.updateIndicators();
      },
      bindHeaders: function () { ensure(); },
    };
  }

  global.LiftCoreTableSort = {
    create: create,
    lazy: lazy,
    parseCode: parseCode,
    parseDate: parseDate,
  };
})(typeof window !== 'undefined' ? window : this);
