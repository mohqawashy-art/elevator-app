/**
 * شريط أدعية نبوية متحرك — فوتر الصفحات (خط ديواني).
 */
(function () {
  var SEP = ' ◆ ';
  var PX_PER_SEC = 42;
  var AZKAR = [
    'اللَّهُمَّ آتِنَا في الدُّنْيَا حَسَنَةً وفي الآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ',
    'لَا إِلَهَ إِلَّا أَنْتَ سُبْحَانَكَ إِنِّي كُنْتُ مِنَ الظَّالِمِينَ',
    'يَا مُقَلِّبَ الْقُلُوبِ ثَبِّتْ قَلْبِي عَلَى دِينِكَ',
    'اللَّهُمَّ لَا سَهْلَ إِلَّا مَا جَعَلْتَهُ سَهْلًا وَأَنْتَ تَجْعَلُ الْحَزْنَ إِذَا شِئْتَ سَهْلًا'
  ];

  function buildLine() {
    return AZKAR.join(SEP) + SEP;
  }

  function setDuration(track) {
    var half = track.scrollWidth / 2;
    if (!half) return;
    var sec = Math.max(60, Math.min(360, half / PX_PER_SEC));
    track.style.setProperty('--lc-azkar-duration', sec + 's');
  }

  function start() {
    var track = document.getElementById('lc-azkar-track');
    if (!track || track.dataset.lcReady === '1') return;

    var text = buildLine();
    var seg1 = document.createElement('span');
    seg1.className = 'lc-azkar-segment';
    seg1.textContent = text;

    var seg2 = seg1.cloneNode(true);
    seg2.setAttribute('aria-hidden', 'true');

    track.appendChild(seg1);
    track.appendChild(seg2);
    track.dataset.lcReady = '1';

    requestAnimationFrame(function () {
      setDuration(track);
    });

    window.addEventListener('resize', function () {
      setDuration(track);
    }, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
