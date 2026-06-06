/* LiftCore — تحديد مواقع العملاء (متصفح ثم خادم) */
(function (global) {
  'use strict';

  var cache = {};
  var failed = {};
  var geocoder = null;
  var batchRunning = false;

  function getGeocoder() {
    if (!global.google || !google.maps || !google.maps.Geocoder) return null;
    if (!geocoder) geocoder = new google.maps.Geocoder();
    return geocoder;
  }

  function buildQuery(c) {
    if (c.address) return c.address;
    var parts = [];
    if (c.district) parts.push(c.district);
    if (c.city) parts.push(c.city);
    parts.push('Saudi Arabia');
    return parts.join(', ');
  }

  function hasGps(c) {
    if (global.LiftCoreLocation && LiftCoreLocation.parseCoords) {
      return !!LiftCoreLocation.parseCoords(c.lat, c.lng);
    }
    var lat = parseFloat(c.lat);
    var lng = parseFloat(c.lng);
    return !isNaN(lat) && !isNaN(lng);
  }

  function saveToServer(c, pos, mapsUrl) {
    c.lat = String(pos.lat);
    c.lng = String(pos.lng);
    if (mapsUrl) c.maps_url = mapsUrl;
    fetch('/api/customers/' + c.id + '/location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lat: pos.lat,
        lng: pos.lng,
        maps_url: c.maps_url || ''
      })
    }).catch(function () {});
  }

  function geocodeViaServer(c) {
    return fetch('/api/customers/' + c.id + '/geocode', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.ok) return null;
        var lat = parseFloat(data.lat);
        var lng = parseFloat(data.lng);
        if (isNaN(lat) || isNaN(lng)) return null;
        var pos = { lat: lat, lng: lng, exact: false };
        cache[c.id] = pos;
        c.lat = data.lat;
        c.lng = data.lng;
        if (data.maps_url) c.maps_url = data.maps_url;
        return pos;
      })
      .catch(function () { return null; });
  }

  function geocodeOne(c) {
    if (hasGps(c)) {
      var parsed = global.LiftCoreLocation && LiftCoreLocation.parseCoords
        ? LiftCoreLocation.parseCoords(c.lat, c.lng)
        : { lat: parseFloat(c.lat), lng: parseFloat(c.lng) };
      if (parsed) {
        c.lat = String(parsed.lat);
        c.lng = String(parsed.lng);
        return Promise.resolve({ lat: parsed.lat, lng: parsed.lng, exact: true });
      }
    }
    if (cache[c.id]) return Promise.resolve(cache[c.id]);
    if (failed[c.id]) return Promise.resolve(null);

    var g = getGeocoder();
    var query = buildQuery(c);
    if (!query || query === 'Saudi Arabia') {
      return geocodeViaServer(c).then(function (pos) {
        if (!pos) failed[c.id] = true;
        return pos;
      });
    }

    if (!g) {
      return geocodeViaServer(c).then(function (pos) {
        if (!pos) failed[c.id] = true;
        return pos;
      });
    }

    return new Promise(function (resolve) {
      g.geocode({ address: query, region: 'SA' }, function (results, status) {
        if (status === 'OK' && results && results[0]) {
          var loc = results[0].geometry.location;
          var pos = { lat: loc.lat(), lng: loc.lng(), exact: true };
          cache[c.id] = pos;
          saveToServer(c, pos, results[0].url);
          resolve(pos);
          return;
        }
        geocodeViaServer(c).then(function (pos) {
          if (!pos) failed[c.id] = true;
          resolve(pos);
        });
      });
    });
  }

  function geocodeAll(customers, onProgress) {
    if (batchRunning) return Promise.resolve();
    customers = customers || [];
    var missing = customers.filter(function (c) {
      return !hasGps(c) && !failed[c.id];
    });
    if (!missing.length) return Promise.resolve();

    batchRunning = true;
    var done = 0;
    var total = missing.length;

    function next(i) {
      if (i >= missing.length) {
        batchRunning = false;
        return Promise.resolve();
      }
      return geocodeOne(missing[i]).then(function () {
        done++;
        if (onProgress) onProgress(done, total);
        return new Promise(function (r) {
          setTimeout(function () { r(next(i + 1)); }, 200);
        });
      });
    }
    return next(0);
  }

  global.LiftCoreGeocode = {
    hasGps: hasGps,
    geocodeOne: geocodeOne,
    geocodeAll: geocodeAll
  };
})(typeof window !== 'undefined' ? window : this);
