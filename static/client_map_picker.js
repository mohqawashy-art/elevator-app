/* LiftCore — تحديد موقع العميل من الخريطة (بحث + نقرة + سحب) */
(function (global) {
  'use strict';

  var state = {
    map: null,
    marker: null,
    geocoder: null,
    autocomplete: null,
    opts: null,
    initialized: false,
    hasPoint: false,
  };

  var DEFAULT_CENTER = { lat: 21.4225, lng: 39.8262 };
  var POI_STYLES = [
    { featureType: 'poi', stylers: [{ visibility: 'off' }] },
    { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
  ];

  function $(id) {
    return typeof id === 'string' ? document.getElementById(id) : id;
  }

  function mapsReady() {
    return !!(global.google && google.maps);
  }

  function getGeocoder() {
    if (!mapsReady()) return null;
    if (!state.geocoder) state.geocoder = new google.maps.Geocoder();
    return state.geocoder;
  }

  function defaultPinIcon(color) {
    color = color || '#1fb87a';
    if (typeof global.makePinIcon === 'function') {
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
    if (state.marker) state.marker.setIcon(defaultPinIcon(pinColor()));
  }

  function parseAddressComponents(components) {
    var out = { address: '', city: '', district: '' };
    var route = '';
    var streetNumber = '';
    var parts = components || [];

    parts.forEach(function (c) {
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

    if (route) {
      out.address = (streetNumber ? streetNumber + ' ' : '') + route;
    }
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
      el.textContent = 'لم يُحدَّد موقع بعد — اضغط على الخريطة أو ابحث أعلاه';
      el.classList.remove('set');
      return;
    }
    el.textContent = 'GPS: ' + Number(payload.lat).toFixed(6) + ', ' + Number(payload.lng).toFixed(6);
    el.classList.add('set');
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

  function reverseGeocode(lat, lng) {
    var g = getGeocoder();
    if (!g) return;
    g.geocode({ location: { lat: lat, lng: lng } }, function (results, status) {
      if (status === 'OK' && results && results[0]) {
        applyGeocodeResult(results[0], lat, lng);
      } else {
        emitUpdate({
          lat: String(lat),
          lng: String(lng),
          address: '',
          city: '',
          district: '',
          maps_url: buildMapsUrl(lat, lng),
        });
      }
    });
  }

  function setMarkerPosition(lat, lng, pan) {
    if (!state.map) return;
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
    if (place.geometry.viewport) {
      state.map.fitBounds(place.geometry.viewport);
    } else {
      state.map.setCenter({ lat: lat, lng: lng });
      state.map.setZoom(17);
    }
    setMarkerPosition(lat, lng, false);
    if (place.address_components) {
      applyGeocodeResult(
        {
          address_components: place.address_components,
          formatted_address: place.formatted_address,
          url: place.url,
        },
        lat,
        lng
      );
    }
  }

  function bindMyLocation() {
    var btn = state.opts && $(state.opts.myLocEl);
    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = '1';
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
          btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="14" height="14"><path d="M12 21s7-4.5 7-11a7 7 0 10-14 0c0 6.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg> موقعي';
          setMarkerPosition(pos.coords.latitude, pos.coords.longitude);
        },
        function () {
          btn.disabled = false;
          btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="14" height="14"><path d="M12 21s7-4.5 7-11a7 7 0 10-14 0c0 6.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg> موقعي';
          alert('تعذّر الحصول على موقعك — تحقق من صلاحيات الموقع');
        },
        { enableHighAccuracy: true, timeout: 12000 }
      );
    });
  }

  function bindSearch() {
    var input = state.opts && $(state.opts.searchEl);
    if (!input || !google.maps.places) return;
    if (state.autocomplete) {
      google.maps.event.clearInstanceListeners(state.autocomplete);
    }
    state.autocomplete = new google.maps.places.Autocomplete(input, {
      componentRestrictions: { country: 'sa' },
      fields: ['address_components', 'formatted_address', 'geometry', 'name', 'url'],
    });
    state.autocomplete.bindTo('bounds', state.map);
    state.autocomplete.addListener('place_changed', onPlaceSelected);
  }

  function ensureMap() {
    var mapEl = state.opts && $(state.opts.mapEl);
    if (!mapEl || !mapsReady()) return false;

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
      bindSearch();
      bindMyLocation();
      state.initialized = true;
    }
    return true;
  }

  function init(options) {
    if (state.map && state.opts && options && state.opts.mapEl !== options.mapEl) {
      hardReset();
    }
    state.opts = options || {};
    state.hasPoint = false;
    if (!ensureMap()) return false;
    updateCoordsLabel(null);
    return true;
  }

  function reset() {
    if (state.marker) {
      state.marker.setMap(null);
      state.marker = null;
    }
    state.hasPoint = false;
    var search = state.opts && $(state.opts.searchEl);
    if (search) search.value = '';
    if (state.map) {
      var center = (state.opts && state.opts.defaultCenter) || DEFAULT_CENTER;
      state.map.setCenter(center);
      state.map.setZoom(12);
    }
    updateCoordsLabel(null);
  }

  function hardReset() {
    state.map = null;
    state.marker = null;
    state.geocoder = null;
    state.autocomplete = null;
    state.initialized = false;
    state.hasPoint = false;
    state.opts = null;
  }

  function setLocation(lat, lng, options) {
    options = options || {};
    if (!ensureMap()) return false;
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
    if (state.map && google.maps) {
      google.maps.event.trigger(state.map, 'resize');
      if (state.marker) {
        var p = state.marker.getPosition();
        if (p) state.map.setCenter(p);
      }
    }
  }

  function hasLocation() {
    return state.hasPoint;
  }

  function geocodeAddress(query, callback) {
    var g = getGeocoder();
    if (!g || !query) return;
    g.geocode({ address: query, region: 'SA' }, function (results, status) {
      if (status === 'OK' && results && results[0]) {
        var loc = results[0].geometry.location;
        setMarkerPosition(loc.lat(), loc.lng());
        if (callback) callback(true);
      } else if (callback) {
        callback(false);
      }
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
  };
})(typeof window !== 'undefined' ? window : this);
