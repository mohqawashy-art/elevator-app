/** مشترك: تبويبات، خريطة، تقويم، فلاتر */
window.OpsPage = (function () {
  var mapInstance = null;
  var calMonth = new Date().getMonth();
  var calYear = new Date().getFullYear();
  var calItems = [];
  var calDateField = 'visit_date';

  function switchTab(name) {
    ['table', 'map', 'cal'].forEach(function (t) {
      var panel = document.getElementById('tab-' + t);
      var btn = document.getElementById('tab-btn-' + t);
      if (panel) panel.style.display = t === name ? '' : 'none';
      if (btn) btn.classList.toggle('active', t === name);
    });
    if (name === 'map') {
      setTimeout(function () {
        if (mapInstance) mapInstance.invalidateSize();
      }, 200);
    }
  }

  function statusColor(status) {
    var s = status || '';
    if (s.indexOf('مكتمل') >= 0 || s === 'محلول') return '#1fb87a';
    if (s.indexOf('متأخر') >= 0 || s === 'مفتوح') return '#e04848';
    if (s.indexOf('جاري') >= 0 || s.indexOf('قيد') >= 0) return '#e09030';
    if (s.indexOf('مُرسل') >= 0) return '#2a9fff';
    return '#2a7fff';
  }

  function initMap(containerId, points) {
    if (typeof L === 'undefined') return;
    var el = document.getElementById(containerId);
    if (!el) return;
    if (mapInstance) {
      mapInstance.remove();
      mapInstance = null;
    }
    mapInstance = L.map(el).setView([21.4225, 39.8262], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(mapInstance);
    var bounds = [];
    (points || []).forEach(function (p) {
      if (!p.lat || !p.lng) return;
      var color = statusColor(p.status || p.priority);
      var m = L.circleMarker([p.lat, p.lng], {
        radius: 8,
        color: color,
        fillColor: color,
        fillOpacity: 0.85,
        weight: 2,
      }).addTo(mapInstance);
      m.bindPopup('<b>' + (p.label || '') + '</b><br>' + (p.status || p.priority || ''));
      bounds.push([p.lat, p.lng]);
    });
    if (bounds.length) mapInstance.fitBounds(bounds, { padding: [30, 30] });
    else {
      L.marker([21.4225, 39.8262]).addTo(mapInstance)
        .bindPopup('لا توجد إحداثيات — أضف موقع العميل من صفحة العملاء')
        .openPopup();
    }
  }

  function fillFilterSelect(id, options, allLabel) {
    var sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = '<option value="">' + (allLabel || 'الكل') + '</option>' +
      options.map(function (o) {
        return '<option value="' + String(o.value).replace(/"/g, '&quot;') + '">' + o.label + '</option>';
      }).join('');
  }

  function initCalendar(gridId, titleId, items, dateField) {
    calItems = items || [];
    calDateField = dateField || 'visit_date';
    renderCalendar(gridId, titleId);
  }

  function setCalendarMonth(year, monthIndex) {
    calYear = year;
    calMonth = monthIndex;
  }

  function setCalendarItems(items) {
    calItems = items || [];
  }

  function refreshCalendar(gridId, titleId) {
    renderCalendar(gridId, titleId);
  }

  function renderCalendar(gridId, titleId) {
    var grid = document.getElementById(gridId);
    var title = document.getElementById(titleId);
    if (!grid) return;
    var months = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];
    if (title) {
      if (window.LiftCoreFormat) {
        title.innerHTML = window.LiftCoreFormat.monthLabel(calYear + '-' + String(calMonth + 1).padStart(2, '0'));
      } else {
        title.innerHTML = '<bdi dir="rtl">' + months[calMonth] + '</bdi> <bdi dir="ltr" class="lc-num">' + calYear + '</bdi>';
      }
    }
    var first = new Date(calYear, calMonth, 1);
    var daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    var startDay = first.getDay();
    var counts = {};
    calItems.forEach(function (it) {
      var d = (it[calDateField] || '').slice(0, 10);
      if (!d) return;
      var parts = d.split('-');
      if (parseInt(parts[0], 10) === calYear && parseInt(parts[1], 10) === calMonth + 1) {
        var day = parseInt(parts[2], 10);
        counts[day] = (counts[day] || 0) + 1;
      }
    });
    var html = '<div class="cal-day-name">ح</div><div class="cal-day-name">ن</div><div class="cal-day-name">ث</div><div class="cal-day-name">ر</div><div class="cal-day-name">خ</div><div class="cal-day-name">ج</div><div class="cal-day-name">س</div>';
    for (var i = 0; i < startDay; i++) html += '<div class="cal-day empty"></div>';
    for (var day = 1; day <= daysInMonth; day++) {
      var n = counts[day] || 0;
      html += '<div class="cal-day' + (n ? ' has-events' : '') + '"><span>' + day + '</span>' +
        (n ? '<small>' + n + '</small>' : '') + '</div>';
    }
    grid.innerHTML = html;
  }

  function changeMonth(delta) {
    calMonth += delta;
    if (calMonth > 11) { calMonth = 0; calYear++; }
    if (calMonth < 0) { calMonth = 11; calYear--; }
    renderCalendar('cal-grid', 'cal-title');
  }

  function goToday() {
    var now = new Date();
    calMonth = now.getMonth();
    calYear = now.getFullYear();
    renderCalendar('cal-grid', 'cal-title');
  }

  function printModalContent(titleId, bodyId) {
    var t = document.getElementById(titleId);
    var b = document.getElementById(bodyId);
    if (!t || !b) return;
    var w = window.open('', '_blank');
    w.document.write('<html dir="rtl"><head><title>' + t.textContent + '</title></head><body>' + b.innerHTML + '</body></html>');
    w.document.close();
    w.print();
  }

  return {
    switchTab: switchTab,
    initMap: initMap,
    fillFilterSelect: fillFilterSelect,
    initCalendar: initCalendar,
    setCalendarMonth: setCalendarMonth,
    setCalendarItems: setCalendarItems,
    refreshCalendar: refreshCalendar,
    changeMonth: changeMonth,
    goToday: goToday,
    printModalContent: printModalContent,
  };
})();

function switchTab(name) { OpsPage.switchTab(name); }
function changeMonth(d) { OpsPage.changeMonth(d); }
function goToday() { OpsPage.goToday(); }
