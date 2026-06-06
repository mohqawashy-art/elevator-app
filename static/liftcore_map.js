/**
 * LiftCore — خرائط العملاء/العقود (أسلوب SuiteSmart)
 * أقمار صناعية + دبابيس خضراء + تجميع بعدد عند التصغير
 */
(function (global) {
  'use strict';

  var DEFAULT_CENTER = { lat: 21.4225, lng: 39.8262 };
  var DEFAULT_ZOOM = 12;

  var POI_HIDDEN = [
    { featureType: 'poi', stylers: [{ visibility: 'off' }] },
    { featureType: 'transit', stylers: [{ visibility: 'off' }] }
  ];

  var PIN_PATH = 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z';

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

  function createClusterRenderer(unitLabel) {
    unitLabel = unitLabel || 'موقع';
    return {
      render: function (cluster) {
        var count = cluster.count;
        return new global.google.maps.Marker({
          position: cluster.position,
          title: count + ' ' + unitLabel,
          icon: makeClusterIcon(count),
          zIndex: Number(global.google.maps.Marker.MAX_ZINDEX) + count
        });
      }
    };
  }

  function initMap(el, existingMap) {
    if (existingMap) return existingMap;
    if (!el || typeof global.google === 'undefined' || !global.google.maps) return null;
    return new global.google.maps.Map(el, {
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
    });
  }

  function attachCluster(map, markers, unitLabel) {
    if (!markers.length) {
      return null;
    }
    if (typeof markerClusterer === 'undefined' || !markerClusterer.MarkerClusterer) {
      markers.forEach(function (m) { m.setMap(map); });
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
      bounds.extend(m.getPosition());
    });
    map.fitBounds(bounds, 64);
    global.google.maps.event.addListenerOnce(map, 'bounds_changed', function () {
      if (map.getZoom() > 16) map.setZoom(16);
    });
  }

  function coordsForRecord(record) {
    if (!record) return null;
    if (global.LiftCoreLocation && global.LiftCoreLocation.coordsForCustomer) {
      return global.LiftCoreLocation.coordsForCustomer(record);
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
      infoWindow.open(map, marker);
    });
    marker.addListener('mouseout', function () {
      if (pinState.pinned) return;
      pinState.timer = setTimeout(function () { infoWindow.close(); }, 250);
    });
    marker.addListener('click', function () {
      if (pinState.timer) clearTimeout(pinState.timer);
      pinState.pinned = true;
      infoWindow.setContent(getContent());
      infoWindow.open(map, marker);
    });
    return pinState;
  }

  function geocodeMissing(customers, onProgress) {
    if (!global.LiftCoreGeocode || !customers.length) {
      return Promise.resolve();
    }
    return global.LiftCoreGeocode.geocodeAll(customers, onProgress);
  }

  global.LiftCoreMap = {
    DEFAULT_CENTER: DEFAULT_CENTER,
    POI_HIDDEN: POI_HIDDEN,
    makePinIcon: makePinIcon,
    makeClusterIcon: makeClusterIcon,
    createClusterRenderer: createClusterRenderer,
    initMap: initMap,
    attachCluster: attachCluster,
    fitMapToMarkers: fitMapToMarkers,
    coordsForRecord: coordsForRecord,
    bindMarkerHover: bindMarkerHover,
    geocodeMissing: geocodeMissing
  };
})(typeof window !== 'undefined' ? window : this);
