/**
 * شريط أذكار وأدعية — JSON محلي + تحريك (تلاشي/آلة كاتبة/شريط).
 */
(function () {
  var DATA_URL = '/static/data/azkar-duas.json?v=1';
  var SEP = ' ◆ ';
  var state = { items: [], config: {}, timer: null, idx: 0, reduced: false };

  function $(id) { return document.getElementById(id); }

  function shuffleDaily(items) {
    var list = items.slice();
    var d = new Date();
    var seed = d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
    for (var i = list.length - 1; i > 0; i--) {
      seed = (seed * 9301 + 49297) % 233280;
      var j = seed % (i + 1);
      var t = list[i];
      list[i] = list[j];
      list[j] = t;
    }
    return list;
  }

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function loadData(cb) {
    fetch(DATA_URL, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var items = (data && data.items) || [];
        cb({
          items: shuffleDaily(items.filter(function (x) { return x && x.text; })),
          config: data || {},
        });
      })
      .catch(function () {
        cb({
          items: shuffleDaily([
            { text: 'سُبْحَانَ اللَّهِ وَبِحَمْدِهِ', animation: 'fade' },
            { text: 'لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ', animation: 'fade' },
          ]),
          config: { defaultMode: 'fade', holdMs: 8000, fadeMs: 600, typewriterMs: 45 },
        });
      });
  }

  function setMarqueeDuration(track, pxPerSec) {
    var half = track.scrollWidth / 2;
    if (!half) return;
    var sec = Math.max(60, Math.min(420, half / (pxPerSec || 42)));
    track.style.setProperty('--lc-azkar-duration', sec + 's');
  }

  function startMarquee(items, cfg) {
    var track = $('lc-azkar-track');
    var rotate = $('lc-azkar-rotate');
    if (!track) return;
    if (rotate) rotate.hidden = true;
    track.hidden = false;
    if (track.dataset.lcReady === '1') return;

    var line = items.map(function (it) { return it.text; }).join(SEP) + SEP;
    var seg1 = document.createElement('span');
    seg1.className = 'lc-azkar-segment';
    seg1.textContent = line;
    var seg2 = seg1.cloneNode(true);
    seg2.setAttribute('aria-hidden', 'true');
    track.appendChild(seg1);
    track.appendChild(seg2);
    track.dataset.lcReady = '1';

    var px = cfg.marqueePxPerSec || 42;
    requestAnimationFrame(function () { setMarqueeDuration(track, px); });
    window.addEventListener('resize', function () { setMarqueeDuration(track, px); }, { passive: true });
  }

  function clearTimer() {
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }
  }

  function typewriter(el, text, ms, done) {
    el.textContent = '';
    var i = 0;
    function step() {
      if (i >= text.length) {
        if (done) done();
        return;
      }
      el.textContent += text.charAt(i);
      i += 1;
      state.timer = setTimeout(step, ms);
    }
    step();
  }

  function showRotateItem(item, cfg, onDone) {
    var box = $('lc-azkar-rotate');
    var label = $('lc-azkar-label');
    var textEl = $('lc-azkar-text');
    if (!box || !textEl) {
      if (onDone) onDone();
      return;
    }

    var holdMs = cfg.holdMs || 9000;
    var fadeMs = cfg.fadeMs || 650;
    var twMs = cfg.typewriterMs || 45;
    var useTypewriter = !state.reduced && item.animation === 'typewriter';

    if (label) {
      label.textContent = item.title || '';
      label.hidden = !item.title;
    }

    box.classList.remove('lc-azkar-visible');
    textEl.textContent = state.reduced ? item.text : '';

    requestAnimationFrame(function () {
      box.classList.add('lc-azkar-visible');
      clearTimer();

      function afterReveal() {
        state.timer = setTimeout(function () {
          box.classList.remove('lc-azkar-visible');
          state.timer = setTimeout(function () {
            if (onDone) onDone();
          }, fadeMs);
        }, holdMs);
      }

      if (useTypewriter) {
        typewriter(textEl, item.text, twMs, afterReveal);
      } else {
        textEl.textContent = item.text;
        afterReveal();
      }
    });
  }

  function startFadeRotation(items, cfg) {
    var track = $('lc-azkar-track');
    var rotate = $('lc-azkar-rotate');
    if (!rotate || !items.length) return;
    if (track) track.hidden = true;
    rotate.hidden = false;

    state.idx = 0;
    function next() {
      var item = items[state.idx % items.length];
      state.idx += 1;
      showRotateItem(item, cfg, next);
    }
    next();
  }

  function boot() {
    var footer = $('lc-azkar-footer');
    if (!footer || footer.dataset.lcBoot === '1') return;
    footer.dataset.lcBoot = '1';
    state.reduced = prefersReducedMotion();

    loadData(function (payload) {
      state.items = payload.items;
      state.config = payload.config;
      if (!state.items.length) return;

      var mode = (payload.config.defaultMode || 'fade').toLowerCase();
      if (state.reduced && mode === 'marquee') {
        startFadeRotation(state.items, payload.config);
        return;
      }
      if (mode === 'marquee') {
        startMarquee(state.items, payload.config);
      } else {
        startFadeRotation(state.items, payload.config);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.LiftCoreAzkar = {
    reload: function () {
      var footer = $('lc-azkar-footer');
      if (footer) delete footer.dataset.lcBoot;
      var track = $('lc-azkar-track');
      if (track) {
        track.innerHTML = '';
        delete track.dataset.lcReady;
      }
      clearTimer();
      boot();
    },
  };
})();
