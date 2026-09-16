/**
 * LiftCore — كميات المخزون حسب وحدة الصنف (عدد صحيح vs كسور).
 */
(function (global) {
  'use strict';

  var DECIMAL_HINTS = [
    'لتر', 'liter', 'litre', 'lit',
    'متر', 'meter', 'metre', 'm²', 'm2', 'sqm',
    'كيل', 'كجم', 'kg', 'kilogram',
    'جرام', 'gram', 'g ',
    'طن', 'ton', 'tonne',
    'قدم', 'foot', 'ft',
    'مل', 'ml', 'mm', 'سم', 'cm',
  ];
  var INTEGER_HINTS = [
    'قطعة', 'حبة', 'علبة', 'كرتون', 'رول', 'زوج', 'مجمو', 'باك',
    'pcs', 'pc', 'piece', 'unit', 'box', 'roll', 'set', 'ea', 'each',
    'عدد', 'حزم', 'حزمة', 'كيس', 'ظرف', 'طقم',
  ];

  function normUnit(unit) {
    return String(unit || '').trim().toLowerCase().replace(/\u0640/g, '');
  }

  function allowsDecimals(unit) {
    var u = normUnit(unit);
    if (!u) return false;
    var i;
    for (i = 0; i < DECIMAL_HINTS.length; i += 1) {
      if (u.indexOf(DECIMAL_HINTS[i]) !== -1) return true;
    }
    for (i = 0; i < INTEGER_HINTS.length; i += 1) {
      if (u.indexOf(INTEGER_HINTS[i]) !== -1) return false;
    }
    return false;
  }

  function fmt(qty, unit) {
    var q = Number(qty) || 0;
    if (!allowsDecimals(unit)) return String(Math.round(q));
    if (Math.abs(q - Math.round(q)) < 1e-9) return String(Math.round(q));
    var text = q.toFixed(4).replace(/\.?0+$/, '');
    return text || '0';
  }

  function inputAttrs(unit) {
    if (allowsDecimals(unit)) {
      return { step: '0.01', min: '0.01' };
    }
    return { step: '1', min: '1' };
  }

  function applyInput(input, unit) {
    if (!input) return;
    var attrs = inputAttrs(unit);
    input.step = attrs.step;
    input.min = attrs.min;
    if (input.value !== '' && !allowsDecimals(unit)) {
      input.value = String(Math.max(1, Math.round(Number(input.value) || 0)));
    }
  }

  function normalize(qty, unit) {
    var q = Number(qty) || 0;
    if (q <= 0) return 0;
    if (allowsDecimals(unit)) return Math.round(q * 10000) / 10000;
    return Math.round(q);
  }

  function labelWithUnit(qty, unit) {
    var q = fmt(qty, unit);
    var u = String(unit || '').trim();
    return u ? (q + ' ' + u) : q;
  }

  global.LcInventoryQty = {
    allowsDecimals: allowsDecimals,
    fmt: fmt,
    inputAttrs: inputAttrs,
    applyInput: applyInput,
    normalize: normalize,
    labelWithUnit: labelWithUnit,
  };
})(window);
