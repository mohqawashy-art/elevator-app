/* LiftCore — تحديد موقع العميل (Google Maps أو OpenStreetMap تلقائياً) */
(function (global) {
  'use strict';

  function lcT(s) {
    if (global.LiftCoreI18n && global.LiftCoreI18n.t) return global.LiftCoreI18n.t(s);
    return s;
  }

  var state = {
    provider: null,
    map: null,
    marker: null,
    geocoder: null,
    autocomplete: null,
    placeAutocompleteEl: null,
    placeSelectListener: null,
    autocompleteWrap: null,
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

  function dismissPlacesAutocomplete() {
    document.querySelectorAll('.pac-container').forEach(function (el) {
      el.style.display = 'none';
      el.style.visibility = 'hidden';
    });
    if (state.placeAutocompleteEl && state.placeAutocompleteEl.blur) {
      try { state.placeAutocompleteEl.blur(); } catch (e) { /* ignore */ }
    }
  }

  function teardownGoogleSearch() {
    if (state.placeSelectListener && state.placeAutocompleteEl) {
      try { state.placeAutocompleteEl.removeEventListener('gmp-select', state.placeSelectListener); } catch (e) { /* ignore */ }
    }
    state.placeSelectListener = null;
    if (state.placeAutocompleteEl) {
      try { state.placeAutocompleteEl.remove(); } catch (e) { /* ignore */ }
      state.placeAutocompleteEl = null;
    }
    if (state.autocompleteWrap) {
      try { state.autocompleteWrap.remove(); } catch (e) { /* ignore */ }
      state.autocompleteWrap = null;
    }
    if (state.autocomplete) {
      try { google.maps.event.clearInstanceListeners(state.autocomplete); } catch (e) { /* ignore */ }
      state.autocomplete = null;
    }
    var input = state.opts && $(state.opts.searchEl);
    if (input) input.style.display = '';
  }

  function suspendPlacesAutocomplete() {
    teardownGoogleSearch();
    state.autocompleteSuspended = true;
    dismissPlacesAutocomplete();
  }

  function ensurePlacesAutocomplete() {
    if (state.provider !== 'google' || !state.map || state.autocomplete || state.placeAutocompleteEl) return;
    bindGoogleSearch();
    state.autocompleteSuspended = false;
  }

  function bindSearchEnterKey(el, getQuery) {
    if (!el || el.dataset.lcEnterBound) return;
    el.dataset.lcEnterBound = '1';
    el.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      var q = (typeof getQuery === 'function' ? getQuery() : (el.value || '')).trim();
      if (!q) return;
      geocodeAddress(q);
    });
  }

  function setSearchValue(text) {
    var val = text || '';
    var input = state.opts && $(state.opts.searchEl);
    if (input) input.value = val;
    if (state.placeAutocompleteEl) state.placeAutocompleteEl.value = val;
  }

  function setSearchQuery(text) {
    var input = state.opts && $(state.opts.searchEl);
    if (!input) return;
    setSearchValue(text || '');
  }

  function setSearchQueryWithoutPac(searchEl, text) {
    if (!searchEl || !text) return;
    suspendPlacesAutocomplete();
    searchEl.setAttribute('autocomplete', 'off');
    searchEl.readOnly = true;
    setSearchValue(text);
    searchEl.blur();
    dismissPlacesAutocomplete();
    setTimeout(function () {
      searchEl.readOnly = false;
      dismissPlacesAutocomplete();
      if (state.provider === 'google' && state.map && !state.autocompleteSuspended) {
        bindGoogleSearch();
      }
    }, 400);
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
      if (global.LiftCoreMap && LiftCoreMap.refreshPinMarkerIcon) {
        LiftCoreMap.refreshPinMarkerIcon(state.marker, pinColor(), 1.2);
      } else {
        state.marker.setIcon(defaultPinIcon(pinColor()));
      }
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
        el.textContent = lcT('خريطة OpenStreetMap — ابحث أو انقر لتحديد الموقع');
      } else {
        el.textContent = lcT('لم يُحدَّد موقع بعد — اضغط على الخريطة أو ابحث أعلاه');
      }
      el.classList.remove('set');
      el.style.color = '';
      if (global.applyClientModalI18n) global.applyClientModalI18n();
      return;
    }
    var prefix = state.provider === 'leaflet' ? 'OSM GPS' : 'GPS';
    var gps = prefix + ': ' + Number(payload.lat).toFixed(6) + ', ' + Number(payload.lng).toFixed(6);
    var place = payload.formatted_address || payload.address || '';
    el.textContent = place ? place + ' · ' + gps : gps;
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

  function normalizeMarkerOpts(panOrOpts) {
    if (typeof panOrOpts === 'object' && panOrOpts !== null) return panOrOpts;
    return { pan: panOrOpts !== false };
  }

  function createMapMarker(pos) {
    var color = pinColor();
    if (global.LiftCoreMap && LiftCoreMap.createPinMarker) {
      var advanced = LiftCoreMap.createPinMarker({
        position: pos,
        map: state.map,
        draggable: true,
        color: color,
        scale: 1.2,
      });
      if (advanced) return advanced;
    }
    if (global.google && google.maps && google.maps.Marker) {
      return new google.maps.Marker({
        position: pos,
        map: state.map,
        draggable: true,
        icon: defaultPinIcon(color),
      });
    }
    return null;
  }

  function setMarkerPosition(lat, lng, panOrOpts) {
    var opts = normalizeMarkerOpts(panOrOpts);
    var pan = opts.pan !== false;
    var skipReverseGeocode = !!opts.skipReverseGeocode;
    if (!state.map) return;
    if (state.provider === 'leaflet') {
      setLeafletMarker(lat, lng, pan, skipReverseGeocode);
      return;
    }
    if (global.LiftCoreMap && LiftCoreMap.ensureMarkerLibReady && !LiftCoreMap.canUseAdvancedMarkers()) {
      LiftCoreMap.ensureMarkerLibReady(function () { setMarkerPosition(lat, lng, panOrOpts); });
      return;
    }
    var pos = { lat: lat, lng: lng };
    if (!state.marker) {
      state.marker = createMapMarker(pos);
      if (!state.marker) return;
      state.marker.addListener('dragend', function () {
        var p = global.LiftCoreMap && LiftCoreMap.getMarkerPosition
          ? LiftCoreMap.getMarkerPosition(state.marker)
          : (function () {
            if (state.marker.getPosition) {
              var gp = state.marker.getPosition();
              return { lat: gp.lat(), lng: gp.lng() };
            }
            if (state.marker.position) {
              var pp = state.marker.position;
              return {
                lat: typeof pp.lat === 'function' ? pp.lat() : pp.lat,
                lng: typeof pp.lng === 'function' ? pp.lng() : pp.lng,
              };
            }
            return null;
          })();
        if (p) reverseGeocode(p.lat, p.lng);
      });
    } else {
      if (global.LiftCoreMap && LiftCoreMap.setMarkerPosition) {
        LiftCoreMap.setMarkerPosition(state.marker, pos);
        LiftCoreMap.setMarkerMap(state.marker, state.map);
      } else {
        state.marker.setPosition(pos);
        state.marker.setMap(state.map);
      }
      refreshMarkerIcon();
    }
    if (pan !== false) {
      state.map.panTo(pos);
      if (state.map.getZoom() < 15) state.map.setZoom(16);
    }
    if (!skipReverseGeocode) reverseGeocode(lat, lng);
  }

  function setLeafletMarker(lat, lng, pan, skipReverseGeocode) {
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
    if (!skipReverseGeocode) reverseGeocode(lat, lng);
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

  function placeToGeocodeResult(place) {
    return {
      address_components: (place.addressComponents || []).map(function (c) {
        return {
          long_name: c.longText || '',
          short_name: c.shortText || '',
          types: c.types || [],
        };
      }),
      formatted_address: place.formattedAddress || '',
      url: place.googleMapsURI || '',
    };
  }

  function placeLatLng(place) {
    if (!place || !place.location) return null;
    var loc = place.location;
    var lat = typeof loc.lat === 'function' ? loc.lat() : loc.lat;
    var lng = typeof loc.lng === 'function' ? loc.lng() : loc.lng;
    if (lat == null || lng == null) return null;
    return { lat: lat, lng: lng };
  }

  function onPlaceSelectedLegacy() {
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
    setMarkerPosition(lat, lng, { pan: false });
    if (place.address_components) {
      applyGeocodeResult({
        address_components: place.address_components,
        formatted_address: place.formatted_address,
        url: place.url,
      }, lat, lng);
    }
  }

  function onPlaceSelectedNew(place) {
    if (!place || !state.map) return;
    var coords = placeLatLng(place);
    if (!coords) return;
    if (place.viewport) state.map.fitBounds(place.viewport);
    else {
      state.map.setCenter(coords);
      state.map.setZoom(17);
    }
    setMarkerPosition(coords.lat, coords.lng, { pan: false });
    applyGeocodeResult(placeToGeocodeResult(place), coords.lat, coords.lng);
  }

  function updatePlaceAutocompleteBias() {
    if (!state.placeAutocompleteEl || !state.map || !state.map.getBounds) return;
    try {
      var bounds = state.map.getBounds();
      if (bounds) state.placeAutocompleteEl.locationBias = bounds;
    } catch (e) { /* ignore */ }
  }

  function bindGoogleSearchLegacy(input) {
    if (!input || !google.maps.places) return;
    input.style.display = '';
    state.autocomplete = new google.maps.places.Autocomplete(input, {
      componentRestrictions: { country: 'sa' },
      fields: ['address_components', 'formatted_address', 'geometry', 'name', 'url'],
    });
    state.autocomplete.bindTo('bounds', state.map);
    state.autocomplete.addListener('place_changed', onPlaceSelectedLegacy);
    bindSearchEnterKey(input);
    state.autocompleteSuspended = false;
  }

  function bindGoogleSearchModern(input) {
    var PlaceAutocompleteElement = google.maps.places.PlaceAutocompleteElement;
    if (!PlaceAutocompleteElement) return false;

    input.style.display = 'none';
    var wrap = document.createElement('div');
    wrap.className = 'lc-place-autocomplete-wrap';
    input.insertAdjacentElement('afterend', wrap);
    state.autocompleteWrap = wrap;

    var pac = new PlaceAutocompleteElement({
      includedRegionCodes: ['SA'],
    });
    pac.className = 'map-picker-search lc-gmp-autocomplete';
    if (input.placeholder) pac.setAttribute('placeholder', input.placeholder);
    wrap.appendChild(pac);
    state.placeAutocompleteEl = pac;
    updatePlaceAutocompleteBias();

    state.placeSelectListener = function (event) {
      var prediction = event.placePrediction;
      if (!prediction || !prediction.toPlace) return;
      var place = prediction.toPlace();
      place.fetchFields({
        fields: ['addressComponents', 'formattedAddress', 'location', 'viewport', 'googleMapsURI'],
      }).then(function () {
        onPlaceSelectedNew(place);
      }).catch(function (err) { console.error('PlaceAutocomplete select', err); });
    };
    pac.addEventListener('gmp-select', state.placeSelectListener);
    bindSearchEnterKey(pac, function () { return pac.value || ''; });

    if (!state.boundsListener && state.map) {
      state.boundsListener = function () { updatePlaceAutocompleteBias(); };
      state.map.addListener('bounds_changed', state.boundsListener);
    }

    state.autocompleteSuspended = false;
    return true;
  }

  function bindGoogleSearch() {
    var input = state.opts && $(state.opts.searchEl);
    if (!input || !mapsReady()) return;
    teardownGoogleSearch();
    input.setAttribute('autocomplete', 'off');
    if (bindGoogleSearchModern(input)) return;
    bindGoogleSearchLegacy(input);
  }

  function getSearchQuery() {
    if (state.placeAutocompleteEl && state.placeAutocompleteEl.value) {
      return String(state.placeAutocompleteEl.value).trim();
    }
    var input = state.opts && $(state.opts.searchEl);
    return input && input.value ? input.value.trim() : '';
  }

  function runMapSearch(callback) {
    var q = getSearchQuery();
    if (!q) {
      alert('أدخل عنواناً للبحث');
      if (callback) callback(false);
      return;
    }
    geocodeAddress(q, callback);
  }

  function bindSearchButton() {
    var btn = state.opts && $(state.opts.searchBtnEl);
    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
    var defaultHtml = btn.innerHTML;
    btn.addEventListener('click', function () {
      var q = getSearchQuery();
      if (!q) {
        alert('أدخل عنواناً للبحث');
        return;
      }
      btn.disabled = true;
      btn.textContent = 'جاري البحث...';
      geocodeAddress(q, function (ok) {
        btn.disabled = false;
        btn.innerHTML = defaultHtml;
        if (!ok) alert('تعذّر العثور على هذا العنوان — جرّب صياغة أخرى أو انقر على الخريطة');
      });
    });
  }

  function bindLeafletSearch() {
    var input = state.opts && $(state.opts.searchEl);
    if (!input || state.searchBound) return;
    state.searchBound = true;
    bindSearchEnterKey(input);
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
      var mapOpts = {
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
      };
      if (global.LiftCoreMap && LiftCoreMap.mergeMapOptions) {
        mapOpts = LiftCoreMap.mergeMapOptions(mapOpts);
      }
      state.map = new google.maps.Map(mapEl, mapOpts);
      state.map.addListener('click', onMapClick);
      bindGoogleSearch();
      bindSearchButton();
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
      bindSearchButton();
      state.initialized = true;
    }
    setTimeout(function () { if (state.map) state.map.invalidateSize(); }, 120);
    return true;
  }

  function mapHasGoogleError(mapEl) {
    if (!mapEl) return false;
    // فقط حاوية خطأ Google الرسمية — لا تعتمد على نص «تحميل» وغيره (كانت تحوّل OSM بالخطأ)
    return !!mapEl.querySelector('.gm-err-container, .gm-err-title, .gm-err-message');
  }

  function fallbackFromGoogleError() {
    if (state.provider !== 'google') return;
    var mapEl = state.opts && $(state.opts.mapEl);
    if (!mapHasGoogleError(mapEl)) return;
    global.__gmapsAuthFailed = true;
    var coords = state.opts && $(state.opts.coordsEl);
    if (coords) {
      coords.textContent = 'تعذّر تحميل Google Maps — تحقق من قيود المفتاح (HTTP referrers) لـ jama.liftcoreapp.com';
      coords.style.color = 'var(--warning)';
    }
    var opts = state.opts;
    hardReset();
    if (opts) init(opts);
  }

  function scheduleGoogleErrorCheck() {
    // فحص متأخر فقط لحاوية الخطأ الرسمية — بعد اكتمال التحميل
    [2000, 4000].forEach(function (ms) {
      setTimeout(fallbackFromGoogleError, ms);
    });
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

    // إن وُجد مفتاح Google: لا تسقط على OSM بمجرد أن المكتبة لم تجهز بعد
    if (preferLeaflet()) {
      if (!ensureLeafletMap()) return false;
      updateCoordsLabel(null);
      return true;
    }
    if (!mapsReady()) {
      var coordsWait = $(state.opts.coordsEl);
      if (coordsWait) {
        coordsWait.textContent = 'جاري تحميل خرائط Google...';
        coordsWait.style.color = '';
      }
      return false;
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
      else if (global.LiftCoreMap && LiftCoreMap.setMarkerMap) LiftCoreMap.setMarkerMap(state.marker, null);
      else if (state.marker.setMap) state.marker.setMap(null);
      state.marker = null;
    }
    state.hasPoint = false;
    var search = state.opts && $(state.opts.searchEl);
    if (search) setSearchValue('');
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
    var opts = state.opts;
    teardownGoogleSearch();
    clearMapContainer();
    if (opts) {
      var input = $(opts.searchEl);
      if (input) {
        delete input.dataset.lcEnterBound;
        delete input.dataset.lcPacFocus;
        input.style.display = '';
      }
      var searchBtn = $(opts.searchBtnEl);
      if (searchBtn) delete searchBtn.dataset.bound;
    }
    state.provider = null;
    state.map = null;
    state.marker = null;
    state.geocoder = null;
    state.autocomplete = null;
    state.placeAutocompleteEl = null;
    state.placeSelectListener = null;
    state.autocompleteWrap = null;
    state.boundsListener = null;
    state.initialized = false;
    state.hasPoint = false;
    state.searchBound = false;
    state.autocompleteSuspended = false;
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
    var search = state.opts && $(state.opts.searchEl);
    if (search && (options.formatted_address || options.address)) {
      setSearchQueryWithoutPac(search, options.formatted_address || options.address || '');
    }
    setMarkerPosition(la, ln, { skipReverseGeocode: !!options.skipReverseGeocode });
    if (options.address || options.city || options.district || options.skipReverseGeocode) {
      emitUpdate({
        lat: String(la),
        lng: String(ln),
        address: options.address || '',
        city: options.city || '',
        district: options.district || '',
        maps_url: options.maps_url || buildMapsUrl(la, ln),
        formatted_address: options.formatted_address || options.address || '',
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
      var gp = null;
      if (global.LiftCoreMap && LiftCoreMap.getMarkerPosition) {
        gp = LiftCoreMap.getMarkerPosition(state.marker);
      } else if (state.marker.getPosition) {
        var raw = state.marker.getPosition();
        if (raw) gp = { lat: raw.lat(), lng: raw.lng() };
      }
      if (gp) state.map.setCenter(gp);
    } else state.map.setCenter(center);
  }

  function hasLocation() {
    return state.hasPoint;
  }

  function geocodeAddress(query, callback, options) {
    options = options || {};
    if (!query) return;
    if (!state.map && !init(state.opts || global.LiftCoreMapPicker._lastOpts || {})) {
      if (callback) callback(false);
      return;
    }
    if (state.provider === 'leaflet' || preferLeaflet()) {
      geocodeAddressOsm(query, callback);
      return;
    }
    var g = getGeocoder();
    if (!g) {
      geocodeAddressOsm(query, callback);
      return;
    }
    g.geocode({ address: query, componentRestrictions: { country: 'SA' }, region: 'SA' }, function (results, status) {
      if (status === 'OK' && results && results[0]) {
        var r = results[0];
        var loc = r.geometry.location;
        var lat = loc.lat();
        var lng = loc.lng();
        if (state.map) {
          if (r.geometry.viewport) state.map.fitBounds(r.geometry.viewport);
          else {
            state.map.setCenter({ lat: lat, lng: lng });
            if (state.map.getZoom() < 15) state.map.setZoom(16);
          }
        }
        setMarkerPosition(lat, lng, { pan: false, skipReverseGeocode: true });
        applyGeocodeResult({
          address_components: r.address_components,
          formatted_address: r.formatted_address,
          url: r.url,
        }, lat, lng);
        if (options.skipReverseGeocode && options.clientUpdate) {
          emitUpdate(Object.assign({}, options.clientUpdate, {
            lat: String(lat),
            lng: String(lng),
            maps_url: options.clientUpdate.maps_url || buildMapsUrl(lat, lng),
          }));
        }
        if (callback) callback(true);
        return;
      }
      geocodeAddressOsm(query, callback);
    });
  }

  global.LiftCoreMapPicker = {
    init: init,
    reset: reset,
    hardReset: hardReset,
    setLocation: setLocation,
    dismissPlacesAutocomplete: dismissPlacesAutocomplete,
    suspendPlacesAutocomplete: suspendPlacesAutocomplete,
    resize: resize,
    hasLocation: hasLocation,
    refreshMarkerIcon: refreshMarkerIcon,
    geocodeAddress: geocodeAddress,
    runMapSearch: runMapSearch,
    setSearchQuery: setSearchQuery,
    getSearchQuery: getSearchQuery,
    _lastOpts: null,
  };
})(typeof window !== 'undefined' ? window : this);
