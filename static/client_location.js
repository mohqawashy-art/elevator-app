/* LiftCore — عنوان العميل: اتجاهات + صورة المبنى */
(function (global) {
  'use strict';

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function formatAddress(c) {
    var parts = [];
    if (c.address) parts.push(c.address);
    var area = [c.district, c.city].filter(Boolean).join(' — ');
    if (area) parts.push(area);
    return parts.join(' · ') || '—';
  }

  function hasCoordinates(c) {
    var lat = parseFloat(c.lat);
    var lng = parseFloat(c.lng);
    return !isNaN(lat) && !isNaN(lng);
  }

  function directionsUrl(c) {
    if (c.maps_url && /google\.com\/maps/i.test(c.maps_url)) {
      if (/dir\//i.test(c.maps_url)) return c.maps_url;
      if (hasCoordinates(c)) {
        return 'https://www.google.com/maps/dir/?api=1&destination=' +
          encodeURIComponent(c.lat + ',' + c.lng);
      }
      return c.maps_url;
    }
    if (hasCoordinates(c)) {
      return 'https://www.google.com/maps/dir/?api=1&destination=' +
        encodeURIComponent(c.lat + ',' + c.lng);
    }
    var addr = formatAddress(c);
    if (addr && addr !== '—') {
      return 'https://www.google.com/maps/dir/?api=1&destination=' + encodeURIComponent(addr);
    }
    return null;
  }

  function ensureModals() {
    if (document.getElementById('modal-cloc-actions')) return;
    document.body.insertAdjacentHTML('beforeend',
      '<div class="modal-overlay cloc-actions-overlay" id="modal-cloc-actions">' +
        '<div class="modal">' +
          '<div class="modal-head">' +
            '<div class="modal-title" id="cloc-actions-title">موقع العميل</div>' +
            '<button class="modal-close" onclick="LiftCoreLocation.closeActions()">' +
              '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">' +
                '<line x1="2" y1="2" x2="12" y2="12"/><line x1="12" y1="2" x2="2" y2="12"/>' +
              '</svg></button></div>' +
          '<div class="modal-body cloc-actions-body">' +
            '<div class="cloc-actions-address" id="cloc-actions-address"></div>' +
            '<div class="cloc-action-btns">' +
              '<button type="button" class="cloc-action-btn" id="cloc-btn-directions">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">' +
                  '<path d="M3 11l19-9-9 19-2-8-8-2z"/></svg><span>الاتجاهات</span></button>' +
              '<button type="button" class="cloc-action-btn" id="cloc-btn-building">' +
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">' +
                  '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 21v-6h6v6M9 9h.01M15 9h.01M9 13h.01M15 13h.01"/></svg>' +
                '<span>صورة المبنى</span></button>' +
            '</div></div></div></div>' +
      '<div class="modal-overlay cloc-photo-overlay" id="modal-cloc-photo">' +
        '<div class="modal">' +
          '<div class="modal-head">' +
            '<div class="modal-title" id="cloc-photo-title">صورة المبنى</div>' +
            '<button class="modal-close" onclick="LiftCoreLocation.closePhoto()">' +
              '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">' +
                '<line x1="2" y1="2" x2="12" y2="12"/><line x1="12" y1="2" x2="2" y2="12"/>' +
              '</svg></button></div>' +
          '<div class="modal-body cloc-photo-body">' +
            '<div class="cloc-photo-wrap" id="cloc-photo-wrap"></div>' +
          '</div></div></div>'
    );
    document.getElementById('cloc-btn-directions').addEventListener('click', function () {
      if (global._clocCurrent) openDirections(global._clocCurrent);
    });
    document.getElementById('cloc-btn-building').addEventListener('click', function () {
      if (global._clocCurrent) showBuildingPhoto(global._clocCurrent);
    });
  }

  function openDirections(c) {
    var url = directionsUrl(c);
    if (!url) {
      alert('لا يوجد عنوان أو إحداثيات مسجّلة لهذا العميل');
      return;
    }
    window.open(url, '_blank', 'noopener');
  }

  function showBuildingPhoto(c) {
    ensureModals();
    document.getElementById('cloc-photo-title').textContent = 'صورة المبنى — ' + (c.name || '');
    var wrap = document.getElementById('cloc-photo-wrap');
    if (c.building_photo_url) {
      wrap.innerHTML = '<img src="' + esc(c.building_photo_url) + '" alt="صورة المبنى">';
    } else {
      wrap.innerHTML = '<div class="cloc-photo-empty">لا توجد صورة مبنى مرفوعة لهذا العميل.<br>يمكن رفعها من تعديل بيانات العميل.</div>';
    }
    document.getElementById('modal-cloc-photo').classList.add('open');
  }

  function openActions(c) {
    ensureModals();
    global._clocCurrent = c;
    document.getElementById('cloc-actions-title').textContent = c.name || 'موقع العميل';
    document.getElementById('cloc-actions-address').textContent = formatAddress(c);
    document.getElementById('modal-cloc-actions').classList.add('open');
  }

  function closeActions() {
    var el = document.getElementById('modal-cloc-actions');
    if (el) el.classList.remove('open');
  }

  function closePhoto() {
    var el = document.getElementById('modal-cloc-photo');
    if (el) el.classList.remove('open');
  }

  var _lookupFn = null;

  function setLookup(fn) {
    _lookupFn = fn;
  }

  function openById(id) {
    if (_lookupFn) {
      var found = _lookupFn(id);
      if (found) return openActions(normalize(found));
    }
    return fetchAndOpen(id);
  }

  function renderLocationBlock(c, options) {
    options = options || {};
    var addr = formatAddress(c);
    var hint = options.hint || 'اضغط للاتجاهات أو صورة المبنى';
    var id = c.id || 0;
    return '<div class="cloc-box" onclick="LiftCoreLocation.openById(' + id + ')">' +
      '<div class="cloc-label">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">' +
          '<path d="M12 21s7-4.5 7-11a7 7 0 10-14 0c0 6.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>' +
        'عنوان الموقع</div>' +
      '<div class="cloc-address">' + esc(addr) + '</div>' +
      '<div class="cloc-hint">' + esc(hint) + ' →</div>' +
    '</div>';
  }

  function normalize(c) {
    return {
      id: c.id,
      name: c.name || '',
      address: c.address || '',
      city: c.city || '',
      district: c.district || '',
      lat: c.lat || '',
      lng: c.lng || '',
      maps_url: c.maps_url || '',
      building_photo_url: c.building_photo_url || ''
    };
  }

  function fetchAndOpen(customerId) {
    return fetch('/api/customers/' + customerId + '/location')
      .then(function (r) { return r.json(); })
      .then(function (data) { openActions(normalize(data)); });
  }

  global.LiftCoreLocation = {
    formatAddress: formatAddress,
    directionsUrl: directionsUrl,
    openDirections: openDirections,
    showBuildingPhoto: showBuildingPhoto,
    openActions: openActions,
    closeActions: closeActions,
    closePhoto: closePhoto,
    renderLocationBlock: renderLocationBlock,
    normalize: normalize,
    fetchAndOpen: fetchAndOpen,
    openById: openById,
    setLookup: setLookup
  };
})(typeof window !== 'undefined' ? window : this);
