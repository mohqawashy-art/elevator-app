(function (global) {
  'use strict';

  /** معرّفات حقول صفحة التسعير — templates/elevator-estimates.html */
  var FIELD_IDS = {
    stops: 'stops',
    machine_type: 'machine_type',
    capacity_kg: 'capacity_kg',
    doors_count: 'doors_count',
    elev_type: 'elev_type',
    speed: 'speed',
    travel_m: 'travel_m',
  };

  var FLOOR_NAMES = [
    'الأرضي', 'الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس',
    'السادس', 'السابع', 'الثامن', 'التاسع', 'العاشر',
    '11', '12', '13', '14', '15',
  ];

  var THEMES = {
    dark: {
      shaftFill: '#1a2435',
      shaftStroke: 'rgba(201, 161, 74, 0.38)',
      floorLine: 'rgba(138, 155, 184, 0.42)',
      floorLabelBg: '#0a2647',
      floorLabelText: '#e4eaf5',
      doorFill: '#6b7789',
      doorStroke: '#8a9bb8',
      doorAccent: '#c9a14a',
      doorSplit: '#5a6a7e',
      counterweight: '#8a9bb8',
      counterweightStroke: '#6b7789',
      rail: 'rgba(138, 155, 184, 0.38)',
      carFill: '#2a7fff',
      carStroke: '#18578d',
      carDoor: '#cfe0f2',
      carText: '#eaf2fb',
      rope: '#8794a8',
      machineFill: '#0a2647',
      machineStroke: '#c9a14a',
      machineText: '#8a9bb8',
      machineRoomFill: '#0a2647',
      machineRoomText: '#ffffff',
      pitFill: '#161e2b',
      pitStroke: 'rgba(201, 161, 74, 0.28)',
      pitText: '#8a9bb8',
      bumper: '#7a8a9c',
      infoText: '#c8a055',
      hydraulicFill: '#2a5a8a',
    },
    light: {
      shaftFill: '#eef2f8',
      shaftStroke: '#b9c4d6',
      floorLine: '#c4cedd',
      floorLabelBg: '#0a2647',
      floorLabelText: '#ffffff',
      doorFill: '#9aa6b8',
      doorStroke: '#6b7789',
      doorAccent: '#c9a14a',
      doorSplit: '#6b7789',
      counterweight: '#9aa6b8',
      counterweightStroke: '#6b7789',
      rail: '#b9c4d6',
      carFill: '#2e7cc4',
      carStroke: '#18578d',
      carDoor: '#cfe0f2',
      carText: '#eaf2fb',
      rope: '#8794a8',
      machineFill: '#0a2647',
      machineStroke: '#c9a14a',
      machineText: '#6b7a90',
      machineRoomFill: '#0a2647',
      machineRoomText: '#ffffff',
      pitFill: '#dde4ee',
      pitStroke: '#b9c4d6',
      pitText: '#6b7a90',
      bumper: '#9aa6b8',
      infoText: '#0a2647',
      hydraulicFill: '#2e7cc4',
    },
  };

  function clamp(n, min, max) {
    return Math.min(max, Math.max(min, n));
  }

  function safeInt(value, fallback, min, max) {
    var n = parseInt(value, 10);
    if (isNaN(n)) n = fallback;
    return clamp(n, min, max);
  }

  function getEl(idOrName) {
    if (!idOrName) return null;
    return document.getElementById(idOrName) ||
      document.querySelector('[name="' + idOrName + '"]');
  }

  function mapMachineType(raw) {
    var v = (raw || 'MR').toUpperCase();
    if (v === 'MRL') return 'gearless';
    if (v === 'HYDRAULIC') return 'hydraulic';
    return 'geared';
  }

  function deriveEntrances(stops, doorsCount) {
    var doors = safeInt(doorsCount, stops, 1, 120);
    if (doors >= stops * 2) return '2';
    if (doors > stops) return '2';
    return '1';
  }

  function normalizeSpec(raw) {
    var stops = safeInt(raw && raw.stops, 5, 2, 15);
    var doorsCount = raw && raw.doors_count != null ? raw.doors_count : stops;
    var door = (raw && raw.door_type) || 'tele';
    if (door !== 'tele' && door !== 'center' && door !== 'semi') door = 'tele';

    return {
      stops: stops,
      cap: String(raw && raw.capacity_kg != null ? raw.capacity_kg : 630),
      machine: mapMachineType(raw && raw.machine_type),
      machineLabel: (raw && raw.machine_type) || 'MR',
      door: door,
      entr: (raw && raw.entrances) || deriveEntrances(stops, doorsCount),
    };
  }

  function readFromForm() {
    return normalizeSpec({
      stops: getEl(FIELD_IDS.stops) && getEl(FIELD_IDS.stops).value,
      machine_type: getEl(FIELD_IDS.machine_type) && getEl(FIELD_IDS.machine_type).value,
      capacity_kg: getEl(FIELD_IDS.capacity_kg) && getEl(FIELD_IDS.capacity_kg).value,
      doors_count: getEl(FIELD_IDS.doors_count) && getEl(FIELD_IDS.doors_count).value,
    });
  }

  function doorShape(door, dx, doorY, doorH, side, c) {
    var part = '';
    var w = 7;
    if (side === 'right') {
      part += '<rect x="' + dx + '" y="' + doorY + '" width="' + w + '" height="' + doorH + '" fill="' + c.doorFill + '" stroke="' + c.doorStroke + '" stroke-width="1"/>';
      if (door === 'semi') {
        part += '<line x1="' + (dx + w) + '" y1="' + doorY + '" x2="' + (dx + w + 6) + '" y2="' + (doorY + 5) + '" stroke="' + c.doorAccent + '" stroke-width="1.2"/>';
        part += '<path d="M ' + (dx + w) + ' ' + (doorY + doorH) + ' q 7 -3 7 -9" fill="none" stroke="' + c.doorAccent + '" stroke-width="1" stroke-dasharray="2 2"/>';
      } else {
        part += '<line x1="' + (dx + w / 2) + '" y1="' + doorY + '" x2="' + (dx + w / 2) + '" y2="' + (doorY + doorH) + '" stroke="' + c.doorSplit + '" stroke-width="0.8"/>';
      }
      part += '<circle cx="' + (dx + w + 13) + '" cy="' + (doorY + doorH / 2) + '" r="3" fill="' + c.doorAccent + '"/>';
    } else {
      part += '<rect x="' + dx + '" y="' + doorY + '" width="' + w + '" height="' + doorH + '" fill="' + c.doorFill + '" stroke="' + c.doorStroke + '" stroke-width="1"/>';
      if (door === 'semi') {
        part += '<line x1="' + dx + '" y1="' + doorY + '" x2="' + (dx - 6) + '" y2="' + (doorY + 5) + '" stroke="' + c.doorAccent + '" stroke-width="1.2"/>';
        part += '<path d="M ' + dx + ' ' + (doorY + doorH) + ' q -7 -3 -7 -9" fill="none" stroke="' + c.doorAccent + '" stroke-width="1" stroke-dasharray="2 2"/>';
      } else {
        part += '<line x1="' + (dx + w / 2) + '" y1="' + doorY + '" x2="' + (dx + w / 2) + '" y2="' + (doorY + doorH) + '" stroke="' + c.doorSplit + '" stroke-width="0.8"/>';
      }
      part += '<circle cx="' + (dx - 13) + '" cy="' + (doorY + doorH / 2) + '" r="3" fill="' + c.doorAccent + '"/>';
    }
    return part;
  }

  function buildSvg(spec, themeName) {
    var c = THEMES[themeName === 'light' ? 'light' : 'dark'] || THEMES.dark;
    var stops = spec.stops;
    var cap = spec.cap;
    var machine = spec.machine;
    var door = spec.door;
    var entr = spec.entr;
    var machineLabel = spec.machineLabel;

    var W = entr === '2' ? 380 : 340;
    var floorH = 58;
    var topPad = machine === 'gearless' ? 30 : (machine === 'hydraulic' ? 24 : 64);
    var pitH = machine === 'hydraulic' ? 48 : 34;
    var shaftX = 70;
    var shaftW = 150;
    var shaftTop = topPad;
    var shaftH = stops * floorH;
    var shaftBottom = shaftTop + shaftH;
    var H = shaftBottom + pitH + 24;

    var carW = shaftW * 0.52;
    var carMargin = (shaftW - carW) / 2;
    var carH = floorH - 12;
    var carY = shaftBottom - floorH + 6;
    var carX = shaftX + carMargin;

    var s = '';
    var i;
    s += '<svg viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Sans Arabic,Tajawal,sans-serif" role="img" aria-label="مخطط مصعد">';

    s += '<rect x="' + shaftX + '" y="' + shaftTop + '" width="' + shaftW + '" height="' + shaftH + '" fill="' + c.shaftFill + '" stroke="' + c.shaftStroke + '" stroke-width="2"/>';

    for (i = 0; i < stops; i++) {
      var fy = shaftTop + i * floorH;
      if (i > 0) {
        s += '<line x1="' + shaftX + '" y1="' + fy + '" x2="' + (shaftX + shaftW) + '" y2="' + fy + '" stroke="' + c.floorLine + '" stroke-width="1.4" stroke-dasharray="4 3"/>';
      }
      var floorIndex = stops - 1 - i;
      var labelY = fy + floorH / 2 + 4;
      var labelX = entr === '2' ? (shaftX + shaftW / 2) : (shaftX + shaftW + 36);
      s += '<g>';
      if (entr === '2') {
        s += '<rect x="' + (labelX - 28) + '" y="' + (labelY - 13) + '" width="56" height="22" rx="5" fill="' + c.floorLabelBg + '"/>';
        s += '<text x="' + labelX + '" y="' + (labelY + 2) + '" fill="' + c.floorLabelText + '" font-size="11" font-weight="700" text-anchor="middle">' + (FLOOR_NAMES[floorIndex] || floorIndex) + '</text>';
      } else {
        s += '<rect x="' + (shaftX + shaftW + 8) + '" y="' + (labelY - 13) + '" width="56" height="22" rx="5" fill="' + c.floorLabelBg + '"/>';
        s += '<text x="' + (shaftX + shaftW + 36) + '" y="' + (labelY + 2) + '" fill="' + c.floorLabelText + '" font-size="11" font-weight="700" text-anchor="middle">' + (FLOOR_NAMES[floorIndex] || floorIndex) + '</text>';
      }
      s += '</g>';

      var doorH = floorH * 0.6;
      var doorY = fy + (floorH - doorH) / 2;
      s += doorShape(door, shaftX - 7, doorY, doorH, 'left', c);
      if (entr === '2') {
        s += doorShape(door, shaftX + shaftW, doorY, doorH, 'right', c);
      }
    }

    if (machine !== 'hydraulic') {
      var cwX = shaftX + shaftW - 22;
      var cwW = 14;
      s += '<rect x="' + cwX + '" y="' + (shaftTop + 10) + '" width="' + cwW + '" height="' + (shaftH * 0.34) + '" rx="2" fill="' + c.counterweight + '" stroke="' + c.counterweightStroke + '" stroke-width="1"/>';
    }

    s += '<line x1="' + (shaftX + carMargin - 6) + '" y1="' + shaftTop + '" x2="' + (shaftX + carMargin - 6) + '" y2="' + shaftBottom + '" stroke="' + c.rail + '" stroke-width="2"/>';
    s += '<line x1="' + (shaftX + carMargin + carW + 6) + '" y1="' + shaftTop + '" x2="' + (shaftX + carMargin + carW + 6) + '" y2="' + shaftBottom + '" stroke="' + c.rail + '" stroke-width="2"/>';

    s += '<rect x="' + carX + '" y="' + carY + '" width="' + carW + '" height="' + carH + '" rx="3" fill="' + c.carFill + '" stroke="' + c.carStroke + '" stroke-width="2"/>';
    s += '<line x1="' + (carX + carW / 2) + '" y1="' + carY + '" x2="' + (carX + carW / 2) + '" y2="' + (carY + carH) + '" stroke="' + c.carDoor + '" stroke-width="1.5"/>';
    s += '<text x="' + (carX + carW / 2) + '" y="' + (carY + carH / 2 + 5) + '" fill="' + c.carText + '" font-size="14" text-anchor="middle">▲▼</text>';

    if (machine === 'hydraulic') {
      s += '<line x1="' + (carX + carW / 2) + '" y1="' + (carY + carH) + '" x2="' + (carX + carW / 2) + '" y2="' + shaftBottom + '" stroke="' + c.rope + '" stroke-width="2"/>';
      s += '<rect x="' + (carX + carW / 2 - 8) + '" y="' + (shaftBottom + 6) + '" width="16" height="' + (pitH - 10) + '" rx="4" fill="' + c.hydraulicFill + '" stroke="' + c.machineStroke + '" stroke-width="1.5"/>';
      s += '<text x="' + (shaftX + shaftW / 2) + '" y="' + (shaftTop - 8) + '" fill="' + c.machineText + '" font-size="9.5" text-anchor="middle">ماكينة هيدروليك (Hydraulic)</text>';
    } else {
      s += '<line x1="' + (carX + carW / 2) + '" y1="' + carY + '" x2="' + (carX + carW / 2) + '" y2="' + shaftTop + '" stroke="' + c.rope + '" stroke-width="1.2"/>';
      var cwMid = shaftX + shaftW - 15;
      s += '<line x1="' + cwMid + '" y1="' + (shaftTop + 10) + '" x2="' + cwMid + '" y2="' + shaftTop + '" stroke="' + c.rope + '" stroke-width="1.2"/>';
      if (machine === 'gearless') {
        s += '<circle cx="' + (shaftX + shaftW / 2) + '" cy="' + (shaftTop - 2) + '" r="13" fill="' + c.machineFill + '" stroke="' + c.machineStroke + '" stroke-width="2"/>';
        s += '<text x="' + (shaftX + shaftW / 2) + '" y="' + (shaftTop - 18) + '" fill="' + c.machineText + '" font-size="9.5" text-anchor="middle">ماكينة جيرلس (MRL)</text>';
      } else {
        s += '<rect x="' + (shaftX - 6) + '" y="' + (shaftTop - 44) + '" width="' + (shaftW + 12) + '" height="40" rx="3" fill="' + c.machineRoomFill + '"/>';
        s += '<text x="' + (shaftX + shaftW / 2) + '" y="' + (shaftTop - 20) + '" fill="' + c.machineRoomText + '" font-size="10" text-anchor="middle" font-weight="700">غرفة الماكينة (MR)</text>';
        s += '<circle cx="' + (shaftX + shaftW / 2) + '" cy="' + (shaftTop - 12) + '" r="6" fill="' + c.machineStroke + '"/>';
      }
    }

    s += '<rect x="' + shaftX + '" y="' + shaftBottom + '" width="' + shaftW + '" height="' + pitH + '" fill="' + c.pitFill + '" stroke="' + c.pitStroke + '" stroke-width="2"/>';
    s += '<text x="' + (shaftX + shaftW / 2) + '" y="' + (shaftBottom + pitH / 2 + 4) + '" fill="' + c.pitText + '" font-size="10" text-anchor="middle">حفرة (Pit)</text>';
    s += '<rect x="' + (carX + carW / 2 - 10) + '" y="' + (shaftBottom + 8) + '" width="6" height="' + (pitH - 14) + '" fill="' + c.bumper + '"/>';
    s += '<rect x="' + (carX + carW / 2 + 4) + '" y="' + (shaftBottom + 8) + '" width="6" height="' + (pitH - 14) + '" fill="' + c.bumper + '"/>';

    var capTxt = cap + ' كجم';
    var doorTxt = door === 'tele' ? 'تليسكوبي' : (door === 'center' ? 'سنتر' : 'نص أوتوماتيك');
    var entrTxt = entr === '2' ? 'مدخلان' : 'مدخل';
    s += '<text x="' + (W / 2) + '" y="' + (H - 4) + '" fill="' + c.infoText + '" font-size="11" font-weight="700" text-anchor="middle">'
      + stops + ' وقفات · ' + capTxt + ' · ' + machineLabel + ' · باب ' + doorTxt + ' · ' + entrTxt + '</text>';

    s += '</svg>';
    return s;
  }

  function draw(containerId, spec, options) {
    var el = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
    if (!el) return '';
    var opts = options || {};
    var normalized = normalizeSpec(spec || {});
    var svg = buildSvg(normalized, opts.theme || 'dark');
    el.innerHTML = svg;
    return svg;
  }

  function bindForm(containerId) {
    var container = containerId || 'elevatorDiagram';
    function refresh() {
      draw(container, readFromForm(), { theme: 'dark' });
    }
    refresh();
    Object.keys(FIELD_IDS).forEach(function (key) {
      var field = getEl(FIELD_IDS[key]);
      if (!field) return;
      field.addEventListener('input', refresh);
      field.addEventListener('change', refresh);
    });
  }

  global.LiftCoreElevatorDiagram = {
    FIELD_IDS: FIELD_IDS,
    readFromForm: readFromForm,
    normalizeSpec: normalizeSpec,
    draw: draw,
    bindForm: bindForm,
  };
})(typeof window !== 'undefined' ? window : this);
