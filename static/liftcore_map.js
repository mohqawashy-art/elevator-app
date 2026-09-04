/**
 * LiftCore — خرائط العملاء/العقود (أسلوب SuiteSmart)
 * أقمار صناعية + دبابيس خضراء + تجميع بعدد عند التصغير
 */
(function (global) {
  'use strict';

  var DEFAULT_CENTER = { lat: 21.4225, lng: 39.8262 };
  var DEFAULT_ZOOM = 12;
  /* لا نستخدم DEMO_MAP_ID افتراضياً — يفرض خرائط Vector وقد يعطل الخرائط بدون فوترة/Map ID صالح */

  var POI_HIDDEN = [
    { featureType: 'poi', stylers: [{ visibility: 'off' }] },
    { featureType: 'transit', stylers: [{ visibility: 'off' }] }
  ];

  var PIN_PATH = 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z';
  var markerLib = null;

  function _setMarkerLib(lib) {
    markerLib = lib || null;
  }

  function getMarkerClasses() {
    if (markerLib) return markerLib;
    if (global.__gmapsMarkerLib) return global.__gmapsMarkerLib;
    if (global.google && global.google.maps && global.google.maps.marker) {
      return global.google.maps.marker;
    }
    return null;
  }

  function getMapId() {
    var id = (global.LIFTCORE_GOOGLE_MAP_ID || '').trim();
    return id || null;
  }

  function canUseAdvancedMarkers() {
    if (!getMapId()) return false;
    var mc = getMarkerClasses();
    return !!(mc && mc.AdvancedMarkerElement);
  }

  function isAdvancedMarker(marker) {
    if (!marker || !canUseAdvancedMarkers()) return false;
    var AdvancedMarkerElement = getMarkerClasses().AdvancedMarkerElement;
    return marker instanceof AdvancedMarkerElement;
  }

  function mergeMapOptions(options) {
    options = options || {};
    var merged = Object.assign({}, options);
    var mapId = merged.mapId || getMapId();
    if (mapId) merged.mapId = mapId;
    else delete merged.mapId;
    return merged;
  }

  function makePinIcon(color, scale) {
    return {
      path: PIN_PATH,
      fillColor: color || '#1fb87a',
      fillOpacity: 1,
      strokeColor: '#ffffff',
      strokeWeight: 2,
      scale: scale || 1.35,
      anchor: new global.google.maps.Point(12, 22)
    };
  }

  function makePinContent(color, scale) {
    var mc = getMarkerClasses();
    if (mc && mc.PinElement) {
      var pin = new mc.PinElement({
        background: color || '#1fb87a',
        borderColor: '#ffffff',
        glyphColor: '#ffffff',
        scale: scale || 1.2
      });
      return pin.element;
    }
    return null;
  }

  function makeClusterIcon(count) {
    var n = Math.max(1, parseInt(count, 10) || 1);
    var size = Math.min(58, 34 + Math.sqrt(n) * 5);
    var fontSize = n > 99 ? 11 : (n > 9 ? 13 : 14);
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '" viewBox="0 0 58 58">' +
      '<circle cx="29" cy="29" r="27" fill="rgba(42,127,255,0.12)"/>' +
      '<circle cx="29" cy="29" r="21" fill="rgba(42,127,255,0.22)"/>' +
      '<circle cx="29" cy="29" r="15" fill="#2a7fff" stroke="#ffffff" stroke-width="2.5"/>' +
      '<text x="29" y="34" text-anchor="middle" fill="#ffffff" font-size="' + fontSize + '" font-weight="700" font-family="DM Sans,Arial,sans-serif">' + n + '</text>' +
      '</svg>';
    return {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
      scaledSize: new global.google.maps.Size(size, size),
      anchor: new global.google.maps.Point(size / 2, size / 2)
    };
  }

  function clusterZIndex(count) {
    return 1000000 + count;
  }

  function requireMarkerClasses() {
    if (!canUseAdvancedMarkers()) return null;
    var mc = getMarkerClasses();
    if (!mc || !mc.AdvancedMarkerElement) {
      return null;
    }
    return mc;
  }

  function createClusterMarker(cluster, unitLabel) {
    var count = cluster.count;
    var title = count + ' ' + (unitLabel || 'موقع');
    var icon = makeClusterIcon(count);
    var mc = requireMarkerClasses();
    if (mc && mc.AdvancedMarkerElement) {
      var img = document.createElement('img');
      img.src = icon.url;
      img.width = icon.scaledSize.width;
      img.height = icon.scaledSize.height;
      img.alt = title;
      return new mc.AdvancedMarkerElement({
        position: cluster.position,
        title: title,
        content: img,
        zIndex: clusterZIndex(count)
      });
    }
    if (!global.google || !global.google.maps || !global.google.maps.Marker) return null;
    return new global.google.maps.Marker({
      position: cluster.position,
      title: title,
      icon: icon,
      zIndex: clusterZIndex(count)
    });
  }

  function createClusterRenderer(unitLabel) {
    unitLabel = unitLabel || 'موقع';
    return {
      render: function (cluster) {
        return createClusterMarker(cluster, unitLabel);
      }
    };
  }

  function createPinMarker(opts) {
    opts = opts || {};
    var position = opts.position;
    var color = opts.color || '#1fb87a';
    var scale = opts.scale || 1.2;
    var mc = requireMarkerClasses();
    if (mc && mc.AdvancedMarkerElement) {
      try {
        return new mc.AdvancedMarkerElement({
          map: opts.map || null,
          position: position,
          title: opts.title || '',
          content: makePinContent(color, scale),
          gmpDraggable: !!opts.draggable,
          zIndex: opts.zIndex
        });
      } catch (advErr) {
        console.warn('LiftCoreMap: AdvancedMarkerElement failed, using classic marker', advErr);
      }
    }
    if (!global.google || !global.google.maps || !global.google.maps.Marker) return null;
    return new global.google.maps.Marker({
      map: opts.map || null,
      position: position,
      title: opts.title || '',
      icon: opts.icon || makePinIcon(color, scale),
      draggable: !!opts.draggable,
      zIndex: opts.zIndex
    });
  }

  function setMarkerMap(marker, map) {
    if (!marker) return;
    if (isAdvancedMarker(marker)) marker.map = map || null;
    else marker.setMap(map || null);
  }

  function getMarkerPosition(marker) {
    if (!marker) return null;
    var p = marker.position;
    if (!p && marker.getPosition) p = marker.getPosition();
    if (!p) return null;
    if (typeof p.lat === 'function') return { lat: p.lat(), lng: p.lng() };
    return { lat: p.lat, lng: p.lng };
  }

  function setMarkerPosition(marker, position) {
    if (!marker || !position) return;
    if (isAdvancedMarker(marker)) marker.position = position;
    else marker.setPosition(position);
  }

  function refreshPinMarkerIcon(marker, color, scale) {
    if (!marker) return;
    color = color || '#1fb87a';
    scale = scale || 1.2;
    if (isAdvancedMarker(marker)) {
      marker.content = makePinContent(color, scale);
      return;
    }
    if (marker.setIcon) marker.setIcon(makePinIcon(color, scale));
  }

  function openInfoWindow(infoWindow, map, marker) {
    if (!infoWindow || !map || !marker) return;
    if (isAdvancedMarker(marker)) infoWindow.open({ map: map, anchor: marker });
    else infoWindow.open(map, marker);
  }

  function initMap(el, existingMap) {
    if (existingMap) return existingMap;
    if (!el || typeof global.google === 'undefined' || !global.google.maps) return null;
    return new global.google.maps.Map(el, mergeMapOptions({
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      mapTypeId: 'satellite',
      clickableIcons: false,
      streetViewControl: false,
      fullscreenControl: true,
      zoomControl: true,
      mapTypeControl: true,
      mapTypeControlOptions: {
        style: global.google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
        position: global.google.maps.ControlPosition.TOP_LEFT,
        mapTypeIds: ['satellite', 'hybrid', 'roadmap']
      },
      styles: POI_HIDDEN
    }));
  }

  function attachCluster(map, markers, unitLabel) {
    if (!markers.length) {
      return null;
    }
    if (typeof markerClusterer === 'undefined' || !markerClusterer.MarkerClusterer) {
      markers.forEach(function (m) { setMarkerMap(m, map); });
      return null;
    }
    return new markerClusterer.MarkerClusterer({
      map: map,
      markers: markers,
      renderer: createClusterRenderer(unitLabel),
      algorithm: new markerClusterer.SuperClusterAlgorithm({ radius: 90, maxZoom: 16 }),
      onClusterClick: function (_event, cluster, mapInstance) {
        mapInstance.fitBounds(cluster.bounds, 48);
      }
    });
  }

  function fitMapToMarkers(map, markers, fitAgain) {
    if (!map) return;
    global.google.maps.event.trigger(map, 'resize');
    if (!markers.length) {
      if (fitAgain) {
        map.setCenter(DEFAULT_CENTER);
        map.setZoom(DEFAULT_ZOOM);
      }
      return;
    }
    if (!fitAgain) return;
    var bounds = new global.google.maps.LatLngBounds();
    markers.forEach(function (m) {
      var pos = getMarkerPosition(m);
      if (pos) bounds.extend(pos);
    });
    map.fitBounds(bounds, 64);
    global.google.maps.event.addListenerOnce(map, 'bounds_changed', function () {
      if (map.getZoom() > 16) map.setZoom(16);
    });
  }

  function coordsForRecord(record) {
    if (!record) return null;
    if (global.LiftCoreLocation && global.LiftCoreLocation.hasCoordinates && global.LiftCoreLocation.parseCoords) {
      if (!global.LiftCoreLocation.hasCoordinates(record)) return null;
      var parsed = global.LiftCoreLocation.parseCoords(record.lat, record.lng);
      if (!parsed) return null;
      return { lat: parsed.lat, lng: parsed.lng, exact: true };
    }
    var lat = parseFloat(record.lat);
    var lng = parseFloat(record.lng);
    if (isNaN(lat) || isNaN(lng)) return null;
    return { lat: lat, lng: lng, exact: true };
  }

  function bindMarkerHover(marker, map, infoWindow, getContent, pinState) {
    pinState = pinState || { pinned: false, timer: null };
    marker.addListener('mouseover', function () {
      if (pinState.timer) clearTimeout(pinState.timer);
      infoWindow.setContent(getContent());
      openInfoWindow(infoWindow, map, marker);
    });
    marker.addListener('mouseout', function () {
      if (pinState.pinned) return;
      pinState.timer = setTimeout(function () { infoWindow.close(); }, 250);
    });
    marker.addListener('click', function () {
      if (pinState.timer) clearTimeout(pinState.timer);
      pinState.pinned = true;
      infoWindow.setContent(getContent());
      openInfoWindow(infoWindow, map, marker);
    });
    return pinState;
  }

  function geocodeMissing(customers, onProgress) {
    if (!global.LiftCoreGeocode || !customers.length) {
      return Promise.resolve();
    }
    return global.LiftCoreGeocode.geocodeAll(customers, onProgress);
  }

  function ensureMarkerLibReady(fn) {
    if (!fn) return Promise.resolve();
    if (!global.google || !global.google.maps || global.__gmapsAuthFailed) {
      fn();
      return Promise.resolve();
    }
    if (canUseAdvancedMarkers()) {
      fn();
      return Promise.resolve();
    }
    var loader;
    if (global.loadGmapsMarkerLib) {
      loader = global.loadGmapsMarkerLib();
    } else if (global.google.maps.importLibrary) {
      loader = global.google.maps.importLibrary('marker').then(function (lib) {
        _setMarkerLib(lib);
        global.__gmapsMarkerLib = lib;
        global.__gmapsMarkerReady = true;
        return lib;
      });
    } else {
      fn();
      return Promise.resolve();
    }
    return loader.then(function () {
      fn();
    }).catch(function (err) {
      console.error('LiftCoreMap: failed to load marker library', err);
      fn();
    });
  }

  var markerLibWaitAttempted = false;

  /** انتظر مكتبة العلامات مرة واحدة فقط عند وجود mapId — وإلا تعلّق/حلقة لا نهائية */
  function ensureMapMarkersReady(fn) {
    if (!fn) return Promise.resolve();
    if (!getMapId() || canUseAdvancedMarkers() || markerLibWaitAttempted) {
      fn();
      return Promise.resolve();
    }
    markerLibWaitAttempted = true;
    return ensureMarkerLibReady(fn);
  }

  if (global.__gmapsMarkerLib) {
    _setMarkerLib(global.__gmapsMarkerLib);
  }

  global.LiftCoreMap = {
    DEFAULT_CENTER: DEFAULT_CENTER,
    POI_HIDDEN: POI_HIDDEN,
    _setMarkerLib: _setMarkerLib,
    getMapId: getMapId,
    canUseAdvancedMarkers: canUseAdvancedMarkers,
    isAdvancedMarker: isAdvancedMarker,
    mergeMapOptions: mergeMapOptions,
    makePinIcon: makePinIcon,
    makePinContent: makePinContent,
    makeClusterIcon: makeClusterIcon,
    createClusterMarker: createClusterMarker,
    createClusterRenderer: createClusterRenderer,
    createPinMarker: createPinMarker,
    setMarkerMap: setMarkerMap,
    getMarkerPosition: getMarkerPosition,
    setMarkerPosition: setMarkerPosition,
    refreshPinMarkerIcon: refreshPinMarkerIcon,
    openInfoWindow: openInfoWindow,
    initMap: initMap,
    attachCluster: attachCluster,
    fitMapToMarkers: fitMapToMarkers,
    coordsForRecord: coordsForRecord,
    bindMarkerHover: bindMarkerHover,
    geocodeMissing: geocodeMissing,
    ensureMarkerLibReady: ensureMarkerLibReady,
    ensureMapMarkersReady: ensureMapMarkersReady
  };
})(typeof window !== 'undefined' ? window : this);
