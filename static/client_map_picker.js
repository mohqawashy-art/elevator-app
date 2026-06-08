/* LiftCore — تحديد موقع العميل (Google Maps أو OpenStreetMap تلقائياً) */
(function (global) {
  'use strict';

  var state = {
    provider: null,
    map: null,
    marker: null,
    geocoder: null,
    autocomplete: null,
    opts: null,
    initialized: false,
    hasPoint: false,
    searchBound: false,
  };

  var DEFAULT_CENTER = { lat: 21.4225, lng: 39.8262 };
  var POI_STYLES = [
    { featureType: 'poi', stylers: [{ visibility: 'off' }] },
    { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
  ];
  var NOMINATIM_HEADERS = { 'Accept-Language': 'ar' };

  function $(id) {
    return typeof id === 'string' ? document.getElementById(id) : id;
  }

  function mapsReady() {
    return !!(global.google && google.maps);
  }

  function preferLeaflet() {
    if (global.__gmapsAuthFailed) return true;
    if (!global.LIFTCORE_GOOGLE_MAPS_KEY) return true;
    return false;
  }

  function clearMapContainer() {
    var mapEl = state.opts && $(state.opts.mapEl);
    if (!mapEl) return;
    if (state.provider === 'leaflet' && state.map) {
      try { state.map.remove(); } catch (e) { /* ignore */ }
    }
    mapEl.innerHTML = '';
  }

  function getGeocoder() {
    if (!mapsReady()) return null;
    if (!state.geocoder) state.geocoder = new google.maps.Geocoder();
    return state.geocoder;
  }

  function defaultPinIcon(color) {
    color = color || '#1fb87a';
    if (typeof global.makePinIcon === 'function' && mapsReady()) {
      return global.makePinIcon(color, 1.2);
    }
    return {
      path: google.maps.SymbolPath.CIRCLE,
      fillColor: color,
      fillOpacity: 1,
      strokeColor: '#fff',
      strokeWeight: 2,
      scale: 10,
    };
  }

  function pinColor() {
    if (state.opts && typeof state.opts.getPinColor === 'function') {
      return state.opts.getPinColor() || '#1fb87a';
    }
    return '#1fb87a';
  }

  function refreshMarkerIcon() {
    if (state.provider === 'leaflet' && state.marker) {
      state.marker.setStyle({ fillColor: pinColor() });
      return;
    }
    if (state.marker && state.provider === 'google') {
      state.marker.setIcon(defaultPinIcon(pinColor()));
    }
  }

  function parseAddressComponents(components) {
    var out = { address: '', city: '', district: '' };
    var route = '';
    var streetNumber = '';
    (components || []).forEach(function (c) {
      var t = c.types || [];
      if (t.indexOf('street_number') >= 0) streetNumber = c.long_name;
      if (t.indexOf('route') >= 0) route = c.long_name;
      if (t.indexOf('sublocality_level_1') >= 0 || t.indexOf('neighborhood') >= 0) {
        if (!out.district) out.district = c.long_name;
      }
      if (t.indexOf('sublocality') >= 0 && !out.district) out.district = c.long_name;
      if (t.indexOf('locality') >= 0) out.city = c.long_name;
      if (t.indexOf('administrative_area_level_2') >= 0 && !out.city) out.city = c.long_name;
    });
    if (route) out.address = (streetNumber ? streetNumber + ' ' : '') + route;
    return out;
  }

  function emitUpdate(payload) {
    state.hasPoint = !!(payload && payload.lat && payload.lng);
    updateCoordsLabel(payload);
    if (state.opts && typeof state.opts.onUpdate === 'function') {
      state.opts.onUpdate(payload);
    }
  }

  function updateCoordsLabel(payload) {
    var el = state.opts && $(state.opts.coordsEl);
    if (!el) return;
    if (!payload || !payload.lat || !payload.lng) {
      if (state.provider === 'leaflet') {
        el.textContent = 'خريطة OpenStreetMap — ابحث أو انقر لتحديد الموقع';
      } else {
        el.textContent = 'لم يُحدَّد موقع بعد — اضغط على الخريطة أو ابحث أعلاه';
      }
      el.classList.remove('set');
      el.style.color = '';
      return;
    }
    var prefix = state.provider === 'leaflet' ? 'OSM GPS' : 'GPS';
    el.textContent = prefix + ': ' + Number(payload.lat).toFixed(6) + ', ' + Number(payload.lng).toFixed(6);
    el.classList.add('set');
    el.style.color = '';
  }

  function buildMapsUrl(lat, lng) {
    return 'https://www.google.com/maps?q=' + encodeURIComponent(lat + ',' + lng);
  }

  function applyGeocodeResult(result, lat, lng) {
    var parsed = parseAddressComponents(result.address_components);
    var formatted = result.formatted_address || parsed.address || '';
    emitUpdate({
      lat: String(lat),
      lng: String(lng),
      address: parsed.address || formatted,
      city: parsed.city,
      district: parsed.district,
      maps_url: result.url || buildMapsUrl(lat, lng),
      formatted_address: formatted,
    });
  }

  function applyOsmAddress(data, lat, lng) {
    var addr = (data && data.address) || {};
    emitUpdate({
      lat: String(lat),
      lng: String(lng),
      address: data.display_name || '',
      city: addr.city || addr.town || addr.state || addr.county || '',
      district: addr.suburb || addr.neighbourhood || addr.quarter || '',
      maps_url: buildMapsUrl(lat, lng),
      formatted_address: data.display_name || '',
    });
  }

  function reverseGeocodeGoogle(lat, lng) {
    var g = getGeocoder();
    if (!g) {
      emitUpdate({ lat: String(lat), lng: String(lng), address: '', city: '', district: '', maps_url: buildMapsUrl(lat, lng) });
      return;
    }
    g.geocode({ location: { lat: lat, lng: lng } }, function (results, status) {
      if (status === 'OK' && results && results[0]) {
        applyGeocodeResult(results[0], lat, lng);
      } else {
        reverseGeocodeOsm(lat, lng);
      }
    });
  }

  function reverseGeocodeOsm(lat, lng) {
    fetch(
      'https://nominatim.openstreetmap.org/reverse?format=json&lat=' +
        encodeURIComponent(lat) + '&lon=' + encodeURIComponent(lng),
      { headers: NOMINATIM_HEADERS }
    )
      .then(function (r) { return r.json(); })
      .then(function (data) { applyOsmAddress(data, lat, lng); })
      .catch(function () {
        emitUpdate({ lat: String(lat), lng: String(lng), address: '', city: '', district: '', maps_url: buildMapsUrl(lat, lng) });
      });
  }

  function reverseGeocode(lat, lng) {
    if (state.provider === 'leaflet') reverseGeocodeOsm(lat, lng);
    else reverseGeocodeGoogle(lat, lng);
  }

  function setMarkerPosition(lat, lng, pan) {
    if (!state.map) return;
    if (state.provider === 'leaflet') {
      setLeafletMarker(lat, lng, pan);
      return;
    }
    var pos = { lat: lat, lng: lng };
    if (!state.marker) {
      state.marker = new google.maps.Marker({
        position: pos,
        map: state.map,
        draggable: true,
        icon: defaultPinIcon(pinColor()),
      });
      state.marker.addListener('dragend', function () {
        var p = state.marker.getPosition();
        reverseGeocode(p.lat(), p.lng());
      });
    } else {
      state.marker.setPosition(pos);
      state.marker.setMap(state.map);
      refreshMarkerIcon();
    }
    if (pan !== false) {
      state.map.panTo(pos);
      if (state.map.getZoom() < 15) state.map.setZoom(16);
    }
    reverseGeocode(lat, lng);
  }

  function setLeafletMarker(lat, lng, pan) {
    var color = pinColor();
    if (!state.marker) {
      state.marker = L.circleMarker([lat, lng], {
        radius: 10,
        color: '#ffffff',
        weight: 2,
        fillColor: color,
        fillOpacity: 1,
        draggable: false,
      }).addTo(state.map);
      state.marker.on('mousedown', function () {
        state.map.dragging.disable();
        state.map.on('mousemove', onLeafletDrag);
        global.addEventListener('mouseup', onLeafletDragEnd, { once: true });
      });
    } else {
      state.marker.setLatLng([lat, lng]);
      state.marker.setStyle({ fillColor: color });
    }
    if (pan !== false) {
      state.map.setView([lat, lng], Math.max(state.map.getZoom(), 15));
    }
    reverseGeocode(lat, lng);
  }

  function onLeafletDrag(e) {
    if (state.marker) state.marker.setLatLng(e.latlng);
  }

  function onLeafletDragEnd() {
    state.map.dragging.enable();
    state.map.off('mousemove', onLeafletDrag);
    if (state.marker) {
      var p = state.marker.getLatLng();
      reverseGeocode(p.lat, p.lng);
    }
  }

  function onMapClick(e) {
    setMarkerPosition(e.latLng.lat(), e.latLng.lng());
  }

  function onPlaceSelected() {
    if (!state.autocomplete) return;
    var place = state.autocomplete.getPlace();
    if (!place || !place.geometry || !place.geometry.location) return;
    var loc = place.geometry.location;
    var lat = loc.lat();
    var lng = loc.lng();
    if (place.geometry.viewport) state.map.fitBounds(place.geometry.viewport);
    else {
      state.map.setCenter({ lat: lat, lng: lng });
      state.map.setZoom(17);
    }
    setMarkerPosition(lat, lng, false);
    if (place.address_components) {
      applyGeocodeResult({
        address_components: place.address_components,
        formatted_address: place.formatted_address,
        url: place.url,
      }, lat, lng);
    }
  }

  function bindMyLocation() {
    var btn = state.opts && $(state.opts.myLocEl);
    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
    var defaultHtml = btn.innerHTML;
    btn.addEventListener('click', function () {
      if (!navigator.geolocation) {
        alert('المتصفح لا يدعم تحديد الموقع');
        return;
      }
      btn.disabled = true;
      btn.textContent = 'جاري التحديد...';
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          btn.disabled = false;
          btn.innerHTML = defaultHtml;
          setMarkerPosition(pos.coords.latitude, pos.coords.longitude);
        },
        function () {
          btn.disabled = false;
          btn.innerHTML = defaultHtml;
          alert('تعذّر الحصول على موقعك — تحقق من صلاحيات الموقع');
        },
        { enableHighAccuracy: true, timeout: 12000 }
      );
    });
  }

  function bindGoogleSearch() {
    var input = state.opts && $(state.opts.searchEl);
    if (!input || !google.maps.places) return;
    if (state.autocomplete) google.maps.event.clearInstanceListeners(state.autocomplete);
    state.autocomplete = new google.maps.places.Autocomplete(input, {
      componentRestrictions: { country: 'sa' },
      fields: ['address_components', 'formatted_address', 'geometry', 'name', 'url'],
    });
    state.autocomplete.bindTo('bounds', state.map);
    state.autocomplete.addListener('place_changed', onPlaceSelected);
  }

  function bindLeafletSearch() {
    var input = state.opts && $(state.opts.searchEl);
    if (!input || state.searchBound) return;
    state.searchBound = true;
    input.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      var q = input.value.trim();
      if (!q) return;
      geocodeAddressOsm(q);
    });
  }

  function geocodeAddressOsm(query, callback) {
    fetch(
      'https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=sa&q=' +
        encodeURIComponent(query),
      { headers: NOMINATIM_HEADERS }
    )
      .then(function (r) { return r.json(); })
      .then(function (rows) {
        if (rows && rows[0]) {
          var lat = parseFloat(rows[0].lat);
          var lng = parseFloat(rows[0].lon);
          setMarkerPosition(lat, lng);
          applyOsmAddress({ display_name: rows[0].display_name, address: {} }, lat, lng);
          if (callback) callback(true);
        } else if (callback) callback(false);
      })
      .catch(function () { if (callback) callback(false); });
  }

  function ensureGoogleMap() {
    var mapEl = state.opts && $(state.opts.mapEl);
    if (!mapEl || !mapsReady()) return false;
    state.provider = 'google';
    if (!state.map) {
      var center = (state.opts && state.opts.defaultCenter) || DEFAULT_CENTER;
      state.map = new google.maps.Map(mapEl, {
        center: center,
        zoom: 12,
        mapTypeId: 'roadmap',
        clickableIcons: false,
        mapTypeControl: true,
        mapTypeControlOptions: {
          style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
          position: google.maps.ControlPosition.TOP_LEFT,
          mapTypeIds: ['roadmap', 'satellite', 'hybrid'],
        },
        streetViewControl: false,
        fullscreenControl: true,
        zoomControl: true,
        styles: (state.opts && state.opts.poiStyles) || POI_STYLES,
      });
      state.map.addListener('click', onMapClick);
      bindGoogleSearch();
      bindMyLocation();
      state.initialized = true;
      scheduleGoogleErrorCheck();
    }
    return true;
  }

  function ensureLeafletMap() {
    var mapEl = state.opts && $(state.opts.mapEl);
    if (!mapEl || typeof L === 'undefined') return false;
    state.provider = 'leaflet';
    if (!state.map) {
      var center = (state.opts && state.opts.defaultCenter) || DEFAULT_CENTER;
      state.map = L.map(mapEl, { zoomControl: true }).setView([center.lat, center.lng], 12);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap',
      }).addTo(state.map);
      state.map.on('click', function (e) {
        setMarkerPosition(e.latlng.lat, e.latlng.lng);
      });
      bindLeafletSearch();
      bindMyLocation();
      state.initialized = true;
    }
    setTimeout(function () { if (state.map) state.map.invalidateSize(); }, 120);
    return true;
  }

  function scheduleGoogleErrorCheck() {
    setTimeout(function () {
      if (state.provider !== 'google') return;
      var mapEl = state.opts && $(state.opts.mapEl);
      if (!mapEl) return;
      if (mapEl.querySelector('.gm-err-container')) {
        global.__gmapsAuthFailed = true;
        var opts = state.opts;
        hardReset();
        if (opts) init(opts);
      }
    }, 1800);
  }

  function init(options) {
    if (state.map && state.opts && options && state.opts.mapEl !== options.mapEl) {
      hardReset();
    }
    state.opts = options || {};
    global.LiftCoreMapPicker._lastOpts = state.opts;
    state.hasPoint = false;
    clearMapContainer();
    state.map = null;
    state.marker = null;
    state.initialized = false;

    if (preferLeaflet() || !mapsReady()) {
      if (!ensureLeafletMap()) return false;
      updateCoordsLabel(null);
      return true;
    }
    if (!ensureGoogleMap()) {
      if (!ensureLeafletMap()) return false;
    }
    updateCoordsLabel(null);
    return true;
  }

  function reset() {
    if (state.marker) {
      if (state.provider === 'leaflet' && state.map) state.map.removeLayer(state.marker);
      else if (state.marker.setMap) state.marker.setMap(null);
      state.marker = null;
    }
    state.hasPoint = false;
    var search = state.opts && $(state.opts.searchEl);
    if (search) search.value = '';
    var center = (state.opts && state.opts.defaultCenter) || DEFAULT_CENTER;
    if (state.map) {
      if (state.provider === 'leaflet') state.map.setView([center.lat, center.lng], 12);
      else {
        state.map.setCenter(center);
        state.map.setZoom(12);
      }
    }
    updateCoordsLabel(null);
  }

  function hardReset() {
    clearMapContainer();
    state.provider = null;
    state.map = null;
    state.marker = null;
    state.geocoder = null;
    state.autocomplete = null;
    state.initialized = false;
    state.hasPoint = false;
    state.searchBound = false;
    state.opts = null;
  }

  function setLocation(lat, lng, options) {
    options = options || {};
    if (!state.map && !init(state.opts || global.LiftCoreMapPicker._lastOpts || {})) return false;
    var la = parseFloat(lat);
    var ln = parseFloat(lng);
    if (isNaN(la) || isNaN(ln)) {
      reset();
      return false;
    }
    setMarkerPosition(la, ln);
    if (options.address || options.city || options.district) {
      emitUpdate({
        lat: String(la),
        lng: String(ln),
        address: options.address || '',
        city: options.city || '',
        district: options.district || '',
        maps_url: options.maps_url || buildMapsUrl(la, ln),
      });
    }
    return true;
  }

  function resize() {
    var mapEl = state.opts && $(state.opts.mapEl);
    if (mapEl) mapEl.style.minHeight = mapEl.style.minHeight || '260px';
    if (!state.map) return;
    var center = (state.opts && state.opts.defaultCenter) || DEFAULT_CENTER;
    if (state.provider === 'leaflet') {
      state.map.invalidateSize();
      if (state.marker) {
        var p = state.marker.getLatLng();
        state.map.setView(p, state.map.getZoom());
      } else state.map.setView([center.lat, center.lng], state.map.getZoom() || 12);
      return;
    }
    if (!google.maps) return;
    google.maps.event.trigger(state.map, 'resize');
    if (state.marker) {
      var gp = state.marker.getPosition();
      if (gp) state.map.setCenter(gp);
    } else state.map.setCenter(center);
  }

  function hasLocation() {
    return state.hasPoint;
  }

  function geocodeAddress(query, callback) {
    if (!query) return;
    if (state.provider === 'leaflet' || preferLeaflet()) {
      geocodeAddressOsm(query, callback);
      return;
    }
    var g = getGeocoder();
    if (!g) {
      geocodeAddressOsm(query, callback);
      return;
    }
    g.geocode({ address: query, region: 'SA' }, function (results, status) {
      if (status === 'OK' && results && results[0]) {
        var loc = results[0].geometry.location;
        setMarkerPosition(loc.lat(), loc.lng());
        if (callback) callback(true);
      } else if (callback) callback(false);
    });
  }

  global.LiftCoreMapPicker = {
    init: init,
    reset: reset,
    hardReset: hardReset,
    setLocation: setLocation,
    resize: resize,
    hasLocation: hasLocation,
    refreshMarkerIcon: refreshMarkerIcon,
    geocodeAddress: geocodeAddress,
    _lastOpts: null,
  };
})(typeof window !== 'undefined' ? window : this);
