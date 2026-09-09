/**
 * LiftCore — ترتيب جداول (كل الأعمدة) تصاعدي وتنازلي
 */
(function (global) {
  'use strict';

  function parseCode(code) {
    if (code == null || code === '') return 0;
    var parts = String(code).match(/\d+/g);
    if (!parts || !parts.length) return String(code).toLowerCase();
    // آخر مجموعة أرقام = الرقم التسلسلي (VI-00002 → 2، VI-00011 → 11)
    return parseInt(parts[parts.length - 1], 10) || 0;
  }

  function naturalCodeCompare(a, b) {
    var sa = String(a == null ? '' : a);
    var sb = String(b == null ? '' : b);
    return sa.localeCompare(sb, undefined, { numeric: true, sensitivity: 'base' });
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

  function defaultDirForCol() {
    return 'asc';
  }

  function create(options) {
    options = options || {};
    var getters = options.getters || {};
    var state = {
      col: options.defaultCol || 'code',
      dir: options.defaultDir || 'asc',
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
        if (isCodeCol(col, options)) {
          return naturalCodeCompare(getValue(a, col), getValue(b, col)) * mul;
        }
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

  function isPinnedRow(tr) {
    if (!tr || tr.classList.contains('total-row') || tr.classList.contains('lc-sort-skip')) return true;
    var cells = tr.querySelectorAll('td');
    if (!cells.length) return true;
    if (cells.length === 1 && cells[0].hasAttribute('colspan')) return true;
    return false;
  }

  function bindDomTables(root) {
    (root || document).querySelectorAll('table').forEach(function (table) {
      if (table._lcDomSortBound) return;
      var ths = table.querySelectorAll('thead th.th-sort[data-sort-col]');
      if (!ths.length) return;
      var tbody = table.querySelector('tbody');
      if (!tbody) return;
      table._lcDomSortBound = true;

      var state = { col: null, dir: 'asc' };

      function colIndex(th) {
        return Array.prototype.indexOf.call(th.parentNode.children, th);
      }

      function parseCell(td, type) {
        if (!td) return '';
        var raw = td.getAttribute('data-sort-value');
        if (raw == null) raw = td.textContent.trim();
        if (type === 'num' || (!type && td.classList.contains('td-num'))) {
          return parseNumber(raw);
        }
        if (type === 'date') return parseDate(raw);
        if (type === 'code' || td.classList.contains('td-code')) {
          return parseCode(raw);
        }
        var codeEl = td.querySelector('.td-code');
        if (codeEl) return parseCode(codeEl.textContent);
        return String(raw).toLowerCase();
      }

      function updateDomIndicators(col) {
        table.querySelectorAll('th.th-sort[data-sort-col]').forEach(function (h) {
          var ind = h.querySelector('.sort-ind');
          if (!ind) return;
          if (h.getAttribute('data-sort-col') === col) {
            ind.textContent = state.dir === 'asc' ? '▲' : '▼';
          } else {
            ind.textContent = '';
          }
        });
      }

      function sortBy(th) {
        var idx = colIndex(th);
        if (idx < 0) return;
        var col = th.getAttribute('data-sort-col');
        var type = th.getAttribute('data-sort-type') || '';
        if (state.col === col) {
          state.dir = state.dir === 'asc' ? 'desc' : 'asc';
        } else {
          state.col = col;
          state.dir = 'asc';
        }
        var mul = state.dir === 'asc' ? 1 : -1;
        var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        var pinned = rows.filter(isPinnedRow);
        var dataRows = rows.filter(function (r) { return !isPinnedRow(r); });

        dataRows.sort(function (a, b) {
          var va = parseCell(a.children[idx], type);
          var vb = parseCell(b.children[idx], type);
          if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * mul;
          if (isCodeCol(col, {}) || type === 'code') {
            return naturalCodeCompare(va, vb) * mul;
          }
          return String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: 'base' }) * mul;
        });

        dataRows.forEach(function (r) { tbody.appendChild(r); });
        pinned.forEach(function (r) { tbody.appendChild(r); });
        updateDomIndicators(col);
      }

      ths.forEach(function (th) {
        if (th._lcDomSortBound) return;
        th._lcDomSortBound = true;
        th.addEventListener('click', function (e) {
          e.stopPropagation();
          sortBy(th);
        });
      });
    });
  }

  global.LiftCoreTableSort = {
    create: create,
    lazy: lazy,
    bindDomTables: bindDomTables,
    parseCode: parseCode,
    parseDate: parseDate,
  };
})(typeof window !== 'undefined' ? window : this);
