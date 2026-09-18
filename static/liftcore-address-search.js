/**
 * بحث عنوان (Google Places أو Nominatim كاحتياط) لحقول الموقع.
 */
(function (global) {
  'use strict';

  function $(id) {
    return typeof id === 'string' ? document.getElementById(id) : id;
  }

  function parseGoogleComponents(components) {
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

  function applyParts(opts, parts, formatted, extra) {
    var addressEl = $(opts.addressEl);
    var cityEl = $(opts.cityEl);
    var districtEl = $(opts.districtEl);
    var text = formatted || parts.address || '';
    if (addressEl && text) addressEl.value = text;
    if (cityEl && parts.city) cityEl.value = parts.city;
    if (districtEl && parts.district) districtEl.value = parts.district;
    if (typeof opts.onPicked === 'function') opts.onPicked(parts, formatted, extra || {});
  }

  function ensureSuggestBox(input) {
    var wrap = input.parentElement;
    if (!wrap) return null;
    if (getComputedStyle(wrap).position === 'static') wrap.style.position = 'relative';
    var box = wrap.querySelector('.lc-addr-suggest');
    if (box) return box;
    box = document.createElement('div');
    box.className = 'lc-addr-suggest';
    wrap.appendChild(box);
    return box;
  }

  function hideSuggest(box) {
    if (!box) return;
    box.innerHTML = '';
    box.style.display = 'none';
  }

  function bindNominatim(input, opts) {
    if (input.dataset.lcAddrNom) return;
    input.dataset.lcAddrNom = '1';
    var box = ensureSuggestBox(input);
    var timer = null;
    function search(q) {
      if (!q || q.length < 3) { hideSuggest(box); return; }
      var url = 'https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=6&countrycodes=sa&accept-language=ar&q='
        + encodeURIComponent(q);
      fetch(url, { headers: { Accept: 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (rows) {
          if (!Array.isArray(rows) || !rows.length) { hideSuggest(box); return; }
          box.innerHTML = '';
          rows.forEach(function (row) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = row.display_name || '';
            btn.addEventListener('mousedown', function (e) {
              e.preventDefault();
              var a = row.address || {};
              applyParts(opts, {
                city: a.city || a.town || a.village || a.state || '',
                district: a.suburb || a.neighbourhood || a.quarter || '',
                address: row.display_name || '',
              }, row.display_name || '', {
                lat: parseFloat(row.lat),
                lng: parseFloat(row.lon),
              });
              hideSuggest(box);
            });
            box.appendChild(btn);
          });
          box.style.display = 'block';
        })
        .catch(function () { hideSuggest(box); });
    }
    input.addEventListener('input', function () {
      clearTimeout(timer);
      var q = (input.value || '').trim();
      timer = setTimeout(function () { search(q); }, 380);
    });
    input.addEventListener('blur', function () {
      setTimeout(function () { hideSuggest(box); }, 180);
    });
  }

  function bindGoogle(input, opts) {
    if (input.dataset.lcAddrGmaps) return;
    if (!global.google || !google.maps || !google.maps.places || !google.maps.places.Autocomplete) {
      bindNominatim(input, opts);
      return;
    }
    input.dataset.lcAddrGmaps = '1';
    var ac = new google.maps.places.Autocomplete(input, {
      componentRestrictions: { country: 'sa' },
      fields: ['address_components', 'formatted_address', 'geometry', 'name'],
    });
    ac.addListener('place_changed', function () {
      var place = ac.getPlace() || {};
      var parts = parseGoogleComponents(place.address_components || []);
      var formatted = place.formatted_address || place.name || parts.address || '';
      var extra = {};
      if (place.geometry && place.geometry.location) {
        extra.lat = place.geometry.location.lat();
        extra.lng = place.geometry.location.lng();
      }
      applyParts(opts, parts, formatted, extra);
    });
  }

  function bind(inputOrId, opts) {
    var input = $(inputOrId);
    opts = opts || {};
    if (!input || input.dataset.lcAddrBound) return;
    input.dataset.lcAddrBound = '1';
    if (!opts.addressEl) opts.addressEl = input;
    if (!input.getAttribute('placeholder')) {
      input.setAttribute('placeholder', 'ابحث في خرائط جوجل…');
    }
    input.setAttribute('autocomplete', 'off');
    function start() {
      if (typeof global.liftcoreGoogleMapsUsable === 'function' && global.liftcoreGoogleMapsUsable()
          && global.google && google.maps && google.maps.places) {
        bindGoogle(input, opts);
        return;
      }
      bindNominatim(input, opts);
    }
    if (typeof global.whenGoogleMapsReady === 'function') {
      global.whenGoogleMapsReady(start);
    } else {
      start();
    }
  }

  global.LiftCoreAddressSearch = { bind: bind };
})(window);
