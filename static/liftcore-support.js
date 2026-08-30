/* LiftCore — لسان دعم جانبي: يقترب فينزلق، يبتعد فيدخل */
(function () {
  'use strict';

  var LEAVE_MS = 280;
  var leaveTimer = null;

  function closestSupport(el) {
    while (el && el !== document) {
      if (el.classList && el.classList.contains('lc-support')) return el;
      el = el.parentNode;
    }
    return null;
  }

  function setExpanded(node, open) {
    node.classList.toggle('is-open', open);
    var btn = node.querySelector('.lc-support__btn');
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  function closeAll(except) {
    document.querySelectorAll('.lc-support.is-open').forEach(function (node) {
      if (except && node === except) return;
      setExpanded(node, false);
    });
  }

  function setNear(root, near) {
    if (!root) return;
    if (leaveTimer) {
      clearTimeout(leaveTimer);
      leaveTimer = null;
    }
    if (near) {
      root.classList.add('is-near');
      return;
    }
    leaveTimer = setTimeout(function () {
      root.classList.remove('is-near');
      setExpanded(root, false);
      leaveTimer = null;
    }, LEAVE_MS);
  }

  document.addEventListener('mouseover', function (e) {
    var root = closestSupport(e.target);
    if (root) setNear(root, true);
  });

  document.addEventListener('mouseout', function (e) {
    var root = closestSupport(e.target);
    if (!root) return;
    var next = e.relatedTarget;
    if (next && root.contains(next)) return;
    setNear(root, false);
  });

  document.addEventListener('focusin', function (e) {
    var root = closestSupport(e.target);
    if (root) setNear(root, true);
  });

  document.addEventListener('focusout', function (e) {
    var root = closestSupport(e.target);
    if (!root) return;
    var next = e.relatedTarget;
    if (next && root.contains(next)) return;
    setNear(root, false);
  });

  document.addEventListener('click', function (e) {
    var root = closestSupport(e.target);
    var btn = e.target.closest ? e.target.closest('.lc-support__btn') : null;
    if (btn && root) {
      e.preventDefault();
      var open = !root.classList.contains('is-open');
      closeAll(root);
      setExpanded(root, open);
      if (open) root.classList.add('is-near');
      return;
    }
    if (!root) closeAll();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll();
  });
})();
