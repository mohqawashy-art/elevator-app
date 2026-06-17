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
    return !!parseCoords(c && c.lat, c && c.lng);
  }

  /** تحليل lat/lng مع تصحيح الانقلاب الشائع في السعودية */
  function parseCoords(lat, lng) {
    function parseOne(v) {
      if (v == null || v === '') return NaN;
      var s = String(v).trim().replace(/,/g, '.');
      return parseFloat(s);
    }
    var la = parseOne(lat);
    var ln = parseOne(lng);
    if (isNaN(la) || isNaN(ln) || (la === 0 && ln === 0)) return null;
    if (la < -90 || la > 90 || ln < -180 || ln > 180) return null;

    function inSaudi(la, ln) {
      return la >= 15 && la <= 33 && ln >= 33 && ln <= 57;
    }
    if (inSaudi(la, ln)) return { lat: la, lng: ln };
    if (inSaudi(ln, la)) return { lat: ln, lng: la };
    return { lat: la, lng: ln };
  }

  var CITY_COORDS = {
    'مكة': { lat: 21.4225, lng: 39.8262 },
    'مكة المكرمة': { lat: 21.4225, lng: 39.8262 },
    'جدة': { lat: 21.5433, lng: 39.1728 },
    'جده': { lat: 21.5433, lng: 39.1728 },
    'الطائف': { lat: 21.2703, lng: 40.4158 },
    'المدينة': { lat: 24.4672, lng: 39.6111 },
    'المدينة المنورة': { lat: 24.4672, lng: 39.6111 },
    'الرياض': { lat: 24.7136, lng: 46.6753 },
    'الدمام': { lat: 26.4207, lng: 50.0888 },
    'الخبر': { lat: 26.2172, lng: 50.1971 },
    'أبها': { lat: 18.2164, lng: 42.5053 },
    'تبوك': { lat: 28.3838, lng: 36.5550 },
    'بريدة': { lat: 26.3259, lng: 43.9740 }
  };

  function resolveCityCoords(city) {
    if (!city) return null;
    var key = String(city).trim();
    if (CITY_COORDS[key]) return CITY_COORDS[key];
    var normalized = key.replace(/\s+/g, ' ');
    Object.keys(CITY_COORDS).some(function(k) {
      if (normalized.indexOf(k) >= 0 || k.indexOf(normalized) >= 0) {
        normalized = k;
        return true;
      }
      return false;
    });
    return CITY_COORDS[normalized] || null;
  }

  function coordsForCustomer(c) {
    if (!c) return null;
    var parsed = parseCoords(c.lat, c.lng);
    if (parsed) return { lat: parsed.lat, lng: parsed.lng, exact: true };
    var city = resolveCityCoords(c.city);
    if (city) return { lat: city.lat, lng: city.lng, exact: false };
    return null;
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

  function syncModals() {
    if (typeof global.syncModalA11y === 'function') global.syncModalA11y();
  }

  function setModalOpen(id, open) {
    var el = document.getElementById(id);
    if (!el) return;
    if (open) {
      el.classList.add('open');
      el.removeAttribute('inert');
      el.removeAttribute('aria-hidden');
    } else {
      el.classList.remove('open');
    }
    syncModals();
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
          '</div>' +
          '<div class="modal-foot cloc-photo-foot" id="cloc-photo-foot" style="display:none">' +
            '<button type="button" class="btn btn-secondary btn-sm" id="cloc-photo-download">تحميل الصورة</button>' +
          '</div></div></div>'
    );
    document.getElementById('cloc-btn-directions').addEventListener('click', function () {
      if (global._clocCurrent) openDirections(global._clocCurrent);
    });
    document.getElementById('cloc-btn-building').addEventListener('click', function () {
      if (global._clocCurrent) showBuildingPhoto(global._clocCurrent);
    });
    document.getElementById('cloc-photo-download').addEventListener('click', function () {
      if (global._clocPhotoDownloadUrl) {
        var a = document.createElement('a');
        a.href = global._clocPhotoDownloadUrl;
        a.download = global._clocPhotoDownloadName || 'building.jpg';
        a.rel = 'noopener';
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
    });
  }

  var _defaultBuildingPhoto = '/static/images/liftcore-header-logo.png';

  function setDefaultBuildingPhoto(url) {
    if (url) _defaultBuildingPhoto = url;
  }

  function buildingPhotoSrc(c) {
    return (c && c.building_photo_url) ? c.building_photo_url : _defaultBuildingPhoto;
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
    global._clocCurrent = c;
    var hasCustom = !!(c && c.building_photo_url);
    var src = buildingPhotoSrc(c);
    document.getElementById('cloc-photo-title').textContent = hasCustom
      ? ('صورة المبنى — ' + (c.name || ''))
      : ('LiftCore — ' + (c.name || ''));
    var wrap = document.getElementById('cloc-photo-wrap');
    wrap.classList.toggle('cloc-photo-wrap--default', !hasCustom);
    wrap.innerHTML = '';
    var img = document.createElement('img');
    img.alt = hasCustom ? 'صورة المبنى' : 'LiftCore';
    img.src = src;
    img.className = hasCustom ? '' : 'cloc-photo-default-logo';
    wrap.appendChild(img);
    var foot = document.getElementById('cloc-photo-foot');
    if (foot) foot.style.display = hasCustom ? 'flex' : 'none';
    global._clocPhotoDownloadUrl = hasCustom ? c.building_photo_url : '';
    global._clocPhotoDownloadName = 'building-' + (c.code || c.id || 'client') + '.jpg';
    setModalOpen('modal-cloc-photo', true);
  }

  function openActions(c) {
    ensureModals();
    global._clocCurrent = c;
    document.getElementById('cloc-actions-title').textContent = c.name || 'موقع العميل';
    document.getElementById('cloc-actions-address').textContent = formatAddress(c);
    setModalOpen('modal-cloc-actions', true);
  }

  function closeActions() {
    setModalOpen('modal-cloc-actions', false);
  }

  function closePhoto() {
    setModalOpen('modal-cloc-photo', false);
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
    parseCoords: parseCoords,
    resolveCityCoords: resolveCityCoords,
    coordsForCustomer: coordsForCustomer,
    CITY_COORDS: CITY_COORDS,
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
    setLookup: setLookup,
    setDefaultBuildingPhoto: setDefaultBuildingPhoto,
    buildingPhotoSrc: buildingPhotoSrc,
  };
})(typeof window !== 'undefined' ? window : this);
