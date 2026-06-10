/**
 * LiftCore — ترتيب جداول (كود / تاريخ) تصاعدي وتنازلي
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

  function isCodeCol(col, opts) {
    return col === 'code' || col === (opts.codeCol || 'code');
  }

  function isDateCol(col, opts) {
    return col === 'date' || col === opts.dateField || col === (opts.dateCol || 'date');
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
      if (isDateCol(col, options) && options.dateField) return row[options.dateField];
      if (isCodeCol(col, options)) return row[options.codeField || 'code'];
      return row[col];
    }

    function normalize(col, val) {
      if (isCodeCol(col, options)) return parseCode(val);
      if (isDateCol(col, options)) return parseDate(val);
      if (typeof val === 'number') return val;
      if (val == null) return '';
      return String(val);
    }

    function toggle(col) {
      if (state.col === col) {
        state.dir = state.dir === 'asc' ? 'desc' : 'asc';
      } else {
        state.col = col;
        state.dir = (isDateCol(col, options) || isCodeCol(col, options)) ? 'desc' : 'asc';
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
        th.addEventListener('click', function () {
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

  global.LiftCoreTableSort = {
    create: create,
    parseCode: parseCode,
    parseDate: parseDate,
  };
})(typeof window !== 'undefined' ? window : this);
