/**
 * LiftCore — توقيع محفوظ: زر «إضافة توقيع» + هوية + كلمة مرور
 */
(function (global) {
  'use strict';

  const slots = {};

  function paintImageOnCanvas(canvasId, src) {
    return new Promise(function (resolve, reject) {
      const canvas = document.getElementById(canvasId);
      if (!canvas || !src) {
        reject(new Error('canvas missing'));
        return;
      }
      const ctx = canvas.getContext('2d');
      const img = new Image();
      img.onload = function () {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
        const w = img.width * scale;
        const h = img.height * scale;
        ctx.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
        resolve();
      };
      img.onerror = function () { reject(new Error('image load failed')); };
      img.src = src;
    });
  }

  function ensureModal() {
    let modal = document.getElementById('dsign-modal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'dsign-modal';
    modal.innerHTML =
      '<div class="dsign-backdrop">' +
      '<div class="dsign-card" role="dialog" aria-modal="true">' +
      '<div class="dsign-title">إضافة توقيع</div>' +
      '<p class="dsign-hint">أدخل رقم الهوية / الإقامة وكلمة مرور التوقيع (6 أرقام)</p>' +
      '<label>رقم الهوية</label>' +
      '<input type="text" id="dsign-nid" inputmode="numeric" autocomplete="off" dir="ltr">' +
      '<label>كلمة المرور</label>' +
      '<input type="password" id="dsign-pin" inputmode="numeric" maxlength="6" autocomplete="off" dir="ltr">' +
      '<div class="dsign-error" id="dsign-error"></div>' +
      '<div class="dsign-actions">' +
      '<button type="button" class="dsign-btn dsign-cancel" id="dsign-cancel">إلغاء</button>' +
      '<button type="button" class="dsign-btn dsign-ok" id="dsign-ok">توقيع</button>' +
      '</div></div></div>';
    document.body.appendChild(modal);
    modal.querySelector('#dsign-cancel').addEventListener('click', closeModal);
    modal.querySelector('.dsign-backdrop').addEventListener('click', function (e) {
      if (e.target.classList.contains('dsign-backdrop')) closeModal();
    });
    return modal;
  }

  function closeModal() {
    const modal = document.getElementById('dsign-modal');
    if (modal) modal.classList.remove('open');
  }

  function openSignModal(opts) {
    const modal = ensureModal();
    const nidEl = modal.querySelector('#dsign-nid');
    const pinEl = modal.querySelector('#dsign-pin');
    const errEl = modal.querySelector('#dsign-error');
    const okBtn = modal.querySelector('#dsign-ok');
    errEl.textContent = '';
    nidEl.value = opts.prefillNationalId || '';
    pinEl.value = '';
    modal.classList.add('open');
    setTimeout(function () { (nidEl.value ? pinEl : nidEl).focus(); }, 50);

    function submit() {
      errEl.textContent = '';
      okBtn.disabled = true;
      fetch('/api/signatures/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          national_id: nidEl.value.trim(),
          pin: pinEl.value.trim(),
          role: opts.role || 'technician',
          visit_id: opts.visitId || null,
        }),
      })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (res) {
          if (!res.ok || !res.data.ok) throw new Error(res.data.error || 'تعذّر التحقق');
          const src = res.data.signature_data || res.data.signature_url || '';
          if (!src) throw new Error('لا توجد صورة توقيع');
          return paintImageOnCanvas(opts.canvasId, src).then(function () {
            const slot = slots[opts.canvasId] || {};
            slot.meta = {
              method: 'pin',
              signed_by: res.data.name || '',
              signed_at: res.data.signed_at || new Date().toISOString(),
            };
            slots[opts.canvasId] = slot;
            closeModal();
            if (opts.onSuccess) opts.onSuccess(slot.meta);
          });
        })
        .catch(function (err) {
          errEl.textContent = err.message || 'تعذّر التوقيع';
        })
        .finally(function () { okBtn.disabled = false; });
    }

    okBtn.onclick = submit;
    pinEl.onkeydown = function (e) { if (e.key === 'Enter') submit(); };
  }

  function setCanvasDrawing(canvasId, enabled) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    canvas.style.pointerEvents = enabled ? 'auto' : 'none';
    canvas.style.opacity = enabled ? '1' : '0.92';
  }

  function initSignSlot(canvasId, config) {
    if (!config || !config.editable) return;
    const addBtn = document.getElementById(config.addButtonId);
    const drawLink = document.getElementById(config.drawLinkId);
    const method = config.defaultMethod || 'pin';
    const allowPin = method !== 'draw';
    const allowDraw = method !== 'pin';

    slots[canvasId] = { meta: { method: allowDraw ? 'draw' : 'pin', signed_by: '', signed_at: '' } };

    if (!allowPin && addBtn) addBtn.style.display = 'none';
    if (!allowDraw) {
      setCanvasDrawing(canvasId, false);
      if (drawLink) drawLink.style.display = 'none';
    } else if (method === 'both') {
      setCanvasDrawing(canvasId, false);
    } else {
      setCanvasDrawing(canvasId, true);
    }

    if (addBtn && allowPin) {
      addBtn.addEventListener('click', function () {
        openSignModal({
          canvasId: canvasId,
          role: config.role || 'technician',
          visitId: config.visitId,
          prefillNationalId: config.prefillNationalId || '',
          onSuccess: config.onSuccess,
        });
      });
    }

    if (drawLink && allowDraw) {
      drawLink.addEventListener('click', function (e) {
        e.preventDefault();
        setCanvasDrawing(canvasId, true);
        slots[canvasId].meta = { method: 'draw', signed_by: '', signed_at: '' };
        if (global.LiftCoreChecklist) global.LiftCoreChecklist.clearSig(canvasId);
      });
    }
  }

  function applyTechSignMeta(sig) {
    if (!sig || sig.tech_method !== 'pin') return;
    slots['sig-tech'] = {
      meta: {
        method: 'pin',
        signed_by: sig.tech_signed_by || '',
        signed_at: sig.tech_signed_at || '',
      },
    };
    setCanvasDrawing('sig-tech', false);
    if (sig.tech) paintImageOnCanvas('sig-tech', sig.tech).catch(function () {});
  }

  function getTechSignMeta() {
    const slot = slots['sig-tech'];
    return slot && slot.meta ? Object.assign({}, slot.meta) : { method: 'draw', signed_by: '', signed_at: '' };
  }

  function clearTechSignMeta() {
    if (slots['sig-tech']) {
      slots['sig-tech'].meta = { method: 'draw', signed_by: '', signed_at: '' };
    }
    setCanvasDrawing('sig-tech', false);
  }

  global.LiftCoreDigitalSign = {
    initSignSlot,
    openSignModal,
    paintImageOnCanvas,
    applyTechSignMeta,
    getTechSignMeta,
    clearTechSignMeta,
    closeModal,
    initTechSignSlot: function (config) {
      initSignSlot('sig-tech', {
        editable: config.editable,
        visitId: config.visitId,
        defaultMethod: config.defaultMethod,
        prefillNationalId: config.prefillNationalId,
        onSuccess: config.onSuccess,
        role: 'technician',
        addButtonId: 'sig-tech-add-btn',
        drawLinkId: 'sig-tech-draw-link',
      });
    },
  };
})(window);
