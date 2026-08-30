/**
 * LiftCore — بحث موحّد للجداول والقوائم.
 * يطوي العربية، يطابق الأكواد بدون أصفار/شرطات، والهواتف، وكلمات متعددة (AND).
 */
(function (global) {
  'use strict';

  var EASTERN = /[\u0660-\u0669\u06F0-\u06F9]/g;
  var TASHKEEL = /[\u064B-\u065F\u0670\u0640]/g;
  var ALEF = /[\u0622\u0623\u0625\u0671\u0672\u0673]/g;
  var NON_WORD = /[^\u0621-\u064Aa-z0-9]+/gi;

  function easternDigit(ch) {
    var c = ch.charCodeAt(0);
    if (c >= 0x0660 && c <= 0x0669) return String(c - 0x0660);
    if (c >= 0x06F0 && c <= 0x06F9) return String(c - 0x06F0);
    return ch;
  }

  function fold(value) {
    return String(value == null ? '' : value)
      .replace(EASTERN, easternDigit)
      .replace(TASHKEEL, '')
      .replace(ALEF, '\u0627')
      .replace(/\u0629/g, '\u0647')
      .replace(/\u0649/g, '\u064A')
      .replace(/[\u0624]/g, '\u0648')
      .replace(/[\u0626\u0621]/g, '')
      .replace(/[\u0640]/g, '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim();
  }

  function compact(value) {
    NON_WORD.lastIndex = 0;
    return fold(value).replace(NON_WORD, '');
  }

  function phoneKeys(value) {
    var digits = fold(value).replace(/\D+/g, '');
    if (!digits) return [];
    var keys = [digits];
    if (digits.indexOf('00') === 0) digits = digits.slice(2);
    if (digits.indexOf('966') === 0 && digits.length > 9) {
      keys.push(digits.slice(3));
      digits = digits.slice(3);
    }
    if (digits.charAt(0) === '0' && digits.length >= 9) keys.push(digits.slice(1));
    if (digits.length >= 9) keys.push(digits.slice(-9));
    return unique(keys.filter(function (k) { return k.length >= 4; }));
  }

  function codeKeys(value) {
    var raw = compact(value);
    if (!raw) return [];
    var out = [raw];
    var re = /([a-z]{1,5})?0*(\d+)/g;
    var m;
    while ((m = re.exec(raw))) {
      var num = m[2].replace(/^0+/, '') || '0';
      if (m[1]) out.push(m[1] + num);
      if (num.length >= 2) out.push(num);
    }
    return unique(out);
  }

  function unique(arr) {
    var seen = Object.create(null);
    var out = [];
    for (var i = 0; i < arr.length; i++) {
      if (!arr[i] || seen[arr[i]]) continue;
      seen[arr[i]] = 1;
      out.push(arr[i]);
    }
    return out;
  }

  function haystack(fields) {
    var parts = [];
    var i;
    for (i = 0; i < fields.length; i++) {
      if (fields[i] == null || fields[i] === '') continue;
      if (Array.isArray(fields[i])) {
        for (var j = 0; j < fields[i].length; j++) parts.push(fields[i][j]);
      } else {
        parts.push(fields[i]);
      }
    }
    var text = parts.join(' ');
    var folded = fold(text);
    return {
      folded: folded,
      compact: compact(text),
      phones: phoneKeys(text),
      codes: codeKeys(text),
      words: folded ? folded.split(' ') : [],
    };
  }

  function tokenHits(token, hs) {
    var ft = fold(token);
    if (!ft) return true;
    if (hs.folded.indexOf(ft) !== -1) return true;
    var w;
    for (w = 0; w < hs.words.length; w++) {
      if (hs.words[w].indexOf(ft) === 0) return true;
    }
    var ct = compact(token);
    if (ct.length >= 2 && hs.compact.indexOf(ct) !== -1) return true;
    var pk = phoneKeys(token);
    var i, k;
    if (pk.length) {
      for (i = 0; i < pk.length; i++) {
        for (k = 0; k < hs.phones.length; k++) {
          if (hs.phones[k].indexOf(pk[i]) !== -1 || pk[i].indexOf(hs.phones[k]) !== -1) return true;
        }
      }
    }
    var ck = codeKeys(token);
    if (ck.length && ct.length >= 2) {
      for (i = 0; i < ck.length; i++) {
        if (hs.codes.indexOf(ck[i]) !== -1) return true;
      }
    }
    return false;
  }

  function match(query, fields) {
    var q = String(query == null ? '' : query).trim();
    if (!q) return true;
    var hs = haystack(Array.isArray(fields) ? fields : [fields]);
    var tokens = fold(q).split(' ').filter(Boolean);
    if (!tokens.length) return true;
    for (var i = 0; i < tokens.length; i++) {
      if (!tokenHits(tokens[i], hs)) return false;
    }
    return true;
  }

  function queryOf(elOrId) {
    var el = typeof elOrId === 'string' ? document.getElementById(elOrId) : elOrId;
    return el ? String(el.value || '').trim() : '';
  }

  function filterDomRows(rowSelector, searchId, infoId) {
    var q = queryOf(searchId || 'f-search');
    var rows = document.querySelectorAll(rowSelector);
    var count = 0;
    for (var i = 0; i < rows.length; i++) {
      var show = match(q, rows[i].getAttribute('data-search') || rows[i].textContent || '');
      rows[i].style.display = show ? '' : 'none';
      if (show) count += 1;
    }
    var info = infoId ? document.getElementById(infoId) : null;
    if (info) info.textContent = 'عرض ' + count + ' سجل';
    return count;
  }

  global.LcSearch = {
    fold: fold,
    compact: compact,
    match: match,
    queryOf: queryOf,
    filterDomRows: filterDomRows,
  };
})(window);
