/**
 * LiftCore — تحويل الأسماء العربية إلى لاتيني أثناء الكتابة
 */
(function (global) {
  'use strict';

  var CHAR_MAP = {
    '\u0627': 'a', '\u0623': 'a', '\u0625': 'i', '\u0622': 'aa', '\u0671': 'a',
    '\u0628': 'b', '\u062A': 't', '\u062B': 'th', '\u062C': 'j', '\u062D': 'h', '\u062E': 'kh',
    '\u062F': 'd', '\u0630': 'th', '\u0631': 'r', '\u0632': 'z', '\u0633': 's', '\u0634': 'sh',
    '\u0635': 's', '\u0636': 'd', '\u0637': 't', '\u0638': 'z', '\u0639': 'a', '\u063A': 'gh',
    '\u0641': 'f', '\u0642': 'q', '\u0643': 'k', '\u0644': 'l', '\u0645': 'm', '\u0646': 'n',
    '\u0647': 'h', '\u0648': 'w', '\u0624': 'u', '\u064A': 'y', '\u0649': 'a', '\u0626': 'e',
    '\u0629': 'h', '\u0621': '', '\u0640': '',
    '\u064E': '', '\u064F': '', '\u0650': '', '\u0651': '', '\u0652': '',
    '\u064B': '', '\u064C': '', '\u064D': '',
  };

  function isAsciiWord(word) {
    return /^[\w.\-]+$/.test(word);
  }

  function transliterateWord(word) {
    word = String(word || '').trim();
    if (!word) return '';
    if (isAsciiWord(word)) return word;

    var prefix = '';
    if (word.indexOf('\u0627\u0644') === 0 && word.length > 2) {
      prefix = 'Al-';
      word = word.slice(2);
    } else if (word === '\u0627\u0644') {
      return 'Al';
    }

    var out = '';
    for (var i = 0; i < word.length; i++) {
      var ch = word.charAt(i);
      if (CHAR_MAP[ch] !== undefined) out += CHAR_MAP[ch];
      else if (ch === ' ' || ch === '-' || ch === '_' || ch === '.') out += ch;
      else if (/^[\w]$/.test(ch)) out += ch;
    }
    out = out.replace(/^-+/, '');
    if (!out) return prefix.replace(/-$/, '');
    return prefix + out.charAt(0).toUpperCase() + out.slice(1);
  }

  function arabicToLatin(text) {
    if (!text || !String(text).trim()) return '';
    return String(text).trim().split(/(\s+)/).map(function (part) {
      return part.trim() ? transliterateWord(part) : part;
    }).join('').replace(/\s+/g, ' ').trim();
  }

  function bindAutoLatin(arId, enId) {
    var arEl = document.getElementById(arId);
    var enEl = document.getElementById(enId);
    if (!arEl || !enEl) return;

    var manual = false;
    enEl.addEventListener('input', function () {
      manual = enEl.value.trim().length > 0;
    });
    enEl.addEventListener('focus', function () {
      if (!enEl.value.trim()) manual = false;
    });

    function sync() {
      if (manual) return;
      enEl.value = arabicToLatin(arEl.value);
    }

    arEl.addEventListener('input', sync);
    arEl.addEventListener('change', sync);
  }

  global.LiftCoreTranslit = {
    arabicToLatin: arabicToLatin,
    bindAutoLatin: bindAutoLatin,
  };
})(window);
