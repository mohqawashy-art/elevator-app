/**
 * LiftCore — ترقيم صفحات الجداول (10 صفوف لكل صفحة)
 */
(function (global) {
  'use strict';

  var DEFAULT_SIZE = 10;
  var MAX_BTNS = 5;

  function $(sel) {
    if (!sel) return null;
    return typeof sel === 'string' ? document.querySelector(sel) : sel;
  }

  function isRtl() {
    return (document.documentElement.getAttribute('dir') || 'rtl') === 'rtl';
  }

  function pageWindow(current, total) {
    if (total <= MAX_BTNS) {
      var all = [];
      for (var i = 1; i <= total; i++) all.push(i);
      return all;
    }
    var half = Math.floor(MAX_BTNS / 2);
    var start = Math.max(1, current - half);
    var end = Math.min(total, start + MAX_BTNS - 1);
    start = Math.max(1, end - MAX_BTNS + 1);
    var pages = [];
    for (var p = start; p <= end; p++) pages.push(p);
    return pages;
  }

  function fmtInfo(start, end, filtered, master) {
    var LC = global.LiftCoreDisplay;
    if (LC && LC.fmtPageRange) return LC.fmtPageRange(start, end, filtered, master);
    if (!filtered) return 'عرض 0 من ' + (master != null ? master : 0);
    return 'عرض ' + start + '–' + end + ' من ' + (master != null ? master : filtered);
  }

  function numVal(v) {
    if (v == null || v === '') return 0;
    if (typeof v === 'number') return isFinite(v) ? v : 0;
    var s = String(v).replace(/,/g, '').replace(/[^\d.-]/g, '');
    var n = parseFloat(s);
    return isFinite(n) ? n : 0;
  }

  function fmtMoneySum(n) {
    n = numVal(n);
    try {
      return n.toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 0 });
    } catch (e) {
      return String(Math.round(n * 100) / 100);
    }
  }

  function isEnUi() {
    return (document.documentElement.getAttribute('lang') || '').toLowerCase().indexOf('en') === 0
      || (document.documentElement.getAttribute('dir') || '') === 'ltr';
  }

  /** حساب مجاميع الفلترة من الصفوف المعروضة (كل النتائج المصفاة وليس الصفحة فقط) */
  function buildFilterSums(rows, sumFields) {
    if (!sumFields || !sumFields.length || !rows || !rows.length) return '';
    var en = isEnUi();
    var parts = [];
    sumFields.forEach(function (spec) {
      if (!spec) return;
      var total = 0;
      var getter = typeof spec.get === 'function'
        ? spec.get
        : function (row) { return row && (spec.key != null ? row[spec.key] : null); };
      for (var i = 0; i < rows.length; i++) total += numVal(getter(rows[i]));
      var label = en ? (spec.labelEn || spec.label || spec.key) : (spec.label || spec.labelEn || spec.key);
      parts.push(label + ': ' + fmtMoneySum(total));
    });
    return parts.join(en ? ' · ' : ' · ');
  }

  function writeInfo(infoEl, start, end, filtered, master, sumText) {
    if (!infoEl) return;
    var base = fmtInfo(start, end, filtered, master);
    infoEl.textContent = base;
    var prev = infoEl.querySelector('.lc-filter-sums');
    if (prev) prev.remove();
    if (!sumText) return;
    var span = document.createElement('span');
    span.className = 'lc-filter-sums';
    span.setAttribute('data-i18n-skip', '');
    span.textContent = ' · ' + sumText;
    infoEl.appendChild(span);
  }

  /** مفتاح حفظ الصفحة الحالية — لكل جدول في كل صفحة */
  function storageKey(options) {
    if (options.persist === false) return null;
    if (options.persistKey) return 'lc:page:' + options.persistKey;
    var sel = typeof options.container === 'string' ? options.container : null;
    if (!sel) return null;
    return 'lc:page:' + global.location.pathname + '|' + sel;
  }

  function readStored(key) {
    if (!key) return 1;
    try {
      var v = parseInt(global.sessionStorage.getItem(key), 10);
      return v > 0 ? v : 1;
    } catch (e) {
      return 1;
    }
  }

  function writeStored(key, value) {
    if (!key) return;
    try {
      global.sessionStorage.setItem(key, String(value));
    } catch (e) { /* تجاهل */ }
  }

  function create(options) {
    options = options || {};
    var pageSize = options.pageSize || DEFAULT_SIZE;
    var container = $(options.container);
    var infoEl = $(options.infoEl);
    var storeKey = storageKey(options);
    var page = readStored(storeKey);
    var filteredTotal = 0;
    var getMasterTotal = options.getMasterTotal || null;
    var onPageChange = options.onPageChange || null;
    var sumFields = options.sumFields || null;
    var lastFilteredRows = [];

    function totalPages() {
      return Math.max(1, Math.ceil(filteredTotal / pageSize));
    }

    function clampPage() {
      var tp = totalPages();
      if (page > tp) page = tp;
      if (page < 1) page = 1;
    }

    function setPage(p) {
      p = Number(p);
      if (!p || p < 1) p = 1;
      page = p;
      writeStored(storeKey, page);
    }

    function resetPage() {
      // التحديث التلقائي للبيانات لا يجب أن يُرجع المستخدم للصفحة الأولى
      if (global.__lcPreservePage) return;
      page = 1;
      writeStored(storeKey, page);
    }

    function setTotal(n) {
      filteredTotal = Math.max(0, Number(n) || 0);
      clampPage();
    }

    function slice(data) {
      if (!data || !data.length) return [];
      clampPage();
      var start = (page - 1) * pageSize;
      return data.slice(start, start + pageSize);
    }

    function paginate(data, masterTotal) {
      var list = Array.isArray(data) ? data : [];
      lastFilteredRows = list;
      var len = list.length;
      setTotal(len);
      var master = masterTotal != null ? masterTotal : filteredTotal;
      if (!filteredTotal) {
        return {
          rows: [],
          start: 0,
          end: 0,
          filteredTotal: 0,
          masterTotal: master,
          page: 1,
          pages: 1,
          sumText: '',
        };
      }
      var rows = slice(list);
      var startIdx = (page - 1) * pageSize + 1;
      var endIdx = Math.min(page * pageSize, filteredTotal);
      return {
        rows: rows,
        start: startIdx,
        end: endIdx,
        filteredTotal: filteredTotal,
        masterTotal: master,
        page: page,
        pages: totalPages(),
        sumText: buildFilterSums(list, sumFields),
      };
    }

    function goTo(p) {
      p = Number(p);
      if (isNaN(p) || p < 1 || p > totalPages() || p === page) return;
      setPage(p);
      if (onPageChange) onPageChange(page);
    }

    function render(meta) {
      meta = meta || {};
      var tp = meta.pages || totalPages();
      var cur = meta.page || page;
      var master = meta.masterTotal != null ? meta.masterTotal : filteredTotal;
      var sumText = meta.sumText;
      if (sumText == null) sumText = buildFilterSums(lastFilteredRows, sumFields);

      writeInfo(
        infoEl,
        meta.start || 0,
        meta.end || 0,
        meta.filteredTotal != null ? meta.filteredTotal : filteredTotal,
        master,
        sumText
      );

      if (!container) return;

      if ((meta.filteredTotal || filteredTotal) <= pageSize) {
        container.innerHTML = '';
        return;
      }

      var rtl = isRtl();
      var prevChar = rtl ? '\u203A' : '\u2039';
      var nextChar = rtl ? '\u2039' : '\u203A';
      var prevLabel = rtl ? 'الصفحة السابقة' : 'Previous page';
      var nextLabel = rtl ? 'الصفحة التالية' : 'Next page';

      var html = '';
      html += '<button type="button" class="page-btn lc-page-nav"' +
        (cur <= 1 ? ' disabled' : '') +
        ' data-page="' + (cur - 1) + '" aria-label="' + prevLabel + '">' + prevChar + '</button>';
      html += '<span class="lc-page-nums">';
      pageWindow(cur, tp).forEach(function (n) {
        html += '<button type="button" class="page-btn' + (n === cur ? ' active' : '') +
          '" data-page="' + n + '"' + (n === cur ? ' aria-current="page"' : '') + '>' + n + '</button>';
      });
      html += '</span>';
      html += '<button type="button" class="page-btn lc-page-nav"' +
        (cur >= tp ? ' disabled' : '') +
        ' data-page="' + (cur + 1) + '" aria-label="' + nextLabel + '">' + nextChar + '</button>';

      container.classList.add('lc-pagination');
      container.innerHTML = html;

      container.querySelectorAll('.page-btn[data-page]').forEach(function (btn) {
        btn.addEventListener('click', function (ev) {
          ev.preventDefault();
          if (btn.disabled) return;
          goTo(btn.getAttribute('data-page'));
        });
      });
    }

    return {
      pageSize: pageSize,
      resetPage: resetPage,
      setPage: setPage,
      setTotal: setTotal,
      slice: slice,
      paginate: paginate,
      render: render,
      getPage: function () { return page; },
    };
  }

  /** ترقيم صفوف DOM (التقارير) */
  function createDom(options) {
    options = options || {};
    var tbody = $(options.tbody);
    var container = $(options.container);
    var infoEl = $(options.infoEl);
    var pageSize = options.pageSize || DEFAULT_SIZE;
    var page = 1;

    function visibleRows() {
      if (!tbody) return [];
      return Array.prototype.filter.call(tbody.querySelectorAll('tr'), function (tr) {
        if (tr.querySelector('td[colspan]')) return false;
        return tr.dataset.lcSearchHidden !== '1';
      });
    }

    function renderButtons(total, tp) {
      if (!container) return;
      var pager = create({
        pageSize: pageSize,
        container: container,
        persist: false,
        onPageChange: function (p) {
          page = p;
          apply(false);
        },
      });
      pager.paginate({ length: total }, total);
      pager.render({
        start: total ? (page - 1) * pageSize + 1 : 0,
        end: total ? Math.min(page * pageSize, total) : 0,
        filteredTotal: total,
        masterTotal: total,
        page: page,
        pages: tp,
      });
    }

    function apply(reset) {
      if (reset) page = 1;
      var rows = visibleRows();
      var total = rows.length;
      var tp = Math.max(1, Math.ceil(total / pageSize) || 1);
      if (page > tp) page = tp;
      if (page < 1) page = 1;

      rows.forEach(function (tr, i) {
        var pg = Math.floor(i / pageSize) + 1;
        tr.style.display = pg === page ? '' : 'none';
      });

      if (infoEl) {
        if (!total) {
          infoEl.textContent = fmtInfo(0, 0, 0, 0);
        } else {
          var start = (page - 1) * pageSize + 1;
          var end = Math.min(page * pageSize, total);
          infoEl.textContent = fmtInfo(start, end, total, total);
        }
      }

      renderButtons(total, tp);
      return total;
    }

    return {
      resetPage: function () { page = 1; },
      apply: apply,
    };
  }

  global.LiftCorePagination = {
    create: create,
    createDom: createDom,
    PAGE_SIZE: DEFAULT_SIZE,
    /** تهيئة متأخرة — تضمن عمل الترقيم حتى مع تأخر تحميل السكربت */
    bind: function (options) {
      var inst = null;
      function getInst() {
        if (!inst) inst = create(options);
        return inst;
      }
      return {
        pageSize: options.pageSize || DEFAULT_SIZE,
        resetPage: function () {
          var i = getInst();
          if (i) i.resetPage();
        },
        setPage: function (p) {
          var i = getInst();
          if (i) i.setPage(p);
        },
        getPage: function () {
          var i = getInst();
          return i ? i.getPage() : 1;
        },
        /** رقم الصفحة التي يقع فيها صف بترتيب معيّن (0-based) */
        pageOf: function (index) {
          var size = options.pageSize || DEFAULT_SIZE;
          index = Number(index);
          if (isNaN(index) || index < 0) return 1;
          return Math.floor(index / size) + 1;
        },
        apply: function (data, masterTotal) {
          var i = getInst();
          var len = Array.isArray(data) ? data.length : 0;
          var master = masterTotal != null ? masterTotal : len;
          if (!i) {
            return {
              rows: data || [],
              start: len ? 1 : 0,
              end: len,
              filteredTotal: len,
              masterTotal: master,
              page: 1,
              pages: 1,
            };
          }
          var pg = i.paginate(data, master);
          i.render(pg);
          return pg;
        },
      };
    },
  };
})(window);
