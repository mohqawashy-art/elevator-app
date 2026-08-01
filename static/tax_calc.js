/**
 * LiftCore — حساب الضريبة (قبل / شامل) مع تقسيم تلقائي
 */
(function (global) {
  'use strict';

  function $(id) {
    return id ? document.getElementById(id) : null;
  }

  function round2(n) {
    return Math.round((parseFloat(n) || 0) * 100) / 100;
  }

  function fromBeforeTax(before, pct) {
    pct = parseFloat(pct) || 15;
    before = parseFloat(before) || 0;
    var tax = round2(before * pct / 100);
    return { before: round2(before), tax: tax, total: round2(before + tax), pct: pct };
  }

  function fromInclusive(total, pct) {
    pct = parseFloat(pct) || 15;
    total = round2(total);
    var before = round2(total / (1 + pct / 100));
    var tax = round2(total - before);
    /* الإجمالي الشامل هو مصدر الحقيقة — لا تُعد بناؤه من قبل + ضريبة */
    return { before: before, tax: tax, total: total, pct: pct };
  }

  function formatMoney(n) {
    return round2(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' \u20C1';
  }

  function setDisplays(cfg, result) {
    if (cfg.taxLabelId) {
      var label = $(cfg.taxLabelId);
      if (label) label.textContent = 'الضريبة (' + result.pct + '%)';
    }
    if (cfg.beforeDisplayId) {
      var beforeEl = $(cfg.beforeDisplayId);
      if (beforeEl) beforeEl.textContent = formatMoney(result.before);
    }
    if (cfg.taxDisplayId) {
      var taxEl = $(cfg.taxDisplayId);
      if (taxEl) taxEl.textContent = formatMoney(result.tax);
    }
    if (cfg.totalDisplayId) {
      var totalEl = $(cfg.totalDisplayId);
      if (totalEl) totalEl.textContent = formatMoney(result.total);
    }
    if (cfg.beforeValueId) {
      var hidden = $(cfg.beforeValueId);
      if (hidden) hidden.value = result.before > 0 ? result.before.toFixed(2) : '';
    }
    if (cfg.totalValueId) {
      var totalHidden = $(cfg.totalValueId);
      if (totalHidden) totalHidden.value = result.total > 0 ? result.total.toFixed(2) : '';
    }
  }

  function updateBlock(cfg) {
    if (!cfg) return null;
    var inputEl = $(cfg.inputId);
    if (!inputEl) return null;
    var pctEl = cfg.pctId ? $(cfg.pctId) : null;
    var raw = parseFloat(inputEl.value);
    var pct = pctEl ? parseFloat(pctEl.value) : (cfg.defaultPct || 15);
    if (!raw || raw < 0) {
      var empty = { before: 0, tax: 0, total: 0, pct: pct || 15 };
      setDisplays(cfg, empty);
      return null;
    }
    var result = cfg.getMode() === 'inclusive'
      ? fromInclusive(raw, pct)
      : fromBeforeTax(raw, pct);
    setDisplays(cfg, result);
    return result;
  }

  function bind(cfg) {
    cfg._mode = cfg.defaultMode || 'before';
    cfg.getMode = function () { return cfg._mode || 'before'; };
    cfg.setMode = function (mode) {
      var prevMode = cfg._mode || 'before';
      if (mode !== prevMode) {
        var current = updateBlock(cfg);
        var inputEl = $(cfg.inputId);
        if (current && inputEl && parseFloat(inputEl.value) > 0) {
          inputEl.value = mode === 'inclusive'
            ? current.total.toFixed(2)
            : current.before.toFixed(2);
        }
      }
      cfg._mode = mode;
      var beforeBtn = cfg.beforeBtnId ? $(cfg.beforeBtnId) : null;
      var inclusiveBtn = cfg.inclusiveBtnId ? $(cfg.inclusiveBtnId) : null;
      var labelEl = cfg.inputLabelId ? $(cfg.inputLabelId) : null;
      if (beforeBtn) beforeBtn.classList.toggle('active', mode === 'before');
      if (inclusiveBtn) inclusiveBtn.classList.toggle('active', mode === 'inclusive');
      if (labelEl) {
        var labelText = mode === 'inclusive'
          ? (cfg.labelInclusive || 'الإجمالي شامل الضريبة (\u20C1)')
          : (cfg.labelBefore || 'المبلغ قبل الضريبة (\u20C1)');
        if (labelText.indexOf('<') >= 0) {
          labelEl.innerHTML = labelText;
        } else {
          labelEl.textContent = labelText;
        }
      }
      updateBlock(cfg);
    };
    cfg.update = function () { return updateBlock(cfg); };
    cfg.reset = function () {
      var inputEl = $(cfg.inputId);
      if (inputEl) inputEl.value = '';
      if (cfg.beforeValueId) {
        var hidden = $(cfg.beforeValueId);
        if (hidden) hidden.value = '';
      }
      cfg.setMode(cfg.defaultMode || 'before');
    };
    cfg.loadBeforeTax = function (beforeAmount, pct) {
      if (pct != null && cfg.pctId) {
        var pctEl = $(cfg.pctId);
        if (pctEl) pctEl.value = pct;
      }
      cfg.setMode('before');
      var inputEl = $(cfg.inputId);
      if (inputEl) inputEl.value = beforeAmount || '';
      updateBlock(cfg);
    };
    cfg.loadInclusive = function (totalAmount, pct) {
      if (pct != null && cfg.pctId) {
        var pctEl = $(cfg.pctId);
        if (pctEl) pctEl.value = pct;
      }
      cfg.setMode('inclusive');
      var inputEl = $(cfg.inputId);
      if (inputEl) {
        var t = round2(totalAmount);
        inputEl.value = t > 0 ? t.toFixed(2) : '';
      }
      updateBlock(cfg);
    };
    cfg.getBeforeTax = function () {
      var result = updateBlock(cfg);
      return result ? result.before : 0;
    };
    cfg.getTotal = function () {
      var result = updateBlock(cfg);
      return result ? result.total : 0;
    };

    if (cfg.beforeBtnId) {
      var beforeBtn = $(cfg.beforeBtnId);
      if (beforeBtn) beforeBtn.addEventListener('click', function () { cfg.setMode('before'); });
    }
    if (cfg.inclusiveBtnId) {
      var inclusiveBtn = $(cfg.inclusiveBtnId);
      if (inclusiveBtn) inclusiveBtn.addEventListener('click', function () { cfg.setMode('inclusive'); });
    }
    [cfg.inputId, cfg.pctId].forEach(function (id) {
      if (!id) return;
      var el = $(id);
      if (el) el.addEventListener('input', function () { updateBlock(cfg); });
    });

    cfg.setMode(cfg.defaultMode || 'before');
    return cfg;
  }

  function bindFromElement(el) {
    if (!el || el._lcTaxCalc) return el._lcTaxCalc;
    var prefix = el.dataset.lcTaxPrefix;
    if (!prefix) return null;
    var pctEl = el.querySelector('.lc-tax-pct');
    var cfg = bind({
      inputId: prefix + '-input',
      pctId: pctEl ? pctEl.id : null,
      beforeValueId: el.dataset.beforeField || null,
      totalValueId: el.dataset.totalField || null,
      beforeDisplayId: prefix + '-before',
      taxDisplayId: prefix + '-tax',
      totalDisplayId: prefix + '-total',
      taxLabelId: prefix + '-tax-label',
      beforeBtnId: prefix + '-mode-before',
      inclusiveBtnId: prefix + '-mode-inclusive',
      inputLabelId: prefix + '-input-label',
      labelBefore: el.dataset.labelBefore || undefined,
      labelInclusive: el.dataset.labelInclusive || undefined,
      defaultPct: parseFloat(el.dataset.defaultPct) || 15,
    });
    el._lcTaxCalc = cfg;
    return cfg;
  }

  function initAll(root) {
    (root || document).querySelectorAll('.lc-tax-block').forEach(bindFromElement);
  }

  function resetElement(el) {
    var calc = el && (el._lcTaxCalc || bindFromElement(el));
    if (calc) calc.reset();
  }

  function loadElement(el, beforeAmount, pct) {
    var calc = el && (el._lcTaxCalc || bindFromElement(el));
    if (calc) calc.loadBeforeTax(beforeAmount, pct);
  }

  function loadInclusiveElement(el, totalAmount, pct) {
    var calc = el && (el._lcTaxCalc || bindFromElement(el));
    if (calc) calc.loadInclusive(totalAmount, pct);
  }

  function summaryHTML(result, labelBefore) {
    labelBefore = labelBefore || 'المبلغ قبل الضريبة';
    return (
      '<div class="lc-tax-summary">' +
      '<div class="lc-tax-summary-row"><span>' + labelBefore + '</span><span>' + formatMoney(result.before) + '</span></div>' +
      '<div class="lc-tax-summary-row"><span>الضريبة (' + result.pct + '%)</span><span>' + formatMoney(result.tax) + '</span></div>' +
      '<div class="lc-tax-summary-row lc-tax-summary-total"><span>الإجمالي</span><span>' + formatMoney(result.total) + '</span></div>' +
      '</div>'
    );
  }

  global.LiftCoreTaxCalc = {
    round2: round2,
    fromBeforeTax: fromBeforeTax,
    fromInclusive: fromInclusive,
    formatMoney: formatMoney,
    bind: bind,
    update: updateBlock,
    initAll: initAll,
    bindFromElement: bindFromElement,
    resetElement: resetElement,
    loadElement: loadElement,
    loadInclusiveElement: loadInclusiveElement,
    summaryHTML: summaryHTML,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initAll(); });
  } else {
    initAll();
  }
})(window);
