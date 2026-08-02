// Match صناع التميز2026 style — About Us stacked layout
// Safe fonts + separate title frames (no invalid paragraph refs)

(function () {
    if (!app.documents.length) {
        alert("Open the TwinAxis document first.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    function color(name, cmyk) {
        try {
            var s = doc.swatches.itemByName(name);
            if (s.isValid) return s;
        } catch (e) {}
        var c = doc.colors.add();
        c.name = name;
        c.model = ColorModel.PROCESS;
        c.space = ColorSpace.CMYK;
        c.colorValue = cmyk;
        return c;
    }

    function para(name) {
        try {
            var p = doc.paragraphStyles.itemByName(name);
            if (p.isValid) return p;
        } catch (e) {}
        return doc.paragraphStyles.add({ name: name });
    }

    function ch(name) {
        try {
            var c = doc.characterStyles.itemByName(name);
            if (c.isValid) return c;
        } catch (e) {}
        return doc.characterStyles.add({ name: name });
    }

    function layer(name, atEnd) {
        try {
            var L = doc.layers.itemByName(name);
            if (L.isValid) { L.locked = false; return L; }
        } catch (e) {}
        var n = doc.layers.add({ name: name });
        try {
            if (atEnd) n.move(LocationOptions.AT_END);
            else n.move(LocationOptions.AT_BEGINNING);
        } catch (e2) {}
        return n;
    }

    function masterA() {
        for (var i = 0; i < doc.masterSpreads.length; i++) {
            if (String(doc.masterSpreads.item(i).namePrefix) === "A") {
                return doc.masterSpreads.item(i);
            }
        }
        return doc.masterSpreads.item(0);
    }

    function clearLabeled(page, label) {
        var items = page.pageItems.everyItem().getElements();
        for (var i = items.length - 1; i >= 0; i--) {
            try { if (items[i].label === label) items[i].remove(); } catch (e) {}
        }
    }

    function addRect(page, bounds, fill, lay) {
        doc.activeLayer = lay;
        var r = page.rectangles.add();
        r.geometricBounds = bounds;
        r.fillColor = fill;
        r.strokeWeight = 0;
        try { r.strokeColor = doc.swatches.itemByName("None"); } catch (e) {}
        r.label = "em_style_match";
        return r;
    }

    function addTF(page, bounds, lay) {
        doc.activeLayer = lay;
        var t = page.textFrames.add();
        t.geometricBounds = bounds;
        t.label = "em_style_match";
        return t;
    }

    // Apply font by FAMILY + STYLE strings (most reliable in ID)
    function setFont(p, family, style) {
        try {
            p.appliedFont = family;
            p.fontStyle = style;
            return true;
        } catch (e) {
            try {
                p.appliedFont = "Arial";
                p.fontStyle = (style === "Bold" || style === "Bold") ? "Bold" : "Regular";
            } catch (e2) {}
            return false;
        }
    }

    function applyPara(tf, styleObj) {
        try {
            tf.paragraphs.everyItem().appliedParagraphStyle = styleObj;
        } catch (e) {
            try { tf.paragraphs.item(0).appliedParagraphStyle = styleObj; } catch (e2) {}
        }
    }

    function highlightPhrase(tf, phrase, charStyle) {
        try {
            app.findTextPreferences = NothingEnum.NOTHING;
            app.changeTextPreferences = NothingEnum.NOTHING;
            app.findTextPreferences.findWhat = phrase;
            app.changeTextPreferences.appliedCharacterStyle = charStyle;
            tf.changeText();
        } catch (e) {}
        try {
            app.findTextPreferences = NothingEnum.NOTHING;
            app.changeTextPreferences = NothingEnum.NOTHING;
        } catch (e2) {}
    }

    var cNavy    = color("EM / Navy", [100, 80, 20, 35]);
    var cMidBlue = color("EM / Mid Blue", [90, 55, 0, 10]);
    var cGold    = color("EM / Gold", [15, 30, 90, 5]);
    var cBodyAR  = color("EM / Body", [0, 0, 0, 75]);
    var cBodyEN  = color("EM / Body EN", [0, 0, 0, 60]);
    var cSoft    = color("EM / Soft Grey", [0, 0, 0, 8]);
    var cPaper   = doc.swatches.itemByName("Paper");

    // Styles
    var stArH1 = para("01 AR / H1 Section");
    try { stArH1.appliedFont = "Dubai"; stArH1.fontStyle = "Bold"; } catch (e) {
        try { stArH1.appliedFont = "Arial"; stArH1.fontStyle = "Bold"; } catch (e2) {}
    }
    stArH1.pointSize = 26;
    stArH1.leading = 32;
    stArH1.fillColor = cMidBlue;
    stArH1.justification = Justification.LEFT_ALIGN;
    stArH1.spaceAfter = 0;
    try { stArH1.composer = "Adobe World-Ready Paragraph Composer"; } catch (e) {}

    var stEnH1 = para("11 EN / H1 Section");
    try { stEnH1.appliedFont = "Arial"; stEnH1.fontStyle = "Bold"; } catch (e) {}
    stEnH1.pointSize = 11;
    stEnH1.leading = 14;
    stEnH1.fillColor = cGold;
    stEnH1.justification = Justification.LEFT_ALIGN;
    stEnH1.tracking = 100;
    stEnH1.capitalization = Capitalization.ALL_CAPS;
    stEnH1.spaceAfter = 0;

    var stArBody = para("03 AR / Body");
    try { stArBody.appliedFont = "Dubai"; stArBody.fontStyle = "Regular"; } catch (e) {
        try { stArBody.appliedFont = "Tahoma"; stArBody.fontStyle = "Regular"; } catch (e2) {}
    }
    stArBody.pointSize = 10.5;
    stArBody.leading = 18;
    stArBody.fillColor = cBodyAR;
    stArBody.justification = Justification.FULLY_JUSTIFIED;
    stArBody.spaceAfter = "3.5mm";
    stArBody.hyphenation = false;
    try { stArBody.composer = "Adobe World-Ready Paragraph Composer"; } catch (e) {}
    try { stArBody.paragraphDirection = ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION; } catch (e) {}

    var stEnBody = para("13 EN / Body");
    try { stEnBody.appliedFont = "Arial"; stEnBody.fontStyle = "Regular"; } catch (e) {}
    stEnBody.pointSize = 9.5;
    stEnBody.leading = 15;
    stEnBody.fillColor = cBodyEN;
    stEnBody.justification = Justification.LEFT_JUSTIFIED;
    stEnBody.spaceAfter = "3mm";

    var chBrandAR = ch("C01 AR / Brand Bold");
    try { chBrandAR.appliedFont = "Dubai"; chBrandAR.fontStyle = "Bold"; } catch (e) {}
    chBrandAR.fillColor = cMidBlue;

    var chBrandEN = ch("C02 EN / Brand Bold");
    try { chBrandEN.appliedFont = "Arial"; chBrandEN.fontStyle = "Bold"; } catch (e) {}
    chBrandEN.fillColor = cMidBlue;

    var AR_BODY =
        "شركة صناع التميز المحدودة — إحدى شركات صناع التنمية السعودية، والتي تعمل في مجالات متعددة: المقاولات العامة، الاستثمار العقاري، استثمار وتشغيل الفنادق، إدارة المشاريع، خدمات المعتمرين، السياحة، والمطاعم. يقع المقر الرئيسي لها بمدينة مكة المكرمة.\r" +
        "تعكف الشركة دائمًا على التعاون الوثيق مع عملائها، واستغلال الخبرات الفنية المتاحة لديها وفريق العمل المحترف لتحقيق الأهداف المنشودة من حيث الوقت والتكلفة والجودة، مع التركيز على تقليل المخاطر والمحافظة على البيئة، وذلك من خلال السعي الحثيث للتنمية المستدامة في السوق السعودي عامة وسوق مكة المكرمة خاصة.\r" +
        "وتلتزم شركة صناع التميز دائمًا بتدعيم مهاراتها وإمكاناتها الفنية من خلال اختيار وتنمية رأس المال البشري، مع الاستمرار في تطوير كوادرها الفنية عبر برامج التدريب المختلفة.\r" +
        "وتفخر شركة صناع التميز دائمًا ببيئة العمل الحميمة التي توفرها لموظفيها، مما ينعكس مباشرة على الخدمة الممتازة التي تقدمها لعملائها الكرام، لتشارك في وضع بصمة ثابتة وبناءة في السوق السعودي.";

    var EN_BODY =
        "Excellence Makers Co. Ltd., a member of the Saudi Development Makers Group, is a diversified company operating across multiple sectors: general contracting, real estate investment, hotel investment and operations, project management, pilgrim services, tourism, and restaurants. The company’s headquarters is located in Makkah, Saudi Arabia.\r" +
        "We are committed to close collaboration with our clients, leveraging our technical expertise and professional team to achieve the intended objectives in terms of time, cost, and quality—while focusing on risk reduction and environmental protection through a strong pursuit of sustainable development in the Saudi market in general, and the Makkah market in particular.\r" +
        "Excellence Makers continually strengthens its capabilities and technical capacity by selecting and developing human capital, and by continuously advancing its teams through structured training programs across its workforce.\r" +
        "We take pride in the supportive work environment we provide for our employees, which is directly reflected in the outstanding service we deliver to our valued clients—enabling us to leave a lasting and constructive mark on the Saudi market.";

    try {
        try {
            doc.displayPerformancePreferences.defaultDisplaySettings = ViewDisplaySettings.HIGH_QUALITY;
        } catch (e) {}

        var layerBG = layer("01_Background", true);
        var layerContent = layer("02_Content", false);
        var layerChrome = layer("03_Chrome", false);

        while (doc.pages.length < 4) doc.pages.add(LocationOptions.AT_END);
        var page = doc.pages.item(3);
        page.appliedMaster = masterA();

        clearLabeled(page, "em_style_match");
        clearLabeled(page, "about_us_build");

        // Soft wash
        var wash = addRect(page, ["0mm", "0mm", "238mm", "300mm"], cSoft, layerBG);
        try { wash.transparencySettings.blendingSettings.opacity = 25; } catch (e) {}

        // Gold square bleed top-left
        addRect(page, ["0mm", "-3mm", "14mm", "12mm"], cGold, layerChrome);

        // Separate title frames (avoids invalid paragraph index)
        var arTitle = addTF(page, ["6mm", "16mm", "18mm", "140mm"], layerContent);
        arTitle.contents = "من نحن";
        applyPara(arTitle, stArH1);
        setFont(arTitle.paragraphs.item(0), "Dubai", "Bold");
        try {
            arTitle.paragraphs.item(0).composer = "Adobe World-Ready Paragraph Composer";
            arTitle.paragraphs.item(0).fillColor = cMidBlue;
            arTitle.paragraphs.item(0).pointSize = 26;
        } catch (e) {}

        var enTitle = addTF(page, ["18mm", "16mm", "28mm", "140mm"], layerContent);
        enTitle.contents = "ABOUT US";
        applyPara(enTitle, stEnH1);
        setFont(enTitle.paragraphs.item(0), "Arial", "Bold");
        try {
            enTitle.paragraphs.item(0).fillColor = cGold;
            enTitle.paragraphs.item(0).pointSize = 11;
            enTitle.paragraphs.item(0).tracking = 100;
            enTitle.paragraphs.item(0).capitalization = Capitalization.ALL_CAPS;
        } catch (e) {}

        // Gold rule + diamond
        function goldRule(y, x1, x2) {
            addRect(page, [y + "mm", x1 + "mm", (y + 0.35) + "mm", x2 + "mm"], cGold, layerChrome);
            var d = addRect(page, [(y - 1.1) + "mm", x1 + "mm", (y + 1.5) + "mm", (x1 + 2.6) + "mm"], cGold, layerChrome);
            try { d.rotationAngle = 45; } catch (e) {}
        }
        goldRule(34, 16, 120);

        // Arabic body
        var arBody = addTF(page, ["40mm", "16mm", "130mm", "284mm"], layerContent);
        arBody.contents = AR_BODY;
        applyPara(arBody, stArBody);
        var i;
        for (i = 0; i < arBody.paragraphs.length; i++) {
            setFont(arBody.paragraphs.item(i), "Dubai", "Regular");
            try {
                arBody.paragraphs.item(i).composer = "Adobe World-Ready Paragraph Composer";
                arBody.paragraphs.item(i).paragraphDirection = ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION;
                arBody.paragraphs.item(i).hyphenation = false;
                arBody.paragraphs.item(i).fillColor = cBodyAR;
                arBody.paragraphs.item(i).pointSize = 10.5;
                arBody.paragraphs.item(i).leading = 18;
            } catch (e) {}
        }
        highlightPhrase(arBody, "شركة صناع التميز المحدودة", chBrandAR);
        highlightPhrase(arBody, "صناع التنمية السعودية", chBrandAR);
        highlightPhrase(arBody, "شركة صناع التميز", chBrandAR);

        goldRule(136, 16, 120);

        // English body
        var enBody = addTF(page, ["142mm", "16mm", "228mm", "284mm"], layerContent);
        enBody.contents = EN_BODY;
        applyPara(enBody, stEnBody);
        for (i = 0; i < enBody.paragraphs.length; i++) {
            setFont(enBody.paragraphs.item(i), "Arial", "Regular");
            try {
                enBody.paragraphs.item(i).fillColor = cBodyEN;
                enBody.paragraphs.item(i).pointSize = 9.5;
                enBody.paragraphs.item(i).leading = 15;
            } catch (e) {}
        }
        highlightPhrase(enBody, "Excellence Makers Co. Ltd.", chBrandEN);
        highlightPhrase(enBody, "Saudi Development Makers Group", chBrandEN);
        highlightPhrase(enBody, "Excellence Makers", chBrandEN);

        try {
            if (arBody.overflows) {
                arBody.paragraphs.everyItem().pointSize = 10;
                arBody.paragraphs.everyItem().leading = 16.5;
            }
            if (enBody.overflows) {
                enBody.paragraphs.everyItem().pointSize = 8.75;
                enBody.paragraphs.everyItem().leading = 13.5;
            }
        } catch (e) {}

        try {
            app.activeWindow.activePage = page;
            app.activeWindow.zoom(ZoomOptions.FIT_PAGE);
        } catch (e) {}

        alert("About Us page built in صناع التميز2026 style.\n\nPage 4 ready — send a screenshot.");
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
