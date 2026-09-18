/**
 * خريطة عملاء الحي/المنطقة بجانب عرض سعر الصيانة.
 */
(function (global) {
  'use strict';

  var DEFAULT_CENTER = { lat: 21.4225, lng: 39.8262 };
  var DEFAULT_CITY = 'مكة المكرمة';
  var map = null;
  var provider = null;
  var markers = [];
  var focusMarker = null;
  var googleInfo = null;
  var ready = false;
  var refreshTimer = null;

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch];
    });
  }

  function num(v) {
    var n = parseFloat(v);
    return isFinite(n) ? n : null;
  }

  function norm(s) {
    return String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  }

  function areaMatch(hay, needle) {
    if (!needle) return true;
    if (!hay) return false;
    return hay === needle || hay.indexOf(needle) >= 0 || needle.indexOf(hay) >= 0;
  }

  function currentArea() {
    var sel = $('customer_id');
    var cityEl = $('city');
    var distEl = $('district');
    var addrEl = $('address');
    return {
      city: ((cityEl && cityEl.value) || '').trim(),
      district: ((distEl && distEl.value) || '').trim(),
      address: ((addrEl && addrEl.value) || '').trim(),
      selectedId: sel && sel.value ? String(sel.value) : '',
    };
  }

  function isAreaSearch(area) {
    if (area.district) return true;
    if (area.address) return true;
    if (area.city && norm(area.city) !== norm(DEFAULT_CITY)) return true;
    return false;
  }

  function placeFields(c) {
    var out = [c.city, c.district, c.address];
    (c.sites || []).forEach(function (s) {
      out.push(s.city, s.district);
    });
    return out.map(norm).filter(Boolean);
  }

  function inArea(c, area) {
    var fields = placeFields(c);
    var distN = norm(area.district);
    var cityN = norm(area.city);
    var addrN = norm(area.address);
    function hit(needle) {
      if (!needle) return false;
      return fields.some(function (f) { return areaMatch(f, needle); });
    }
    if (distN) return hit(distN);
    if (addrN && addrN.length >= 4) {
      if (hit(addrN) || areaMatch(fields.join(' '), addrN)) return true;
      if (cityN) return hit(cityN);
      return false;
    }
    if (cityN && cityN !== norm(DEFAULT_CITY)) return hit(cityN);
    return true;
  }

  function customers() {
    return Array.isArray(global.MQ_NEARBY_CUSTOMERS) ? global.MQ_NEARBY_CUSTOMERS : [];
  }

  function matching(area) {
    var all = customers();
    if (!isAreaSearch(area)) return all;
    return all.filter(function (c) {
      return !!c.has_contract && inArea(c, area);
    });
  }

  function coordsOf(c) {
    var lat = num(c.lat);
    var lng = num(c.lng);
    if (lat == null || lng == null) return null;
    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
    return { lat: lat, lng: lng };
  }

  function googleOk() {
    return typeof global.liftcoreGoogleMapsUsable === 'function'
      && global.liftcoreGoogleMapsUsable()
      && global.google && google.maps;
  }

  function clearMarkers() {
    markers.forEach(function (m) {
      try {
        if (provider === 'google') m.setMap(null);
        else if (map && map.removeLayer) map.removeLayer(m);
      } catch (e) { /* ignore */ }
    });
    markers = [];
    if (focusMarker) {
      try {
        if (provider === 'google') focusMarker.setMap(null);
        else if (map && map.removeLayer) map.removeLayer(focusMarker);
      } catch (e) { /* ignore */ }
      focusMarker = null;
    }
  }

  function pinColor(c, area) {
    if (area.selectedId && String(c.id) === area.selectedId) return '#c8a055';
    if ((c.status || '') === 'غير نشط') return '#e04848';
    if (c.has_contract) return '#1fb87a';
    return '#8a9bb8';
  }

  function popupHtml(c) {
    var loc = [c.district, c.city].filter(Boolean).join(' · ');
    var st = c.has_contract ? (c.contract_status || 'متعاقد') : 'بدون عقد';
    return '<div class="mq-map-pop"><b>' + esc(c.name) + '</b>'
      + (c.code ? '<div>' + esc(c.code) + '</div>' : '')
      + '<div>' + esc(st) + '</div>'
      + (loc ? '<div>' + esc(loc) + '</div>' : '')
      + (c.address ? '<div>' + esc(c.address) + '</div>' : '')
      + '</div>';
  }

  function addGoogleMarker(c, pos, color) {
    var icon = (global.LiftCoreMap && LiftCoreMap.makePinIcon)
      ? LiftCoreMap.makePinIcon(color, color === '#c8a055' ? 1.45 : 1.15)
      : { path: google.maps.SymbolPath.CIRCLE, fillColor: color, fillOpacity: 1, strokeColor: '#fff', strokeWeight: 2, scale: 8 };
    var marker = new google.maps.Marker({
      map: map,
      position: pos,
      title: c.name || '',
      icon: icon,
    });
    marker.addListener('click', function () {
      if (!googleInfo) googleInfo = new google.maps.InfoWindow();
      googleInfo.setContent(popupHtml(c));
      googleInfo.open(map, marker);
      pickCustomer(c.id);
    });
    markers.push(marker);
  }

  function addLeafletMarker(c, pos, color) {
    var marker = L.circleMarker([pos.lat, pos.lng], {
      radius: color === '#c8a055' ? 10 : 8,
      color: '#fff',
      weight: 2,
      fillColor: color,
      fillOpacity: 1,
    }).addTo(map);
    marker.bindPopup(popupHtml(c));
    marker.on('click', function () { pickCustomer(c.id); });
    markers.push(marker);
  }

  function pickCustomer(id) {
    var sel = $('customer_id');
    if (!sel || !id) return;
    var value = String(id);
    if (!sel.querySelector('option[value="' + value.replace(/"/g, '') + '"]')) return;
    if (sel.value === value) return;
    sel.value = value;
    sel.dispatchEvent(new Event('change'));
  }

  function fitPoints(points) {
    if (!points.length || !map) return;
    if (provider === 'google') {
      if (points.length === 1) {
        map.setCenter(points[0]);
        map.setZoom(15);
        return;
      }
      var b = new google.maps.LatLngBounds();
      points.forEach(function (p) { b.extend(p); });
      map.fitBounds(b, 48);
      return;
    }
    var latlngs = points.map(function (p) { return [p.lat, p.lng]; });
    if (latlngs.length === 1) map.setView(latlngs[0], 15);
    else map.fitBounds(latlngs, { padding: [28, 28] });
  }

  function setFocus(lat, lng) {
    var pos = { lat: num(lat), lng: num(lng) };
    if (pos.lat == null || pos.lng == null || !map) return;
    if (focusMarker) {
      try {
        if (provider === 'google') focusMarker.setMap(null);
        else if (map.removeLayer) map.removeLayer(focusMarker);
      } catch (e) { /* ignore */ }
      focusMarker = null;
    }
    if (provider === 'google') {
      focusMarker = new google.maps.Marker({
        map: map,
        position: pos,
        title: 'موقع العرض',
        zIndex: 999,
        icon: (global.LiftCoreMap && LiftCoreMap.makePinIcon)
          ? LiftCoreMap.makePinIcon('#2a7fff', 1.5)
          : undefined,
      });
      map.panTo(pos);
      if (map.getZoom() < 14) map.setZoom(15);
    } else if (window.L) {
      focusMarker = L.marker([pos.lat, pos.lng]).addTo(map);
      map.setView([pos.lat, pos.lng], Math.max(map.getZoom() || 13, 15));
    }
  }

  function renderList(rows, area) {
    var box = $('mq-nearby-list');
    var meta = $('mq-nearby-meta');
    var searching = isAreaSearch(area);
    if (meta) {
      if (!searching) {
        meta.textContent = 'جميع العملاء على الخريطة (' + rows.length + ') — الأخضر متعاقد';
      } else {
        var label = area.district || area.city || 'المنطقة';
        if (!rows.length) meta.textContent = 'لا يوجد عملاء متعاقد معهم في «' + label + '»';
        else meta.textContent = rows.length + ' عميل متعاقد في «' + label + '»';
      }
    }
    if (!box) return;
    if (!searching) {
      box.innerHTML = '';
      return;
    }
    if (!rows.length) {
      box.innerHTML = '';
      return;
    }
    box.innerHTML = rows.slice(0, 16).map(function (c) {
      var loc = [c.district, c.city].filter(Boolean).join(' · ');
      var on = area.selectedId && String(c.id) === area.selectedId ? ' on' : '';
      return '<button type="button" class="mq-near-item' + on + '" data-id="' + esc(c.id) + '">'
        + '<span>' + esc(c.name) + (c.code ? ' <small>' + esc(c.code) + '</small>' : '') + '</span>'
        + '<small>' + esc(c.contract_status || 'متعاقد') + (loc ? ' · ' + esc(loc) : '') + '</small>'
        + '</button>';
    }).join('');
    box.querySelectorAll('.mq-near-item').forEach(function (btn) {
      btn.addEventListener('click', function () { pickCustomer(btn.getAttribute('data-id')); });
    });
  }

  function refresh() {
    if (!ready || !map) return;
    var area = currentArea();
    var rows = matching(area);
    renderList(rows, area);
    clearMarkers();
    var points = [];
    rows.forEach(function (c) {
      var pos = coordsOf(c);
      if (!pos) return;
      points.push(pos);
      if (provider === 'google') addGoogleMarker(c, pos, pinColor(c, area));
      else addLeafletMarker(c, pos, pinColor(c, area));
    });
    if (points.length) fitPoints(points);
  }

  function scheduleRefresh() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refresh, 180);
  }

  function initMap() {
    var el = $('mq-nearby-map');
    if (!el || map) return;
    if (googleOk()) {
      provider = 'google';
      map = new google.maps.Map(el, {
        center: DEFAULT_CENTER,
        zoom: 12,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        gestureHandling: 'greedy',
      });
    } else if (global.L) {
      provider = 'leaflet';
      map = L.map(el, { scrollWheelZoom: true }).setView([DEFAULT_CENTER.lat, DEFAULT_CENTER.lng], 12);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap',
      }).addTo(map);
    } else {
      el.textContent = 'تعذّر تحميل الخريطة';
      return;
    }
    ready = true;
    setTimeout(function () {
      try {
        if (provider === 'google' && google.maps.event) google.maps.event.trigger(map, 'resize');
        if (provider === 'leaflet' && map.invalidateSize) map.invalidateSize();
      } catch (e) { /* ignore */ }
      refresh();
    }, 80);
  }

  function bind() {
    ['city', 'district', 'address', 'customer_id'].forEach(function (id) {
      var el = $(id);
      if (!el || el.dataset.mqNearBound) return;
      el.dataset.mqNearBound = '1';
      el.addEventListener('change', scheduleRefresh);
      el.addEventListener('input', scheduleRefresh);
    });
  }

  function start() {
    bind();
    initMap();
  }

  function upsertCustomer(cust) {
    if (!cust || !cust.id) return;
    var list = customers();
    var i = list.findIndex(function (c) { return String(c.id) === String(cust.id); });
    var row = {
      id: cust.id,
      code: cust.code || '',
      name: cust.name || '',
      city: cust.city || '',
      district: cust.district || '',
      address: cust.address || '',
      lat: cust.lat || '',
      lng: cust.lng || '',
      status: cust.status || 'نشط',
      has_contract: !!cust.has_contract,
      contract_status: cust.contract_status || 'بدون عقد',
      sites: cust.sites || [],
    };
    if (i >= 0) list[i] = row;
    else list.push(row);
    global.MQ_NEARBY_CUSTOMERS = list;
    scheduleRefresh();
  }

  global.LiftCoreNearbyQuoteMap = {
    refresh: scheduleRefresh,
    setFocus: setFocus,
    upsertCustomer: upsertCustomer,
  };

  if (typeof global.whenGoogleMapsReady === 'function') global.whenGoogleMapsReady(start);
  else if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})(window);
