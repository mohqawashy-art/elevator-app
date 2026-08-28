/**
 * شريط أذكار متحرك — فوتر الصفحات (خط رقعة).
 */
(function () {
  var SEP = ' ◆ ';
  var PX_PER_SEC = 42;
  var AZKAR = [
    'سبحان الله',
    'الحمد لله',
    'الله أكبر',
    'لا إله إلا الله',
    'سبحان الله وبحمده',
    'سبحان الله العظيم',
    'لا حول ولا قوة إلا بالله',
    'أستغفر الله',
    'اللهم صلِّ على محمد',
    'اللهم صلِّ وسلِّم على نبينا محمد',
    'سبحان الله والحمد لله ولا إله إلا الله والله أكبر',
    'حسبي الله لا إله إلا هو عليه توكلت',
    'اللهم بارك لنا في أعمالنا',
    'رضيت بالله رباً وبالإسلام ديناً وبمحمد ﷺ نبياً',
    'اللهم صلِّ على محمد وعلى آل محمد'
  ];

  function buildLine() {
    return AZKAR.join(SEP) + SEP;
  }

  function setDuration(track) {
    var half = track.scrollWidth / 2;
    if (!half) return;
    var sec = Math.max(45, Math.min(240, half / PX_PER_SEC));
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
