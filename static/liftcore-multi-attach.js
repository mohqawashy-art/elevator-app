/**
 * LiftCore — مرفقات متعددة (إيرادات / مصروفات / عقود)
 */
(function (global) {
  'use strict';

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function formatNewFilesPreview(input, listEl) {
    if (!listEl) return;
    if (!input || !input.files || !input.files.length) {
      listEl.innerHTML = '';
      listEl.style.display = 'none';
      return;
    }
    listEl.style.display = 'block';
    listEl.innerHTML = Array.from(input.files).map(function (f) {
      return '<div class="lc-attach-new-item" style="font-size:12px;margin-top:4px;color:var(--text2)">+ ' +
        escHtml(f.name) + '</div>';
    }).join('');
  }

  function renderExisting(container, proofs, opts) {
    if (!container) return;
    opts = opts || {};
    var items = proofs || [];
    if (!items.length) {
      container.style.display = 'none';
      container.innerHTML = '';
      return;
    }
    container.style.display = 'block';
    var label = opts.label || 'المرفقات الحالية:';
    var canDelete = opts.adminOnly ? !!global.__LC_IS_ADMIN : true;
    var html = items.map(function (p, i) {
      var idx = p.index != null ? p.index : i;
      var url = p.url || '';
      var name = p.name || 'مستند';
      var delBtn = '';
      if (canDelete && opts.onRemove) {
        delBtn = ' <button type="button" class="btn btn-danger btn-sm lc-admin-delete" ' +
          'style="margin-inline-start:6px;padding:2px 8px;line-height:1.2" ' +
          'onclick="' + escHtml(opts.onRemove) + '(' + Number(opts.recordId) + ',' + idx + ')" title="حذف">×</button>';
      }
      return '<div class="lc-attach-existing-item" style="display:flex;align-items:center;gap:6px;margin-top:4px;flex-wrap:wrap">' +
        '<a href="' + escHtml(url) + '" target="_blank" rel="noopener" style="font-size:12px">📎 ' + escHtml(name) + '</a>' +
        delBtn +
        '</div>';
    }).join('');
    container.innerHTML = '<div style="font-size:12px;color:var(--text3);margin-bottom:4px">' + escHtml(label) + '</div>' + html;
    if (opts.hintAfter) {
      container.innerHTML += '<div style="font-size:11px;color:var(--text3);margin-top:6px">' + escHtml(opts.hintAfter) + '</div>';
    }
  }

  function appendToFormData(fd, input, fieldName) {
    if (!fd || !input || !input.files || !input.files.length) return 0;
    var n = 0;
    Array.from(input.files).forEach(function (file) {
      fd.append(fieldName, file);
      n += 1;
    });
    return n;
  }

  function proofsHtml(proofs, opts) {
    opts = opts || {};
    if (!proofs || !proofs.length) return opts.empty || '—';
    return proofs.map(function (p, i) {
      var url = p.url || '';
      var name = p.name || 'مستند';
      var adminDel = '';
      if (global.__LC_IS_ADMIN && opts.removeFn) {
        var idx = p.index != null ? p.index : i;
        adminDel = ' <button type="button" class="btn btn-danger btn-sm lc-admin-delete" onclick="' +
          opts.removeFn + '(' + Number(opts.recordId) + ',' + idx + ')">حذف</button>';
      }
      return '<a href="' + escHtml(url) + '" target="_blank" rel="noopener">' + escHtml(name) + '</a>' + adminDel;
    }).join('<br>');
  }

  global.LiftCoreMultiAttach = {
    escHtml: escHtml,
    formatNewFilesPreview: formatNewFilesPreview,
    renderExisting: renderExisting,
    appendToFormData: appendToFormData,
    proofsHtml: proofsHtml,
  };
})(typeof window !== 'undefined' ? window : this);
