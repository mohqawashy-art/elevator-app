// Excellence Makers 2026 — ABOUT US v2 (fixed Arabic fonts + pro layout)
// Open TwinAxis document, run from Scripts panel.

(function () {
    if (app.documents.length === 0) {
        alert("Open the TwinAxis document first.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    function font(name) {
        try {
            var f = app.fonts.itemByName(name);
            if (f.isValid) return f;
        } catch (e) {}
        return null;
    }

    function pickFont(list) {
        var i, f;
        for (i = 0; i < list.length; i++) {
            f = font(list[i]);
            if (f) return f;
        }
        return app.fonts.item(0);
    }

    function ensureColor(name, cmyk) {
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

    function ensurePara(name) {
        try {
            var p = doc.paragraphStyles.itemByName(name);
            if (p.isValid) return p;
        } catch (e) {}
        return doc.paragraphStyles.add({ name: name });
    }

    function layer(name, atEnd) {
        try {
            var L = doc.layers.itemByName(name);
            if (L.isValid) {
                L.locked = false;
                return L;
            }
        } catch (e) {}
        var n = doc.layers.add({ name: name });
        try {
            if (atEnd) n.move(LocationOptions.AT_END);
            else n.move(LocationOptions.AT_BEGINNING);
        } catch (e2) {}
        return n;
    }

    function getMasterA() {
        var i, ms;
        for (i = 0; i < doc.masterSpreads.length; i++) {
            ms = doc.masterSpreads.item(i);
            if (String(ms.namePrefix) === "A") return ms;
        }
        return doc.masterSpreads.item(0);
    }

    function clearLabeled(page, label) {
        var items = page.pageItems.everyItem().getElements();
        var i;
        for (i = items.length - 1; i >= 0; i--) {
            try {
                if (items[i].label === label) items[i].remove();
            } catch (e) {}
        }
    }

    function forceWorldReady(paraStyle) {
        try { paraStyle.composer = "Adobe World-Ready Paragraph Composer"; } catch (e) {}
        try {
            paraStyle.paragraphDirection = ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION;
        } catch (e2) {}
    }

    // Best available fonts on this machine
    var AR_REG = pickFont([
        "IBM Plex Sans Arabic\tRegular",
        "IBMPlexSansArabic-Regular",
        "Dubai\tRegular",
        "Helvetica Neue LT Arabic\tRoman",
        "Frutiger LT Arabic\t55 Roman",
        "Tahoma\tRegular",
        "Arial\tRegular"
    ]);
    var AR_BOLD = pickFont([
        "IBM Plex Sans Arabic\tBold",
        "IBMPlexSansArabic-Bold",
        "Dubai\tBold",
        "Helvetica Neue LT Arabic\tBold",
        "Frutiger LT Arabic\t65 Bold",
        "Tahoma\tBold",
        "Arial\tBold"
    ]);
    var EN_REG = pickFont([
        "Montserrat\tRegular",
        "Montserrat-Regular",
        "Myriad Pro\tRegular",
        "Helvetica Neue\tRegular",
        "Arial\tRegular"
    ]);
    var EN_MED = pickFont([
        "Montserrat\tSemiBold",
        "Montserrat\tMedium",
        "Montserrat-SemiBold",
        "Myriad Pro\tSemibold",
        "Arial\tBold"
    ]);

    var cNavy = ensureColor("EM / Navy", [100, 80, 20, 35]);
    var cGold = ensureColor("EM / Gold", [15, 30, 90, 5]);
    var cBody = ensureColor("EM / Body", [0, 0, 0, 75]);
    var cSoft = ensureColor("EM / Soft Grey", [0, 0, 0, 8]);
    var cPaper = doc.swatches.itemByName("Paper");
    var cNone = doc.swatches.itemByName("None");

    // ---- rebuild critical paragraph styles with REAL fonts ----
    var stArH1 = ensurePara("01 AR / H1 Section");
    stArH1.appliedFont = AR_BOLD;
    stArH1.pointSize = 24;
    stArH1.leading = 30;
    stArH1.fillColor = cNavy;
    stArH1.justification = Justification.RIGHT_ALIGN;
    stArH1.spaceAfter = "2mm";
    forceWorldReady(stArH1);

    var stArBody = ensurePara("03 AR / Body");
    stArBody.appliedFont = AR_REG;
    stArBody.pointSize = 10;
    stArBody.leading = 17;
    stArBody.fillColor = cBody;
    stArBody.justification = Justification.FULLY_JUSTIFIED;
    stArBody.spaceAfter = "3.5mm";
    stArBody.hyphenation = false;
    forceWorldReady(stArBody);

    var stEnH1 = ensurePara("11 EN / H1 Section");
    stEnH1.appliedFont = EN_MED;
    stEnH1.pointSize = 12;
    stEnH1.leading = 14;
    stEnH1.fillColor = cGold;
    stEnH1.justification = Justification.LEFT_ALIGN;
    stEnH1.tracking = 120;
    stEnH1.capitalization = Capitalization.ALL_CAPS;
    stEnH1.spaceAfter = "2mm";

    var stEnBody = ensurePara("13 EN / Body");
    stEnBody.appliedFont = EN_REG;
    stEnBody.pointSize = 9;
    stEnBody.leading = 14.5;
    stEnBody.fillColor = cBody;
    stEnBody.justification = Justification.LEFT_JUSTIFIED;
    stEnBody.spaceAfter = "3.5mm";

    var stURL = ensurePara("21 Chrome / Footer URL");
    stURL.appliedFont = EN_REG;
    stURL.pointSize = 8;
    stURL.fillColor = cPaper;
    stURL.justification = Justification.LEFT_ALIGN;

    var AR_TITLE = "من نحن";
    var EN_TITLE = "ABOUT US";

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
            doc.displayPerformancePreferences.defaultDisplaySettings =
                ViewDisplaySettings.HIGH_QUALITY;
        } catch (eDQ) {}

        var layerBG = layer("01_Background", true);
        var layerContent = layer("02_Content", false);
        var layerChrome = layer("03_Chrome", false);

        while (doc.pages.length < 4) doc.pages.add(LocationOptions.AT_END);
        var page = doc.pages.item(3);
        page.appliedMaster = getMasterA();
        clearLabeled(page, "about_us_build");

        // Soft left wash
        doc.activeLayer = layerBG;
        var wash = page.rectangles.add();
        wash.geometricBounds = ["18mm", "16mm", "230mm", "147mm"];
        wash.fillColor = cSoft;
        wash.strokeWeight = 0;
        try { wash.strokeColor = cNone; } catch (e) {}
        wash.label = "about_us_build";
        try { wash.transparencySettings.blendingSettings.opacity = 40; } catch (e) {}

        // Gold spine
        doc.activeLayer = layerChrome;
        var spine = page.rectangles.add();
        spine.geometricBounds = ["20mm", "149.75mm", "226mm", "150.25mm"];
        spine.fillColor = cGold;
        spine.strokeWeight = 0;
        try { spine.strokeColor = cNone; } catch (e) {}
        spine.label = "about_us_build";

        // Accent squares near titles
        var sqEN = page.rectangles.add();
        sqEN.geometricBounds = ["21mm", "16mm", "25mm", "20mm"];
        sqEN.fillColor = cGold;
        sqEN.strokeWeight = 0;
        sqEN.label = "about_us_build";

        var sqAR = page.rectangles.add();
        sqAR.geometricBounds = ["21mm", "280mm", "25mm", "284mm"];
        sqAR.fillColor = cGold;
        sqAR.strokeWeight = 0;
        sqAR.label = "about_us_build";

        // Thin gold rules under titles
        var ruleEN = page.rectangles.add();
        ruleEN.geometricBounds = ["36mm", "16mm", "36.35mm", "70mm"];
        ruleEN.fillColor = cGold;
        ruleEN.strokeWeight = 0;
        ruleEN.label = "about_us_build";

        var ruleAR = page.rectangles.add();
        ruleAR.geometricBounds = ["36mm", "230mm", "36.35mm", "284mm"];
        ruleAR.fillColor = cGold;
        ruleAR.strokeWeight = 0;
        ruleAR.label = "about_us_build";

        // TEXT
        doc.activeLayer = layerContent;

        var enTitle = page.textFrames.add();
        enTitle.geometricBounds = ["20mm", "23mm", "34mm", "145mm"];
        enTitle.contents = EN_TITLE;
        enTitle.label = "about_us_build";
        enTitle.paragraphs.item(0).appliedParagraphStyle = stEnH1;
        enTitle.paragraphs.item(0).appliedFont = EN_MED;

        var enBody = page.textFrames.add();
        enBody.geometricBounds = ["42mm", "16mm", "228mm", "145mm"];
        enBody.contents = EN_BODY;
        enBody.label = "about_us_build";
        var pi;
        for (pi = 0; pi < enBody.paragraphs.length; pi++) {
            enBody.paragraphs.item(pi).appliedParagraphStyle = stEnBody;
            enBody.paragraphs.item(pi).appliedFont = EN_REG;
        }

        var arTitle = page.textFrames.add();
        arTitle.geometricBounds = ["20mm", "155mm", "34mm", "277mm"];
        arTitle.contents = AR_TITLE;
        arTitle.label = "about_us_build";
        arTitle.paragraphs.item(0).appliedParagraphStyle = stArH1;
        arTitle.paragraphs.item(0).appliedFont = AR_BOLD;
        try {
            arTitle.paragraphs.item(0).composer = "Adobe World-Ready Paragraph Composer";
            arTitle.paragraphs.item(0).justification = Justification.RIGHT_ALIGN;
        } catch (e) {}

        var arBody = page.textFrames.add();
        arBody.geometricBounds = ["42mm", "155mm", "228mm", "284mm"];
        arBody.contents = AR_BODY;
        arBody.label = "about_us_build";
        for (pi = 0; pi < arBody.paragraphs.length; pi++) {
            arBody.paragraphs.item(pi).appliedParagraphStyle = stArBody;
            arBody.paragraphs.item(pi).appliedFont = AR_REG;
            try {
                arBody.paragraphs.item(pi).composer = "Adobe World-Ready Paragraph Composer";
                arBody.paragraphs.item(pi).paragraphDirection =
                    ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION;
                arBody.paragraphs.item(pi).hyphenation = false;
            } catch (e2) {}
        }

        // If overflow, slightly tighten EN
        try {
            if (enBody.overflows) {
                enBody.paragraphs.everyItem().pointSize = 8.5;
                enBody.paragraphs.everyItem().leading = 13.5;
            }
            if (arBody.overflows) {
                arBody.paragraphs.everyItem().pointSize = 9.5;
                arBody.paragraphs.everyItem().leading = 16;
            }
        } catch (eOv) {}

        try {
            app.activeWindow.activePage = page;
            app.activeWindow.zoom(ZoomOptions.FIT_PAGE);
        } catch (eV) {}

        alert(
            "About Us v2 ready (Page 4).\n\n" +
            "AR font: " + AR_REG.name + "\n" +
            "EN font: " + EN_REG.name + "\n\n" +
            "Arabic should display correctly now."
        );
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
