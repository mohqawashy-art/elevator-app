/**
 * LiftCore — تحويل الأسماء العربية إلى لاتيني (Transliteration)
 */
(function (global) {
  'use strict';

  var CHAR_MAP = {
    '\u0627': 'a', '\u0623': 'a', '\u0625': 'i', '\u0622': 'aa', '\u0671': 'a',
    '\u0628': 'b', '\u062A': 't', '\u062B': 'th', '\u062C': 'j', '\u062D': 'h', '\u062E': 'kh',
    '\u062F': 'd', '\u0630': 'th', '\u0631': 'r', '\u0632': 'z', '\u0633': 's', '\u0634': 'sh',
    '\u0635': 's', '\u0636': 'd', '\u0637': 't', '\u0638': 'z', '\u0639': '', '\u063A': 'gh',
    '\u0641': 'f', '\u0642': 'q', '\u0643': 'k', '\u0644': 'l', '\u0645': 'm', '\u0646': 'n',
    '\u0647': 'h', '\u0648': 'o', '\u0624': 'o', '\u064A': 'i', '\u0649': 'a', '\u0626': 'i',
    '\u0629': 'a', '\u0621': '', '\u0640': '',
    '\u064E': '', '\u064F': '', '\u0650': '', '\u0651': '', '\u0652': '',
    '\u064B': '', '\u064C': '', '\u064D': '',
  };

  var DICT = null;
  var DICT_READY = false;

  function normalizeAr(text) {
    return String(text || '')
      .replace(/[\u064B-\u065F\u0670\u0640]/g, '')
      .replace(/[أإآٱ]/g, '\u0627')
      .trim();
  }

  function titleWord(word) {
    if (!word) return '';
    if (word.indexOf('-') >= 0) {
      return word.split('-').map(titleWord).join('-');
    }
    return word.charAt(0).toUpperCase() + word.slice(1);
  }

  function lookupWord(word, words) {
    if (words[word]) {
      var mapped = words[word];
      if (
        word.indexOf('\u0627\u0644') === 0 && word.length > 2
        && mapped.indexOf('Al') !== 0
        && word.slice(-2) === '\u064A\u0629'
      ) {
        return 'Al-' + mapped;
      }
      return mapped;
    }
    if (word.indexOf('\u0627\u0644') === 0 && word.length > 2) {
      var stem = word.slice(2);
      if (words[stem]) {
        return words[stem].indexOf('Al') === 0 ? words[stem] : 'Al-' + words[stem];
      }
    }
    return null;
  }

  function phoneticWord(word) {
    if (word.length > 2 && word.slice(-2) === '\u064A\u0629') {
      var base = word.slice(0, -2);
      var body = '';
      for (var i = 0; i < base.length; i++) {
        var ch = base.charAt(i);
        if (CHAR_MAP[ch] !== undefined) body += CHAR_MAP[ch];
      }
      body = body.replace(/y+/g, 'i').replace(/aa+/g, 'a');
      return titleWord(body + 'ia');
    }

    var out = '';
    for (var j = 0; j < word.length; j++) {
      var c = word.charAt(j);
      if (CHAR_MAP[c] !== undefined) out += CHAR_MAP[c];
      else if (c === ' ' || c === '-' || c === '_' || c === '.') out += c;
      else if (/^[\w]$/.test(c)) out += c;
    }
    out = out.replace(/y+/g, 'i').replace(/oo+/g, 'o').replace(/aa+/g, 'a').replace(/^-+/, '');
    return out ? titleWord(out) : '';
  }

  function transliterateWord(word, words) {
    word = normalizeAr(word);
    if (!word) return '';
    if (/^[\w.\-]+$/.test(word)) return word;

    var hit = lookupWord(word, words);
    if (hit) return hit;

    if (word.indexOf('\u0627\u0644') === 0 && word.length > 2) {
      var stem = word.slice(2);
      hit = lookupWord(stem, words);
      if (hit) return hit.indexOf('Al') === 0 ? hit : 'Al-' + hit;
      var mapped = phoneticWord(stem);
      return mapped ? 'Al-' + mapped : 'Al';
    }

    return phoneticWord(word);
  }

  function buildDictionary(data) {
    var phrases = (data.phrases || []).slice().sort(function (a, b) {
      return b[0].length - a[0].length;
    });
    var labels = data.labels || {};
    var labelPhrases = Object.keys(labels).slice().sort(function (a, b) {
      return b.length - a.length;
    });
    return { phrases: phrases, words: data.words || {}, labels: labels, labelPhrases: labelPhrases };
  }

  function convertParts(parts, phrases, words) {
    var converted = [];
    var i = 0;
    while (i < parts.length) {
      var matched = false;
      for (var p = 0; p < phrases.length; p++) {
        var phrase = phrases[p];
        var phraseParts = phrase[0].split(/\s+/);
        var chunk = parts.slice(i, i + phraseParts.length);
        var same = chunk.length === phraseParts.length;
        if (same) {
          for (var k = 0; k < phraseParts.length; k++) {
            if (chunk[k] !== phraseParts[k]) same = false;
          }
        }
        if (same) {
          converted.push(phrase[1]);
          i += phraseParts.length;
          matched = true;
          break;
        }
      }
      if (matched) continue;
      converted.push(transliterateWord(parts[i], words));
      i += 1;
    }
    return converted;
  }

  function splitLabelPhrase(parts, labels, labelPhrases) {
    if (!parts.length) return { descriptors: [], remaining: [] };

    var descriptors = [];
    var remaining = parts.slice();

    while (remaining.length) {
      var matched = false;
      for (var i = 0; i < labelPhrases.length; i++) {
        var phrase = labelPhrases[i];
        var phraseParts = phrase.split(/\s+/);
        if (remaining.length <= phraseParts.length) continue;
        var chunk = remaining.slice(0, phraseParts.length);
        var same = chunk.length === phraseParts.length;
        if (same) {
          for (var k = 0; k < phraseParts.length; k++) {
            if (chunk[k] !== phraseParts[k]) same = false;
          }
        }
        if (same) {
          descriptors.push(labels[phrase]);
          remaining = remaining.slice(phraseParts.length);
          matched = true;
          break;
        }
      }
      if (!matched) break;
    }

    while (remaining.length > 1 && labels[remaining[0]]) {
      descriptors.push(labels[remaining[0]]);
      remaining = remaining.slice(1);
    }

    while (remaining.length > 1 && labels[remaining[remaining.length - 1]]) {
      descriptors.push(labels[remaining[remaining.length - 1]]);
      remaining = remaining.slice(0, -1);
    }

    if (remaining.length === 1 && labels[remaining[0]] && !descriptors.length) {
      return { descriptors: [labels[remaining[0]]], remaining: [] };
    }

    return { descriptors: descriptors, remaining: remaining };
  }

  function arabicToLatin(text) {
    if (!text || !String(text).trim()) return '';
    if (!DICT_READY || !DICT) return String(text).trim();

    var parts = normalizeAr(text).split(/\s+/).filter(Boolean);
    if (!parts.length) return '';

    var split = splitLabelPhrase(parts, DICT.labels || {}, DICT.labelPhrases || []);
    if (!split.remaining.length) {
      return split.descriptors.join(' ');
    }

    var converted = convertParts(split.remaining, DICT.phrases, DICT.words);
    var name = converted.join(' ').trim();
    if (split.descriptors.length && name) {
      return name + ' ' + split.descriptors.join(' ');
    }
    if (split.descriptors.length) {
      return split.descriptors.join(' ');
    }
    return name;
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

  function initDictionary(data) {
    DICT = buildDictionary(data || {});
    DICT_READY = true;
  }

  initDictionary({
    phrases: [
      ['\u0639\u0628\u062F \u0627\u0644\u0639\u0632\u064A\u0632', 'Abdulaziz'],
      ['\u0639\u0628\u062F\u0627\u0644\u0639\u0632\u064A\u0632', 'Abdulaziz'],
      ['\u0639\u0628\u062F \u0627\u0644\u0644\u0647', 'Abdullah'],
      ['\u0639\u0628\u062F\u0627\u0644\u0644\u0647', 'Abdullah'],
      ['\u0639\u0628\u062F \u0627\u0644\u0631\u062D\u0645\u0646', 'Abdurrahman'],
      ['\u0639\u0628\u062F\u0627\u0644\u0631\u062D\u0645\u0646', 'Abdurrahman'],
      ['\u0645\u0643\u0629 \u0627\u0644\u0645\u0643\u0631\u0645\u0629', 'Makkah'],
      ['\u0627\u0644\u0645\u062F\u064A\u0646\u0629 \u0627\u0644\u0645\u0646\u0648\u0631\u0629', 'Madinah']
    ],
    words: {
      '\u0645\u062D\u0645\u062F': 'Mohamed',
      '\u0623\u062D\u0645\u062F': 'Ahmed',
      '\u0627\u062D\u0645\u062F': 'Ahmed',
      '\u0625\u0628\u0631\u0627\u0647\u064A\u0645': 'Ibrahim',
      '\u0627\u0628\u0631\u0627\u0647\u064A\u0645': 'Ibrahim',
      '\u062E\u0627\u0644\u062F': 'Khaled',
      '\u0633\u0639\u0648\u062F': 'Saud',
      '\u0641\u0647\u062F': 'Fahd',
      '\u062A\u0631\u0643\u064A': 'Turki',
      '\u0639\u0645\u0631': 'Omar',
      '\u0639\u0644\u064A': 'Ali',
      '\u062D\u0633\u0646': 'Hassan',
      '\u062D\u0633\u064A\u0646': 'Hussein',
      '\u064A\u0648\u0633\u0641': 'Youssef',
      '\u0633\u0639\u062F': 'Saad',
      '\u0646\u0627\u0635\u0631': 'Nasser',
      '\u0633\u0644\u0645\u0627\u0646': 'Salman',
      '\u0641\u064A\u0635\u0644': 'Faisal',
      '\u0628\u0646\u062F\u0631': 'Bandar',
      '\u0633\u0644\u0637\u0627\u0646': 'Sultan',
      '\u0645\u0627\u062C\u062F': 'Majed',
      '\u0646\u0648\u0627\u0641': 'Nawaf',
      '\u0637\u0644\u0627\u0644': 'Talal',
      '\u0648\u0644\u064A\u062F': 'Waleed',
      '\u0631\u0627\u0634\u062F': 'Rashid',
      '\u0639\u0628\u062F': 'Abdul',
      '\u0639\u0628\u062F\u0627\u0644': 'Abdul',
      '\u0639\u0632\u064A\u0632': 'Aziz',
      '\u0627\u0644\u0639\u0632\u064A\u0632': 'Aziz',
      '\u0631\u062D\u0645\u0646': 'Rahman',
      '\u0627\u0644\u0631\u062D\u0645\u0646': 'Rahman',
      '\u0641\u0627\u0637\u0645\u0629': 'Fatima',
      '\u0646\u0648\u0631\u0629': 'Noura',
      '\u0633\u0627\u0631\u0629': 'Sara',
      '\u0645\u0643\u0629': 'Makkah',
      '\u062C\u062F\u0629': 'Jeddah',
      '\u0627\u0644\u0631\u064A\u0627\u0636': 'Riyadh',
      '\u0627\u0644\u062F\u0645\u0627\u0645': 'Dammam',
      '\u0627\u0644\u0645\u062F\u064A\u0646\u0629': 'Madinah',
      '\u0627\u0644\u0637\u0627\u0626\u0641': 'Taif',
      '\u0627\u0644\u0639\u0632\u064A\u0632\u064A\u0629': 'Azizia',
      '\u0639\u0632\u064A\u0632\u064A\u0629': 'Azizia',
      '\u0627\u0644\u0634\u0631\u0627\u0626\u0639': 'Sharaie',
      '\u0634\u0631\u0627\u0626\u0639': 'Sharaie',
      '\u0627\u0644\u0639\u0648\u0627\u0644\u064A': 'Awali',
      '\u0639\u0648\u0627\u0644\u064A': 'Awali',
      '\u0627\u0644\u062D\u0645\u0631\u0627\u0621': 'Hamra',
      '\u062D\u0645\u0631\u0627\u0621': 'Hamra',
      '\u0627\u0644\u0634\u0648\u0642\u064A\u0629': 'Shuqaia',
      '\u0634\u0648\u0642\u064A\u0629': 'Shuqaia',
      '\u0627\u0644\u062E\u0627\u0644\u062F\u064A\u0629': 'Khalidia',
      '\u062E\u0627\u0644\u062F\u064A\u0629': 'Khalidia',
      '\u0627\u0644\u0641\u064A\u0635\u0644\u064A\u0629': 'Faisaliah',
      '\u0641\u064A\u0635\u0644\u064A\u0629': 'Faisaliah',
      '\u0627\u0644\u0631\u0648\u0627\u0628\u064A': 'Rawabi',
      '\u0631\u0648\u0627\u0628\u064A': 'Rawabi',
      '\u0627\u0644\u0633\u0644\u0627\u0645\u0629': 'Salamah',
      '\u0633\u0644\u0627\u0645\u0629': 'Salamah',
      '\u0627\u0644\u0628\u0648\u0627\u062F\u064A': 'Bawadi',
      '\u0628\u0648\u0627\u062F\u064A': 'Bawadi',
      '\u0627\u0644\u0631\u0627\u0634\u062F\u064A\u0629': 'Rashidia',
      '\u0631\u0627\u0634\u062F\u064A\u0629': 'Rashidia',
      '\u0627\u0644\u0645\u062D\u0645\u062F\u064A\u0629': 'Mohammadia',
      '\u0645\u062D\u0645\u062F\u064A\u0629': 'Mohammadia',
      '\u0623\u0628\u0648': 'Abu',
      '\u0627\u0628\u0648': 'Abu',
      '\u0628\u0646': 'Bin'
    }
  });

  fetch('/static/translit-dictionary.json?v=2')
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) { if (data) initDictionary(data); })
    .catch(function () { /* keep embedded fallback */ });

  global.LiftCoreTranslit = {
    arabicToLatin: arabicToLatin,
    bindAutoLatin: bindAutoLatin,
  };
})(window);
