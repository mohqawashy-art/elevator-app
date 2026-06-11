/**
 * LiftCore — توقيع رقمي اختياري (هوية + PIN) بجانب الرسم اليدوي
 */
(function (global) {
  'use strict';

  let techSignMeta = { method: 'draw', signed_by: '', signed_at: '' };

  function paintImageOnCanvas(canvasId, url) {
    return new Promise(function (resolve, reject) {
      const canvas = document.getElementById(canvasId);
      if (!canvas) {
        reject(new Error('canvas missing'));
        return;
      }
      const ctx = canvas.getContext('2d');
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = function () {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
        const w = img.width * scale;
        const h = img.height * scale;
        const x = (canvas.width - w) / 2;
        const y = (canvas.height - h) / 2;
        ctx.drawImage(img, x, y, w, h);
        resolve();
      };
      img.onerror = function () { reject(new Error('image load failed')); };
      img.src = url;
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
      '<div class="dsign-title">توقيع بالهوية</div>' +
      '<p class="dsign-hint">أدخل رقم الهوية / الإقامة ورمز التوقيع (6 أرقام)</p>' +
      '<label>رقم الهوية</label>' +
      '<input type="text" id="dsign-nid" inputmode="numeric" autocomplete="off" dir="ltr">' +
      '<label>رمز التوقيع</label>' +
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

  function openPinModal(opts) {
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
          return paintImageOnCanvas(opts.canvasId, res.data.signature_url).then(function () {
            techSignMeta = {
              method: 'pin',
              signed_by: res.data.name || '',
              signed_at: res.data.signed_at || new Date().toISOString(),
            };
            closeModal();
            if (opts.onSuccess) opts.onSuccess(techSignMeta);
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
    canvas.style.opacity = enabled ? '1' : '0.65';
  }

  function initTechSignSlot(config) {
    if (!config || !config.editable) return;
    const modeWrap = document.getElementById('sig-tech-mode');
    const pinBtn = document.getElementById('sig-tech-pin-btn');
    const canvasId = 'sig-tech';
    const defaultMethod = config.defaultMethod || 'both';
    const showPin = defaultMethod !== 'draw';
    const showDraw = defaultMethod !== 'pin';

    if (!showPin && modeWrap) modeWrap.style.display = 'none';
    if (!showPin && pinBtn) pinBtn.style.display = 'none';

    const radios = document.querySelectorAll('input[name="sig-tech-method"]');
    let current = defaultMethod === 'pin' ? 'pin' : 'draw';
    if (defaultMethod === 'both') current = 'draw';

    radios.forEach(function (r) {
      if (r.value === 'draw' && !showDraw) r.parentElement.style.display = 'none';
      if (r.value === 'pin' && !showPin) r.parentElement.style.display = 'none';
      r.checked = r.value === current;
      r.addEventListener('change', function () {
        if (!r.checked) return;
        current = r.value;
        if (current === 'pin') {
          setCanvasDrawing(canvasId, false);
          if (pinBtn) pinBtn.style.display = '';
          techSignMeta.method = 'pin';
        } else {
          setCanvasDrawing(canvasId, true);
          if (pinBtn) pinBtn.style.display = 'none';
          techSignMeta = { method: 'draw', signed_by: '', signed_at: '' };
          if (global.LiftCoreChecklist) global.LiftCoreChecklist.clearSig(canvasId);
        }
      });
    });

    if (current === 'pin') {
      setCanvasDrawing(canvasId, false);
      if (pinBtn) pinBtn.style.display = '';
    }

    if (pinBtn) {
      pinBtn.addEventListener('click', function () {
        openPinModal({
          canvasId: canvasId,
          role: 'technician',
          visitId: config.visitId,
          prefillNationalId: config.prefillNationalId || '',
          onSuccess: config.onSuccess,
        });
      });
    }
  }

  function applyTechSignMeta(sig) {
    if (!sig || sig.tech_method !== 'pin') return;
    techSignMeta = {
      method: 'pin',
      signed_by: sig.tech_signed_by || '',
      signed_at: sig.tech_signed_at || '',
    };
    const pinRadio = document.querySelector('input[name="sig-tech-method"][value="pin"]');
    const pinBtn = document.getElementById('sig-tech-pin-btn');
    if (pinRadio) pinRadio.checked = true;
    setCanvasDrawing('sig-tech', false);
    if (pinBtn) pinBtn.style.display = '';
  }

  function getTechSignMeta() {
    return Object.assign({}, techSignMeta);
  }

  function clearTechSignMeta() {
    techSignMeta = { method: 'draw', signed_by: '', signed_at: '' };
  }

  global.LiftCoreDigitalSign = {
    initTechSignSlot,
    openPinModal,
    paintImageOnCanvas,
    applyTechSignMeta,
    getTechSignMeta,
    clearTechSignMeta,
    closeModal,
  };
})(window);
