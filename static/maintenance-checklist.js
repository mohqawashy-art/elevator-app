/**
 * LiftCore — قائمة فحص الصيانة (مشتركة بين الفني والمكتب)
 * SaaS: CHECKLIST_TEMPLATE يُحقَن من الخادم لكل مستأجر/زيارة.
 */
(function (global) {
  'use strict';

  const STATUS_LABELS = { ok: '✓ سليم', repair: '✗ إصلاح', na: '— لا ينطبق' };

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function buildChecklistTables(template, containerSelector, editable) {
    const root = document.querySelector(containerSelector);
    if (!root || !template || !template.sections) return;
    root.innerHTML = template.sections.map(sec => `
      <div class="checklist-section" data-section="${sec.id}">
        <div class="cl-header">
          <span class="cl-num">${sec.id}</span>
          ${escHtml(sec.title_ar)} — ${escHtml(sec.title_en)}
        </div>
        <table class="cl-table">
          <thead>
            <tr>
              <th class="th-ar">البند</th>
              <th class="cell-en" style="font-size:9px">Item (EN)</th>
              <th>الحالة</th>
              <th>ملاحظة</th>
            </tr>
          </thead>
          <tbody id="cl-${sec.id}">
            ${sec.items.map((item, i) => rowHtml(item, i, editable)).join('')}
          </tbody>
        </table>
      </div>`).join('');
  }

  function cssEsc(s) {
    if (global.CSS && global.CSS.escape) return CSS.escape(String(s));
    return String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  function rowHtml(item, index, editable) {
    const rawId = item.id || 'x_' + index;
    const id = escHtml(rawId);
    const dis = editable ? '' : ' disabled';
    function btn(val, cls, label) {
      return (
        '<button type="button" class="status-btn status-' + cls + '" data-value="' + val + '"' +
        ' aria-pressed="false"' + dis + '>' +
        label + '</button>'
      );
    }
    return (
      '<tr data-item-id="' + id + '">' +
      '<td class="cell-ar">' + escHtml(item.ar) + '</td>' +
      '<td class="cell-en">' + escHtml(item.en) + '</td>' +
      '<td class="cell-status">' +
      '<div class="status-group" data-item-id="' + id + '">' +
      btn('ok', 'ok', STATUS_LABELS.ok) +
      btn('repair', 'repair', STATUS_LABELS.repair) +
      btn('na', 'na', STATUS_LABELS.na) +
      '</div></td>' +
      '<td class="cell-note">' +
      '<input type="text" class="cl-note-input" data-item-id="' + id + '" placeholder="ملاحظة..."' +
      (editable ? '' : ' readonly') + '>' +
      '</td></tr>'
    );
  }

  function findStatusGroup(itemId) {
    return document.querySelector('.status-group[data-item-id="' + cssEsc(itemId) + '"]');
  }

  function setItemStatus(itemId, status) {
    const group = findStatusGroup(itemId);
    if (!group) return;
    group.querySelectorAll('.status-btn').forEach(function (b) {
      const on = b.getAttribute('data-value') === status;
      b.classList.toggle('is-selected', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function pickStatus(btn, ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    if (!btn || btn.disabled) return;
    const group = btn.closest('.status-group');
    if (!group) return;
    group.querySelectorAll('.status-btn').forEach(function (b) {
      b.classList.remove('is-selected');
      b.setAttribute('aria-pressed', 'false');
    });
    btn.classList.add('is-selected');
    btn.setAttribute('aria-pressed', 'true');
    if (group._onStatusChange) group._onStatusChange();
    else if (global.LiftCoreChecklist && global.LiftCoreChecklist._statusChange) {
      global.LiftCoreChecklist._statusChange();
    }
  }

  let statusTapInstalled = false;

  function initStatusGroups(root, onChange) {
    if (!root) return;
    global.LiftCoreChecklist._statusChange = onChange;
    root.querySelectorAll('.status-group').forEach(function (group) {
      group._onStatusChange = onChange;
    });
    if (statusTapInstalled) return;
    statusTapInstalled = true;
    function onStatusTap(e) {
      const btn = e.target.closest('#checklist-root .status-btn');
      if (!btn || btn.disabled) return;
      if (e.type === 'touchend') e.preventDefault();
      pickStatus(btn, e);
    }
    document.addEventListener('click', onStatusTap, true);
    document.addEventListener('touchend', onStatusTap, { capture: true, passive: false });
  }

  function applyReportData(reportData, template) {
    if (!reportData) return;
    const items = reportData.items || {};
    Object.keys(items).forEach(itemId => {
      const val = items[itemId] || {};
      if (val.status) setItemStatus(itemId, val.status);
      const note = document.querySelector(
        '.cl-note-input[data-item-id="' + cssEsc(itemId) + '"]'
      );
      if (note) note.value = val.note || '';
    });
    const meta = reportData.meta || {};
    const map = {
      'tech-notes': meta.tech_notes,
      'issues-found': meta.issues_found,
      'parts-used': meta.parts_used,
      'overall-status': meta.overall_status,
      'arrival-time': meta.arrival_time,
      'end-time': meta.end_time,
      'next-visit': meta.next_visit,
    };
    Object.entries(map).forEach(([elId, v]) => {
      const el = document.getElementById(elId);
      if (el && v != null) el.value = v;
    });
    applySignatures(reportData.signatures || {});
    applyPhotos(reportData.photos || []);
  }

  function applySignatures(signatures) {
    ['tech', 'client'].forEach(kind => {
      const data = signatures[kind];
      if (!data || !data.startsWith('data:')) return;
      const canvas = document.getElementById('sig-' + kind);
      if (!canvas) return;
      const img = new Image();
      img.onload = () => {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      };
      img.src = data;
    });
  }

  function applyPhotos(photos) {
    (photos || []).forEach((ph, idx) => {
      const i = idx + 1;
      const slot = document.querySelector(`.photo-slot[data-slot="${i}"]`);
      if (!slot || !ph.url) return;
      slot.querySelector('.photo-ph').style.display = 'none';
      const img = document.createElement('img');
      img.src = ph.url;
      slot.insertBefore(img, slot.querySelector('.photo-remove'));
      slot.classList.add('has-img');
      const cap = slot.querySelector('.photo-caption-input');
      if (cap) cap.value = ph.caption || '';
    });
  }

  function collectReportData(template) {
    const items = {};
    (template.sections || []).forEach(sec => {
      (sec.items || []).forEach(item => {
        const id = item.id;
        const group = findStatusGroup(id);
        const selected = group ? group.querySelector('.status-btn.is-selected') : null;
        const noteEl = document.querySelector(
          '.cl-note-input[data-item-id="' + cssEsc(id) + '"]'
        );
        items[id] = {
          status: selected ? selected.getAttribute('data-value') || '' : '',
          note: noteEl ? noteEl.value.trim() : '',
        };
      });
    });
    return {
      template_key: template.key,
      template_version: template.version,
      items,
      meta: {
        overall_status: val('overall-status'),
        arrival_time: val('arrival-time'),
        end_time: val('end-time'),
        tech_notes: val('tech-notes'),
        issues_found: val('issues-found'),
        parts_used: val('parts-used'),
        next_visit: val('next-visit'),
      },
      signatures: {
        tech: canvasDataUrl('sig-tech'),
        client: canvasDataUrl('sig-client'),
      },
      photos: collectPhotos(),
    };
  }

  function val(id) {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
  }

  function canvasDataUrl(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return '';
    const blank = document.createElement('canvas');
    blank.width = canvas.width;
    blank.height = canvas.height;
    if (canvas.toDataURL() === blank.toDataURL()) return '';
    return canvas.toDataURL('image/png');
  }

  function collectPhotos() {
    const out = [];
    document.querySelectorAll('.photo-slot.has-img').forEach(slot => {
      const img = slot.querySelector('img');
      const cap = slot.querySelector('.photo-caption-input');
      if (img && img.src) {
        out.push({ url: img.src, caption: cap ? cap.value.trim() : '' });
      }
    });
    return out;
  }

  function buildPhotosGrid(count, editable) {
    const grid = document.getElementById('photos-grid');
    if (!grid) return;
    grid.innerHTML = '';
    for (let i = 1; i <= count; i++) {
      grid.innerHTML += `
        <label class="photo-slot" data-slot="${i}" ${editable ? `onclick="LiftCoreChecklist.triggerPhoto(${i})"` : ''}>
          <input type="file" id="photo-input-${i}" accept="image/*" ${editable ? `onchange="LiftCoreChecklist.loadPhoto(this,${i})"` : ''} style="display:none">
          <div class="photo-ph"><div class="icon">📷</div><div class="txt">صورة ${i}</div></div>
          ${editable ? `<button type="button" class="photo-remove" onclick="LiftCoreChecklist.removePhoto(event,${i})">✕</button>` : ''}
          <input type="text" class="photo-caption-input" placeholder="وصف الصورة..." onclick="event.stopPropagation()" ${editable ? '' : 'readonly'}>
        </label>`;
    }
  }

  function triggerPhoto(i) {
    const slot = document.querySelector(`.photo-slot[data-slot="${i}"]`);
    if (slot && !slot.classList.contains('has-img')) {
      document.getElementById('photo-input-' + i).click();
    }
  }

  function loadPhoto(input, i) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
      const slot = document.querySelector(`.photo-slot[data-slot="${i}"]`);
      slot.querySelector('.photo-ph').style.display = 'none';
      const oldImg = slot.querySelector('img');
      if (oldImg) oldImg.remove();
      const img = document.createElement('img');
      img.src = e.target.result;
      slot.insertBefore(img, slot.querySelector('.photo-remove'));
      slot.classList.add('has-img');
    };
    reader.readAsDataURL(file);
  }

  function removePhoto(event, i) {
    event.preventDefault();
    event.stopPropagation();
    const slot = document.querySelector(`.photo-slot[data-slot="${i}"]`);
    const img = slot.querySelector('img');
    if (img) img.remove();
    document.getElementById('photo-input-' + i).value = '';
    slot.querySelector('.photo-ph').style.display = '';
    slot.classList.remove('has-img');
  }

  function setupSignature(canvasId, editable) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !editable) return;
    const ctx = canvas.getContext('2d');
    ctx.strokeStyle = '#1a3a5c';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    let drawing = false;
    let lastX = 0, lastY = 0;

    function getPos(e) {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      if (e.touches) {
        return {
          x: (e.touches[0].clientX - rect.left) * scaleX,
          y: (e.touches[0].clientY - rect.top) * scaleY,
        };
      }
      return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY,
      };
    }

    canvas.addEventListener('mousedown', e => {
      drawing = true;
      const p = getPos(e);
      lastX = p.x;
      lastY = p.y;
    });
    canvas.addEventListener('mousemove', e => {
      if (!drawing) return;
      const p = getPos(e);
      ctx.beginPath();
      ctx.moveTo(lastX, lastY);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      lastX = p.x;
      lastY = p.y;
    });
    canvas.addEventListener('mouseup', () => { drawing = false; });
    canvas.addEventListener('mouseleave', () => { drawing = false; });
    canvas.addEventListener('touchstart', e => {
      e.preventDefault();
      drawing = true;
      const p = getPos(e);
      lastX = p.x;
      lastY = p.y;
    }, { passive: false });
    canvas.addEventListener('touchmove', e => {
      e.preventDefault();
      if (!drawing) return;
      const p = getPos(e);
      ctx.beginPath();
      ctx.moveTo(lastX, lastY);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      lastX = p.x;
      lastY = p.y;
    }, { passive: false });
    canvas.addEventListener('touchend', () => { drawing = false; });
  }

  function clearSig(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  }

  global.LiftCoreChecklist = {
    buildChecklistTables,
    initStatusGroups,
    pickStatus,
    setItemStatus,
    applyReportData,
    collectReportData,
    buildPhotosGrid,
    triggerPhoto,
    loadPhoto,
    removePhoto,
    setupSignature,
    clearSig,
  };
})(window);
