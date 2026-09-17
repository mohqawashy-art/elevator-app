(function (global) {
  'use strict';

  var IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg)(?:\?|$)/i;
  var PDF_EXT = /\.pdf(?:\?|$)/i;
  var UPLOAD_PATH = /\/static\/uploads\//i;

  function msg(ar, en) {
    if (global.LC_I18N && LC_I18N.t) return LC_I18N.t(ar, en);
    return global.__LC_LANG === 'en' ? en : ar;
  }

  function normalizeUrl(href) {
    if (!href) return '';
    try {
      return new URL(href, global.location.origin).href;
    } catch (e) {
      return href;
    }
  }

  function isSameOrigin(url) {
    try {
      return new URL(url, global.location.origin).origin === global.location.origin;
    } catch (e2) {
      return false;
    }
  }

  function isViewableUpload(href) {
    var url = normalizeUrl(href);
    if (!url || !isSameOrigin(url)) return false;
    var path = '';
    try {
      path = new URL(url).pathname || '';
    } catch (e3) {
      return false;
    }
    if (!UPLOAD_PATH.test(path)) return false;
    return PDF_EXT.test(url) || IMAGE_EXT.test(url);
  }

  function fileNameFromUrl(url, fallback) {
    try {
      var base = decodeURIComponent((new URL(url).pathname.split('/').pop() || '').split('?')[0]);
      if (base) return base;
    } catch (e4) { /* ignore */ }
    return fallback || msg('مرفق', 'Attachment');
  }

  function isImageUrl(url) {
    return IMAGE_EXT.test(url);
  }

  var modal;
  var titleEl;
  var frameEl;
  var imgEl;
  var fallbackEl;
  var downloadEl;
  var openEl;
  var lastFocus;

  function ensureModal() {
    if (modal) return modal;
    modal = document.getElementById('lc-file-viewer');
    if (!modal) return null;
    titleEl = modal.querySelector('#lc-file-viewer-title');
    frameEl = modal.querySelector('.lc-file-viewer__frame');
    imgEl = modal.querySelector('.lc-file-viewer__img');
    fallbackEl = modal.querySelector('.lc-file-viewer__fallback');
    downloadEl = modal.querySelector('.lc-file-viewer__download');
    openEl = modal.querySelector('.lc-file-viewer__open');
    modal.querySelectorAll('[data-lc-file-viewer-close]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        close();
      });
    });
    document.addEventListener('keydown', function (e) {
      if (!modal || modal.hidden) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
      }
    });
    return modal;
  }

  function showPane(which) {
    if (frameEl) frameEl.hidden = which !== 'frame';
    if (imgEl) imgEl.hidden = which !== 'img';
    if (fallbackEl) fallbackEl.hidden = which !== 'fallback';
  }

  function open(url, title) {
    if (!ensureModal()) {
      global.location.href = url;
      return;
    }
    var safeUrl = normalizeUrl(url);
    var label = (title || '').trim() || fileNameFromUrl(safeUrl);
    lastFocus = document.activeElement;
    titleEl.textContent = label;
    if (downloadEl) {
      downloadEl.href = safeUrl;
      downloadEl.setAttribute('download', fileNameFromUrl(safeUrl, 'file'));
    }
    if (openEl) openEl.href = safeUrl;
    if (isImageUrl(safeUrl)) {
      showPane('img');
      imgEl.src = safeUrl;
      imgEl.alt = label;
      if (frameEl) frameEl.removeAttribute('src');
    } else {
      showPane('frame');
      frameEl.src = safeUrl;
      frameEl.title = label;
      if (imgEl) imgEl.removeAttribute('src');
    }
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    var closeBtn = modal.querySelector('.lc-file-viewer__close');
    if (closeBtn) closeBtn.focus();
  }

  function close() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (frameEl) frameEl.removeAttribute('src');
    if (imgEl) imgEl.removeAttribute('src');
    showPane('frame');
    if (lastFocus && typeof lastFocus.focus === 'function') lastFocus.focus();
  }

  function bindLinks(root) {
    (root || document).querySelectorAll('a[href]').forEach(function (a) {
      if (a.dataset.lcFileViewerBound === '1') return;
      if (a.dataset.lcNoFileView === '1' || a.hasAttribute('download')) return;
      if (a.classList.contains('lc-admin-delete')) return;
      if (!isViewableUpload(a.getAttribute('href'))) return;
      a.dataset.lcFileViewerBound = '1';
      a.classList.add('lc-file-view');
      a.addEventListener('click', function (e) {
        e.preventDefault();
        open(a.getAttribute('href'), a.textContent.trim());
      });
    });
  }

  function bindDelegated() {
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
      if (!a || a.dataset.lcNoFileView === '1' || a.hasAttribute('download')) return;
      if (a.classList.contains('lc-admin-delete')) return;
      if (a.classList.contains('lc-file-view')) return;
      if (!isViewableUpload(a.getAttribute('href'))) return;
      e.preventDefault();
      open(a.getAttribute('href'), a.textContent.trim());
    }, true);
  }

  function init() {
    ensureModal();
    bindDelegated();
    bindLinks();
  }

  global.LiftCoreFileViewer = {
    open: open,
    close: close,
    bindLinks: bindLinks,
    isViewableUpload: isViewableUpload,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(typeof window !== 'undefined' ? window : this);
