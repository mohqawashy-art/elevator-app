/**
 * LiftCore — حاسبة BOM وتسعير التركيب
 */
(function (global) {
  'use strict';

  var MACHINE_PRICES = {
    gearless: { 320: 14000, 450: 16000, 630: 19000, 800: 23000, 1000: 28000 },
    gearless_mrl: { 320: 14500, 450: 16500, 630: 19500, 800: 23500, 1000: 28500 },
    gearless_mr: { 320: 13500, 450: 15500, 630: 18500, 800: 22500, 1000: 27500 },
    geared: { 320: 11000, 450: 13000, 630: 15500, 800: 19000, 1000: 24000 },
    hydraulic: { 320: 12000, 450: 14000, 630: 17000, 800: 21000, 1000: 26000 },
    home: { 320: 9000, 450: 11000, 630: 13000, 800: 16000, 1000: 19000 },
  };
  var MACHINE_LABELS = {
    gearless: 'جيرلس MRL',
    gearless_mrl: 'جيرلس MRL (بدون غرفة)',
    gearless_mr: 'جيرلس MR (بغرفة ماكينة)',
    geared: 'جير تقليدي',
    hydraulic: 'هيدروليك',
    home: 'مصعد منزلي / فيلا',
  };
  var ELEV_CLASS_LABELS = {
    passenger: 'ركاب',
    hospital: 'مستشفى / سرير',
    freight: 'بضائع',
    panorama: 'بانوراما',
    home: 'منزلي',
  };
  var CONTROL_SYS_LABELS = {
    simplex: 'Simplex',
    duplex: 'Duplex',
    group: 'Group Control',
    destination: 'Destination Control',
  };
  var PANEL_BASE_PRICE = 8000;
  var CUSTOM_ORIGIN_OPTION = '__custom__';
  var NONE_OPTION = '__none__';
  var ORIGIN_FACTORS = {
    chinese: 1.00,
    turkish: 1.15,
    korean: 1.20,
    indian: 0.95,
    european: 1.25,
    italian: 1.35,
    german: 1.30,
    japanese: 1.30,
  };
  var ORIGIN_LABELS = {
    chinese: 'صيني',
    turkish: 'تركي',
    korean: 'كوري',
    indian: 'هندي',
    european: 'أوروبي',
    italian: 'إيطالي',
    german: 'ألماني',
    japanese: 'ياباني',
  };
  var DOOR_PRICES = { tele: 2600, center: 3200, semi: 1800 };
  var DOOR_NAMES = {
    tele: 'باب دور أوتوماتيك تليسكوبي',
    center: 'باب دور أوتوماتيك سنتر',
    semi: 'باب دور نص أوتوماتيك',
  };
  var CABIN_PRICES = { paint: 12000, steel: 16000, pano: 22000 };
  var CABIN_NAMES = {
    paint: 'كبينة دهان حراري (تشطيب كامل)',
    steel: 'كبينة استانلس ستيل (تشطيب كامل)',
    pano: 'كبينة بانوراما (تشطيب كامل)',
  };
  var STD_CABIN = {
    320: { w: 100, d: 120 },
    450: { w: 110, d: 140 },
    630: { w: 110, d: 150 },
    800: { w: 130, d: 160 },
    1000: { w: 140, d: 170 },
  };
  var SHAFT_MARGIN_W = 70;
  var SHAFT_MARGIN_D = 20;
  var DIM_UNIT = 'سم';

  var STAGE_RAILS = 'مرحلة 1 — سكك وأبواب';
  var STAGE_CABIN = 'مرحلة 2 — تركيب كبينة وأحبال وماكينة';
  var STAGE_CTRL = 'مرحلة 3 — تركيب كنترول وتشغيل';
  var STAGE_UPG = 'أعمال التحديث';
  // نسب توزيع أجور التركيب على المراحل الثلاث (للعرض والطباعة)
  var STAGE_LABOR_SHARE = [
    { stage: STAGE_RAILS, share: 0.30 },
    { stage: STAGE_CABIN, share: 0.45 },
    { stage: STAGE_CTRL, share: 0.25 },
  ];

  var UPG = [
    { id: 'panel', name: 'لوحة تحكم + إنفرتر جديد', unit: 'قطعة', qty: function () { return 1; }, price: function (s, cap, spec) { return applyPanelOrigin(PANEL_BASE_PRICE, spec); }, desc: 'استبدال اللوحة القديمة بنظام حديث' },
    { id: 'machine', name: 'ماكينة جديدة', unit: 'قطعة', qty: function () { return 1; }, price: function (s, cap, spec) { return applyOrigin((MACHINE_PRICES.gearless_mrl || MACHINE_PRICES.gearless)[cap], spec, 'full'); }, desc: 'جيرلس بالحمولة المختارة' },
    { id: 'ldoors', name: 'أبواب أدوار أوتوماتيك', unit: 'باب', qty: function (s) { return s; }, price: function (s, cap, spec) { return applyOrigin(2600, spec, 'light'); }, desc: 'الكمية = عدد الوقفات' },
    { id: 'cdoor', name: 'باب كبينة + مشغل', unit: 'قطعة', qty: function () { return 1; }, price: function (s, cap, spec) { return applyOrigin(4500, spec, 'light'); }, desc: '' },
    { id: 'cabin', name: 'تجديد تشطيب الكبينة', unit: 'مقطوع', qty: function () { return 1; }, price: function () { return 8000; }, desc: '' },
    { id: 'ropes', name: 'حبال جر جديدة', unit: 'طقم', qty: function () { return 1; }, price: function () { return 3000; }, desc: '' },
    { id: 'wiring', name: 'إعادة تمديد ترافلينج وكهرباء البئر', unit: 'مقطوع', qty: function () { return 1; }, price: function () { return 2500; }, desc: '' },
    { id: 'cops', name: 'COP + أزرار استدعاء LOP', unit: 'طقم', qty: function () { return 1; }, price: function (s) { return 1200 + (250 * s); }, desc: '' },
    { id: 'safety', name: 'منظم سرعة + فحص باراشوت', unit: 'طقم', qty: function () { return 1; }, price: function () { return 2200; }, desc: '' },
    { id: 'commission', name: 'ضبط وبرمجة واختبارات تشغيل', unit: 'مقطوع', qty: function () { return 1; }, price: function () { return 2000; }, desc: 'إجباري مع أي تحديث' },
  ];

  function num(v) {
    var n = parseFloat(v);
    return isNaN(n) ? 0 : n;
  }

  function moneyRound(v) {
    return Math.round(num(v) / 10) * 10;
  }

  function isNone(v) {
    return v === NONE_OPTION || v === 'بدون';
  }

  function allInstallStages() {
    return [STAGE_RAILS, STAGE_CABIN, STAGE_CTRL];
  }

  function selectedStages(spec) {
    var all = allInstallStages();
    var raw = spec && spec.include_stages;
    var wanted = [];
    var i;
    if (!raw || !raw.length) return all.slice();
    for (i = 0; i < all.length; i++) {
      if (raw.indexOf(all[i]) >= 0) wanted.push(all[i]);
    }
    return wanted.length ? wanted : all.slice();
  }

  function laborShareForStages(stageNames) {
    var wanted = stageNames && stageNames.length ? stageNames : allInstallStages();
    var share = 0;
    var i;
    for (i = 0; i < STAGE_LABOR_SHARE.length; i++) {
      if (wanted.indexOf(STAGE_LABOR_SHARE[i].stage) >= 0) {
        share += STAGE_LABOR_SHARE[i].share;
      }
    }
    return share > 0 ? share : 1;
  }

  function originDisplay(spec, originKey, countryKey) {
    if (!spec) return '—';
    var id = spec[originKey] || 'chinese';
    if (isNone(id)) return '';
    if (id === CUSTOM_ORIGIN_OPTION) {
      return (spec[countryKey] || '').trim() || 'أخرى';
    }
    return ORIGIN_LABELS[id] || id || '—';
  }

  function originFactorByKey(spec, key) {
    var id = (spec && spec[key]) || 'chinese';
    if (isNone(id) || id === CUSTOM_ORIGIN_OPTION) {
      return 1.0;
    }
    return ORIGIN_FACTORS[id] || 1.0;
  }

  function originFactor(spec) {
    return originFactorByKey(spec, 'machine_origin');
  }

  function panelOriginFactor(spec) {
    return originFactorByKey(spec, 'panel_origin');
  }

  function applyFactor(basePrice, factor, mode) {
    if (mode === 'light') {
      return Math.round(basePrice * (1 + (factor - 1) * 0.5));
    }
    return Math.round(basePrice * factor);
  }

  function applyOrigin(basePrice, spec, mode) {
    return applyFactor(basePrice, originFactor(spec), mode);
  }

  function applyPanelOrigin(basePrice, spec) {
    return applyFactor(basePrice, panelOriginFactor(spec), 'full');
  }

  function equipmentSuffix(originKey, countryKey, brandKey, spec) {
    if (!spec || isNone(spec[originKey])) return '';
    var label = originDisplay(spec, originKey, countryKey);
    var brand = (spec && spec[brandKey]) || '';
    if (isNone(brand)) brand = '';
    if (label && brand) return ' — ' + label + ' ' + brand;
    if (label) return ' — ' + label;
    return '';
  }

  function originSuffix(spec) {
    return equipmentSuffix('machine_origin', 'machine_origin_country', 'machine_brand', spec);
  }

  function panelSuffix(spec) {
    return equipmentSuffix('panel_origin', 'panel_origin_country', 'panel_brand', spec);
  }

  function toCm(val) {
    var n = num(val);
    if (!n) return 0;
    if (n > 500) return Math.round(n / 10);
    return n;
  }

  function calcCabinFromShaft(spec) {
    var shaftW = toCm(spec.shaft_width);
    var shaftD = toCm(spec.shaft_depth);
    var cap = num(spec.capacity) || 630;
    var std = STD_CABIN[cap] || STD_CABIN[630];

    if (!shaftW || !shaftD) {
      return {
        width: std.w,
        depth: std.d,
        priceFactor: 1,
        label: std.w + '×' + std.d + ' ' + DIM_UNIT + ' (قياسي)',
        shaftOk: true,
      };
    }

    var maxW = shaftW - SHAFT_MARGIN_W;
    var maxD = shaftD - SHAFT_MARGIN_D;
    if (maxW < 90 || maxD < 100) {
      return { error: 'أبعاد البئر صغيرة جداً — راجع العرض والعمق الداخلي (بالسم)' };
    }

    var cabinW = Math.min(Math.floor(maxW / 5) * 5, Math.round(std.w * 1.2));
    var cabinD = Math.min(Math.floor(maxD / 5) * 5, Math.round(std.d * 1.2));
    cabinW = Math.max(cabinW, Math.round(std.w * 0.85));
    cabinD = Math.max(cabinD, Math.round(std.d * 0.85));

    if (cabinW < std.w * 0.85 || cabinD < std.d * 0.85) {
      return {
        error: 'مساحة البئر لا تكفي للحمولة ' + cap + ' كجم — الحد الأدنى تقريباً '
          + std.w + '×' + std.d + ' ' + DIM_UNIT,
      };
    }

    var stdArea = std.w * std.d;
    var actualArea = cabinW * cabinD;
    var priceFactor = actualArea / stdArea;
    priceFactor = Math.max(0.85, Math.min(priceFactor, 1.25));

    return {
      width: cabinW,
      depth: cabinD,
      priceFactor: priceFactor,
      label: cabinW + '×' + cabinD + ' ' + DIM_UNIT,
      shaftLabel: shaftW + '×' + shaftD + ' ' + DIM_UNIT,
      shaftOk: true,
    };
  }

  function buildNewBOM(spec) {
    var stops = num(spec.stops);
    var elevators = Math.max(1, Math.round(num(spec.elevator_count) || 1));
    var capRaw = spec.capacity;
    var cap = isNone(capRaw) ? 630 : (num(capRaw) || 630);
    var machine = isNone(spec.machine) ? '' : (spec.machine || 'gearless_mrl');
    if (machine === 'gearless') machine = 'gearless_mrl';
    var door = isNone(spec.door) ? '' : (spec.door || 'tele');
    var cabin = isNone(spec.cabin) ? '' : (spec.cabin || 'steel');
    var entrRaw = spec.entrances;
    var entr = isNone(entrRaw) ? 1 : (num(entrRaw) || 1);
    var floorH = toCm(spec.floor_height) || 300;
    var speed = isNone(spec.speed) ? '' : (spec.speed || '1.0');
    var shaft = isNone(spec.shaft) ? '' : (spec.shaft || 'ready');
    var elevClass = spec.elev_class || 'passenger';
    var controlSys = spec.control_sys || 'simplex';
    var includeMachine = !!machine;
    var includePanel = !isNone(spec.panel_origin);
    var machineSuffix = originSuffix(spec);
    var panelLabel = panelSuffix(spec);
    var wanted = selectedStages(spec);
    var cabinCalc = calcCabinFromShaft(Object.assign({}, spec, { capacity: cap }));

    if (cabinCalc.error && cabin && wanted.indexOf(STAGE_CABIN) >= 0) {
      return { error: cabinCalc.error };
    }

    if (floorH < 250 || floorH > 600) {
      return { error: 'ارتفاع الدور يجب أن يكون بين 250 و 600 سم' };
    }

    var travelM = ((stops - 1) * floorH) / 100;
    var railM = Math.ceil(travelM + 5);
    var brackets = Math.ceil(travelM / 1.5) + 1;
    var ropesM = Math.ceil((travelM + 10) * 5);
    var travCable = Math.ceil(travelM + 15);
    var doorsQty = stops * entr;
    var rows = [];
    var elevNote = elevators > 1 ? (' × ' + elevators + ' مصعد') : '';

    function add(stage, name, unit, qty, price) {
      rows.push({
        stage: stage,
        name: name + elevNote,
        unit: unit,
        qty: qty * elevators,
        price: price,
      });
    }

    // مرحلة 1 — سكك وأبواب
    add(STAGE_RAILS, 'سكك كبينة T89 (بالمتر)', 'متر', railM, 70);
    add(STAGE_RAILS, 'سكك ثقل T50 (بالمتر)', 'متر', railM, 45);
    if (door && DOOR_NAMES[door]) {
      add(STAGE_RAILS, DOOR_NAMES[door] + machineSuffix, 'باب', doorsQty, applyOrigin(DOOR_PRICES[door], spec, 'light'));
    }
    add(STAGE_RAILS, 'شيكالات تثبيت السكك', 'طقم', brackets, 120);
    add(STAGE_RAILS, 'مسامير وزوايا ومتفرقات تثبيت السكك', 'مقطوع', 1, 1500);
    if (shaft === 'steel') {
      add(STAGE_RAILS, 'هيكل حديد + تكسية (يُسعَّر من حاسبة الهيكل)', 'مقطوع', 1, 0);
    }

    // مرحلة 2 — كبينة وأحبال وماكينة
    if (includeMachine && MACHINE_PRICES[machine]) {
      var machineBase = MACHINE_PRICES[machine][cap] || MACHINE_PRICES[machine][630];
      var machineName = 'ماكينة ' + (MACHINE_LABELS[machine] || machine) + ' — ' + cap + ' كجم';
      if (speed) machineName += ' / ' + speed + ' م/ث';
      if (ELEV_CLASS_LABELS[elevClass]) machineName += ' / ' + ELEV_CLASS_LABELS[elevClass];
      machineName += machineSuffix;
      add(STAGE_CABIN, machineName, 'قطعة', 1, applyOrigin(machineBase, spec, 'full'));
    }
    if (cabin && CABIN_NAMES[cabin]) {
      var cabinBase = CABIN_PRICES[cabin];
      var cabinPrice = Math.round(applyOrigin(cabinBase, spec, 'light') * (cabinCalc.priceFactor || 1));
      var cabinDesc = CABIN_NAMES[cabin] + ' ' + (cabinCalc.label || '') + machineSuffix;
      add(STAGE_CABIN, cabinDesc, 'قطعة', 1, cabinPrice);
    }
    add(STAGE_CABIN, 'باب كبينة أوتوماتيك + مشغل (Operator)' + machineSuffix, 'قطعة', 1, applyOrigin(4500, spec, 'light'));
    add(STAGE_CABIN, 'شاسيه كبينة + باراشوت (Safety Gear)', 'طقم', 1, 6500);
    add(STAGE_CABIN, 'إطار ثقل موازن + بلوكات', 'طقم', 1, 3500);
    if (machine === 'hydraulic') {
      add(STAGE_CABIN, 'وحدة قدرة هيدروليك + أسطوانة', 'طقم', 1, applyOrigin(8500, spec, 'full'));
    } else {
      add(STAGE_CABIN, 'حبال جر 8 مم (بالمتر)', 'متر', ropesM, 12);
    }
    add(STAGE_CABIN, 'منظم سرعة (Governor) + بكرة شد', 'طقم', 1, 1800);
    add(STAGE_CABIN, 'بوفرات', 'قطعة', 2, 900);

    // مرحلة 3 — كنترول وتشغيل
    if (includePanel) {
      var ctrlExtra = controlSys === 'destination' ? 4500 : (controlSys === 'group' ? 2500 : (controlSys === 'duplex' ? 1200 : 0));
      var ctrlName = 'لوحة تحكم + إنفرتر' + panelLabel;
      if (CONTROL_SYS_LABELS[controlSys]) ctrlName += ' — ' + CONTROL_SYS_LABELS[controlSys];
      add(STAGE_CTRL, ctrlName, 'قطعة', 1, applyPanelOrigin(PANEL_BASE_PRICE, spec) + ctrlExtra);
    }
    add(STAGE_CTRL, 'ترافلينج كيبل (بالمتر)', 'متر', travCable, 18);
    add(STAGE_CTRL, 'مفاتيح حدود + ممرات مغناطيسية', 'طقم', 1, 800);
    add(STAGE_CTRL, 'لوحة كبينة COP', 'قطعة', 1, 1200);
    add(STAGE_CTRL, 'أزرار استدعاء الأدوار LOP', 'قطعة', stops, 250);
    add(STAGE_CTRL, 'فوتوسيل (ستارة ضوئية)', 'قطعة', 1, 350);
    add(STAGE_CTRL, 'إنتركم + جرس إنذار', 'طقم', 1, 600);
    add(STAGE_CTRL, 'إنارة وتهوية كبينة', 'طقم', 1, 700);
    add(STAGE_CTRL, 'ضبط وبرمجة واختبارات تشغيل وتسليم', 'مقطوع', 1, 2000);

    rows = rows.filter(function (r) { return wanted.indexOf(r.stage) >= 0; });
    if (!rows.length) {
      return { error: 'اختر مرحلة واحدة على الأقل' };
    }

    return {
      rows: rows,
      labor: Math.round((5000 + (1200 * stops)) * elevators * laborShareForStages(wanted)),
      quote_type: 'new',
      cabin_calc: cabinCalc,
      elevator_count: elevators,
      stages: wanted,
    };
  }

    function buildExtendBOM(spec) {
      var currentStops = Math.max(2, Math.round(num(spec.current_stops) || 3));
      var addedStops = Math.max(1, Math.round(num(spec.added_stops) || 1));
      var newStops = currentStops + addedStops;
      var elevators = Math.max(1, Math.round(num(spec.elevator_count) || 1));
      var door = isNone(spec.door) ? '' : (spec.door || 'tele');
      var entrRaw = spec.entrances;
      var entr = isNone(entrRaw) ? 1 : (num(entrRaw) || 1);
      var floorH = toCm(spec.floor_height) || 300;
      var machineSuffix = originSuffix(spec);
      var wanted = selectedStages(spec);

      if (floorH < 250 || floorH > 600) {
        return { error: 'ارتفاع الدور يجب أن يكون بين 250 و 600 سم' };
      }
      if (newStops > 20) {
        return { error: 'إجمالي الوقفات بعد الإضافة كبير جداً — راجع العدد' };
      }

      var addedTravelM = (addedStops * floorH) / 100;
      var railM = Math.ceil(addedTravelM + 1);
      var brackets = Math.ceil(addedTravelM / 1.5) + 1;
      var ropesM = Math.ceil((addedTravelM + 5) * 5);
      var travCable = Math.ceil(addedTravelM + 8);
      var doorsQty = addedStops * entr;
      var rows = [];
      var elevNote = elevators > 1 ? (' × ' + elevators + ' مصعد') : '';
      var rangeNote = ' (من ' + currentStops + ' إلى ' + newStops + ' وقفات)';

      function add(stage, name, unit, qty, price) {
        rows.push({
          stage: stage,
          name: name + elevNote,
          unit: unit,
          qty: qty * elevators,
          price: price,
        });
      }

      add(STAGE_RAILS, 'سكك كبينة T89 للأدوار المضافة' + rangeNote, 'متر', railM, 70);
      add(STAGE_RAILS, 'سكك ثقل T50 للأدوار المضافة' + rangeNote, 'متر', railM, 45);
      if (door && DOOR_NAMES[door]) {
        add(STAGE_RAILS, DOOR_NAMES[door] + ' — أدوار جديدة' + machineSuffix, 'باب', doorsQty, applyOrigin(DOOR_PRICES[door], spec, 'light'));
      }
      add(STAGE_RAILS, 'شيكالات تثبيت السكك للأدوار المضافة', 'طقم', brackets, 120);
      add(STAGE_RAILS, 'مسامير وزوايا ومتفرقات تمديد السكك', 'مقطوع', 1, 800);

      add(STAGE_CABIN, 'تمديد حبال جر 8 مم للأدوار المضافة', 'متر', ropesM, 12);
      add(STAGE_CABIN, 'بلوكات ثقل موازن إضافية', 'طقم', 1, 1800);
      add(STAGE_CABIN, 'بوفرات / تعديلات نهاية البئر', 'طقم', 1, 900);

      add(STAGE_CTRL, 'تمديد ترافلينج كيبل للأدوار المضافة', 'متر', travCable, 18);
      add(STAGE_CTRL, 'أزرار استدعاء الأدوار الجديدة LOP', 'قطعة', addedStops * entr, 250);
      add(STAGE_CTRL, 'تعديل برمجة اللوحة وإضافة المحطات الجديدة', 'مقطوع', 1, 1500);
      add(STAGE_CTRL, 'اختبارات تشغيل وتسليم بعد إضافة الأدوار', 'مقطوع', 1, 1200);

      rows = rows.filter(function (r) { return wanted.indexOf(r.stage) >= 0; });
      if (!rows.length) {
        return { error: 'اختر مرحلة واحدة على الأقل' };
      }

      return {
        rows: rows,
        labor: Math.round((3500 + (1800 * addedStops)) * elevators * laborShareForStages(wanted)),
        quote_type: 'extend',
        elevator_count: elevators,
        current_stops: currentStops,
        added_stops: addedStops,
        stops: newStops,
        stages: wanted,
      };
    }

    function buildUpgradeBOM(spec, selected) {
    var stops = num(spec.stops);
    var elevators = Math.max(1, Math.round(num(spec.elevator_count) || 1));
    var cap = num(spec.capacity) || 630;
    var elevNote = elevators > 1 ? (' × ' + elevators + ' مصعد') : '';
    var rows = [];
    var i, u, count = 0;
    for (i = 0; i < UPG.length; i++) {
      u = UPG[i];
      if (selected[u.id]) {
        rows.push({
          stage: STAGE_UPG,
          name: u.name + elevNote,
          unit: u.unit,
          qty: u.qty(stops) * elevators,
          price: u.price(stops, cap, spec),
        });
        count++;
      }
    }
    if (!count) {
      return { error: 'اختر مكوناً واحداً على الأقل من بطاقات التحديث' };
    }
    return {
      rows: rows,
      labor: (2000 + (400 * stops)) * elevators,
      quote_type: 'upgrade',
      elevator_count: elevators,
    };
  }

  function calcTotals(rows, labor, transport, other, profitPct) {
    var materials = 0;
    var i;
    for (i = 0; i < rows.length; i++) {
      materials += num(rows[i].qty) * num(rows[i].price);
    }
    labor = num(labor);
    transport = num(transport);
    other = num(other);
    profitPct = num(profitPct);
    var cost = materials + labor + transport + other;
    var profit = cost * profitPct / 100;
    var before = cost + profit;
    var vat = before * 0.15;
    var grand = before + vat;
    return {
      materials_total: moneyRound(materials),
      cost_total: moneyRound(cost),
      profit_amount: moneyRound(profit),
      before_tax: moneyRound(before),
      vat_amount: moneyRound(vat),
      grand_total: moneyRound(grand),
    };
  }

  global.LiftCoreInstallPricing = {
    MACHINE_PRICES: MACHINE_PRICES,
    ORIGIN_FACTORS: ORIGIN_FACTORS,
    ORIGIN_LABELS: ORIGIN_LABELS,
    DOOR_NAMES: DOOR_NAMES,
    CABIN_NAMES: CABIN_NAMES,
    STAGE_RAILS: STAGE_RAILS,
    STAGE_CABIN: STAGE_CABIN,
    STAGE_CTRL: STAGE_CTRL,
    STAGE_LABOR_SHARE: STAGE_LABOR_SHARE,
    selectedStages: selectedStages,
    UPG: UPG,
    buildNewBOM: buildNewBOM,
    buildExtendBOM: buildExtendBOM,
    buildUpgradeBOM: buildUpgradeBOM,
    calcTotals: calcTotals,
    calcCabinFromShaft: calcCabinFromShaft,
    originLabel: function (id) { return ORIGIN_LABELS[id] || id || '—'; },
    originDisplay: originDisplay,
    toCm: toCm,
    CUSTOM_ORIGIN_OPTION: CUSTOM_ORIGIN_OPTION,
    NONE_OPTION: NONE_OPTION,
    isNone: isNone,
    num: num,
    splitLaborByStage: function (laborTotal, stageFilter) {
      var total = num(laborTotal);
      var parts = STAGE_LABOR_SHARE;
      var out = [];
      var i, amount, used = 0, shareSum = 0;
      if (stageFilter && stageFilter.length) {
        parts = [];
        for (i = 0; i < STAGE_LABOR_SHARE.length; i++) {
          if (stageFilter.indexOf(STAGE_LABOR_SHARE[i].stage) >= 0) {
            parts.push(STAGE_LABOR_SHARE[i]);
          }
        }
      }
      if (!parts.length) parts = STAGE_LABOR_SHARE;
      for (i = 0; i < parts.length; i++) shareSum += parts[i].share;
      if (shareSum <= 0) shareSum = 1;
      for (i = 0; i < parts.length; i++) {
        if (i === parts.length - 1) {
          amount = Math.round(total - used);
        } else {
          amount = Math.round(total * (parts[i].share / shareSum));
          used += amount;
        }
        out.push({
          stage: parts[i].stage,
          label: 'أجور وتركيب — ' + parts[i].stage.replace(/^مرحلة \d+ — /, ''),
          amount: amount,
        });
      }
      return out;
    },
  };
})(typeof window !== 'undefined' ? window : this);
