/**
 * Excellence Makers Profile 2026 — Twin Axis Document Setup
 * Run in InDesign: File > Scripts > Other Script… (or Scripts panel)
 *
 * Creates a new A4-landscape-like document at 300×260 mm with:
 * - RTL binding
 * - Bilingual 2-column master guides
 * - Brand swatches
 * - Paragraph / Character styles (AR + EN)
 * - Master pages: A-Content, B-Section, C-Cover
 */

#target "InDesign"

(function () {
    if (app.documents.length > 0) {
        var choice = confirm(
            "يوجد مستند مفتوح.\n\nOK = إنشاء ملف جديد Twin Axis\nCancel = إلغاء"
        );
        if (!choice) return;
    }

    // ---------- Units ----------
    var oldHU = app.scriptPreferences.measurementUnit;
    var oldVU = app.scriptPreferences.verticalMeasurementUnits;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;
    app.scriptPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;

    try {
        var doc = app.documents.add();

        // ---------- Document preferences ----------
        with (doc.documentPreferences) {
            pageWidth = "300mm";
            pageHeight = "260mm";
            facingPages = false;
            pagesPerDocument = 8;
            documentBleedTopOffset = "3mm";
            documentBleedBottomOffset = "3mm";
            documentBleedInsideOrLeftOffset = "3mm";
            documentBleedOutsideOrRightOffset = "3mm";
            slugTopOffset = "0mm";
            slugBottomOffset = "0mm";
            slugInsideOrLeftOffset = "0mm";
            slugRightOrOutsideOffset = "0mm";
        }

        // RTL binding for Arabic brochure
        try {
            doc.documentPreferences.pageBinding = PageBindingOptions.RIGHT_TO_LEFT;
        } catch (e) {}

        // ---------- Margins & columns (document default / master) ----------
        // Twin Axis: EN left | gold spine | AR right
        var marginTop = 18;
        var marginBottom = 28; // room for wave footer
        var marginLeft = 16;
        var marginRight = 16;
        var gutter = 10; // space for gold divider

        // ---------- Swatches ----------
        function ensureSwatch(name, c, m, y, k) {
            try {
                return doc.swatches.itemByName(name);
            } catch (e) {
                var s = doc.colors.add();
                s.name = name;
                s.model = ColorModel.PROCESS;
                s.space = ColorSpace.CMYK;
                s.colorValue = [c, m, y, k];
                return s;
            }
        }

        // Brand palette
        var navy = ensureSwatch("EM Navy", 100, 80, 20, 35);
        var gold = ensureSwatch("EM Gold", 15, 30, 90, 5);
        var blueWave = ensureSwatch("EM Wave Blue", 90, 50, 0, 0);
        var bodyGrey = ensureSwatch("EM Body Grey", 0, 0, 0, 70);
        var softGrey = ensureSwatch("EM Soft Grey", 0, 0, 0, 25);
        var white = doc.swatches.itemByName("Paper");
        var black = doc.swatches.itemByName("Black");

        // ---------- Layers ----------
        function ensureLayer(name) {
            try {
                return doc.layers.itemByName(name);
            } catch (e) {
                return doc.layers.add({ name: name });
            }
        }
        var layerBG = ensureLayer("01_Background");
        var layerContent = ensureLayer("02_Content");
        var layerChrome = ensureLayer("03_Chrome"); // footer / page no / divider
        layerChrome.move(LocationOptions.AT_BEGINNING);
        layerContent.move(LocationOptions.AFTER, layerChrome);
        layerBG.move(LocationOptions.AT_END);

        // ---------- Paragraph styles ----------
        function ensurePara(name) {
            try {
                return doc.paragraphStyles.itemByName(name);
            } catch (e) {
                return doc.paragraphStyles.add({ name: name });
            }
        }

        function ensureChar(name) {
            try {
                return doc.characterStyles.itemByName(name);
            } catch (e) {
                return doc.characterStyles.add({ name: name });
            }
        }

        // Prefer installed fonts; fall back safely
        function pickFont(candidates) {
            for (var i = 0; i < candidates.length; i++) {
                try {
                    var f = app.fonts.itemByName(candidates[i]);
                    if (f && f.isValid && f.name) return f;
                } catch (e) {}
            }
            return app.fonts.item(0);
        }

        // Common Arabic / Latin pairs on Saudi machines
        var arFont = pickFont([
            "IBM Plex Sans Arabic\tRegular",
            "IBM Plex Sans Arabic Regular",
            "Noto Naskh Arabic\tRegular",
            "Noto Sans Arabic\tRegular",
            "Adobe Arabic\tRegular",
            "Traditional Arabic\tRegular",
            "Arial\tRegular"
        ]);
        var arFontBold = pickFont([
            "IBM Plex Sans Arabic\tBold",
            "IBM Plex Sans Arabic Bold",
            "Noto Sans Arabic\tBold",
            "Adobe Arabic\tBold",
            "Arial\tBold"
        ]);
        var enFont = pickFont([
            "Montserrat\tRegular",
            "Montserrat Regular",
            "Helvetica Neue\tRegular",
            "Myriad Pro\tRegular",
            "Arial\tRegular"
        ]);
        var enFontMed = pickFont([
            "Montserrat\tMedium",
            "Montserrat Medium",
            "Helvetica Neue\tMedium",
            "Myriad Pro\tSemibold",
            "Arial\tBold"
        ]);

        // --- Arabic styles ---
        var stArTitle = ensurePara("AR / Title Section");
        stArTitle.appliedFont = arFontBold;
        stArTitle.pointSize = 22;
        stArTitle.fillColor = navy;
        stArTitle.justification = Justification.RIGHT_ALIGN;
        stArTitle.spaceAfter = "4mm";
        try { stArTitle.composer = "Adobe World-Ready Paragraph Composer"; } catch (e) {}

        var stArBody = ensurePara("AR / Body");
        stArBody.appliedFont = arFont;
        stArBody.pointSize = 10;
        stArBody.leading = 16;
        stArBody.fillColor = bodyGrey;
        stArBody.justification = Justification.LEFT_JUSTIFIED; // visually justified RTL
        try { stArBody.composer = "Adobe World-Ready Paragraph Composer"; } catch (e) {}
        stArBody.spaceAfter = "3mm";
        try {
            stArBody.paragraphDirection = ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION;
        } catch (e) {}

        var stArName = ensurePara("AR / Name");
        stArName.appliedFont = arFontBold;
        stArName.pointSize = 12;
        stArName.fillColor = navy;
        stArName.justification = Justification.RIGHT_ALIGN;
        try { stArName.composer = "Adobe World-Ready Paragraph Composer"; } catch (e) {}

        // --- English styles ---
        var stEnTitle = ensurePara("EN / Title Section");
        stEnTitle.appliedFont = enFontMed;
        stEnTitle.pointSize = 11;
        stEnTitle.fillColor = gold;
        stEnTitle.justification = Justification.LEFT_ALIGN;
        stEnTitle.tracking = 80;
        stEnTitle.capitalization = Capitalization.ALL_CAPS;
        stEnTitle.spaceAfter = "4mm";

        var stEnBody = ensurePara("EN / Body");
        stEnBody.appliedFont = enFont;
        stEnBody.pointSize = 9.5;
        stEnBody.leading = 14.5;
        stEnBody.fillColor = bodyGrey;
        stEnBody.justification = Justification.LEFT_JUSTIFIED;
        stEnBody.spaceAfter = "3mm";

        var stEnName = ensurePara("EN / Name");
        stEnName.appliedFont = enFontMed;
        stEnName.pointSize = 11;
        stEnName.fillColor = navy;
        stEnName.justification = Justification.LEFT_ALIGN;

        var stFooterURL = ensurePara("Chrome / Footer URL");
        stFooterURL.appliedFont = enFont;
        stFooterURL.pointSize = 8;
        stFooterURL.fillColor = white;
        stFooterURL.justification = Justification.LEFT_ALIGN;

        var stPageNo = ensurePara("Chrome / Page Number");
        stPageNo.appliedFont = enFontMed;
        stPageNo.pointSize = 9;
        stPageNo.fillColor = gold;
        stPageNo.justification = Justification.RIGHT_ALIGN;

        // Character style for company name highlight in AR body
        var chHighlight = ensureChar("AR / Brand Highlight");
        chHighlight.appliedFont = arFontBold;
        chHighlight.fillColor = navy;

        // ---------- Object styles ----------
        function ensureObj(name) {
            try {
                return doc.objectStyles.itemByName(name);
            } catch (e) {
                return doc.objectStyles.add({ name: name });
            }
        }

        var osGoldSquare = ensureObj("Accent / Gold Square");
        try {
            osGoldSquare.enableFill = true;
            osGoldSquare.fillColor = gold;
            osGoldSquare.enableStroke = true;
            osGoldSquare.strokeWeight = 0;
        } catch (e) {}

        var osGoldDivider = ensureObj("Accent / Gold Divider");
        try {
            osGoldDivider.enableStroke = true;
            osGoldDivider.strokeWeight = 0.5;
            osGoldDivider.strokeColor = gold;
            osGoldDivider.enableFill = true;
            osGoldDivider.fillColor = doc.swatches.itemByName("None");
        } catch (e) {}

        // ---------- Masters ----------
        // Rename default master
        var masterA = doc.masterSpreads.item(0);
        masterA.namePrefix = "A";
        masterA.baseName = "Content TwinAxis";

        function setMargins(page) {
            page.marginPreferences.properties = {
                top: marginTop + "mm",
                bottom: marginBottom + "mm",
                left: marginLeft + "mm",
                right: marginRight + "mm",
                columnCount: 2,
                columnGutter: gutter + "mm"
            };
        }

        setMargins(masterA.pages.item(0));

        // Also set for document pages
        for (var p = 0; p < doc.pages.length; p++) {
            setMargins(doc.pages.item(p));
            doc.pages.item(p).appliedMaster = masterA;
        }

        // Draw master chrome on A-Content
        app.activeDocument.activeLayer = layerChrome;

        (function buildContentMaster(ms) {
            var pg = ms.pages.item(0);
            var pw = doc.documentPreferences.pageWidth;
            var ph = doc.documentPreferences.pageHeight;

            // Gold accent square (top-left for EN side visual balance —
            // for Twin Axis put near Arabic title zone on RIGHT)
            var sq = pg.rectangles.add({
                geometricBounds: ["12mm", "276mm", "16mm", "280mm"], // top, left, bottom, right in mm when unit is mm
                fillColor: gold,
                strokeWeight: 0,
                itemLayer: layerChrome
            });
            sq.label = "accent_square";

            // Vertical gold divider at gutter center
            // Page 300mm wide, margins 16+16, gutter 10 → columns ~129mm each
            // Divider at horizontal center of page ≈ 150mm
            var div = pg.rectangles.add({
                geometricBounds: ["18mm", "149.75mm", "225mm", "150.25mm"],
                fillColor: gold,
                strokeWeight: 0,
                itemLayer: layerChrome
            });
            div.label = "gold_spine";

            // Footer wave (simplified solid bar + soft step — replace with real wave later)
            var wave = pg.rectangles.add({
                geometricBounds: ["238mm", "-3mm", "263mm", "303mm"],
                fillColor: navy,
                strokeWeight: 0,
                itemLayer: layerChrome
            });
            wave.label = "footer_wave";

            var waveAccent = pg.rectangles.add({
                geometricBounds: ["238mm", "-3mm", "244mm", "120mm"],
                fillColor: blueWave,
                strokeWeight: 0,
                itemLayer: layerChrome
            });
            waveAccent.label = "footer_wave_accent";

            // URL
            var urlTF = pg.textFrames.add({
                geometricBounds: ["246mm", "16mm", "254mm", "90mm"],
                itemLayer: layerChrome
            });
            urlTF.contents = "www.emakers-sa.com";
            urlTF.paragraphs.item(0).appliedParagraphStyle = stFooterURL;

            // Page number marker
            var pnTF = pg.textFrames.add({
                geometricBounds: ["246mm", "270mm", "254mm", "290mm"],
                itemLayer: layerChrome
            });
            pnTF.contents = "";
            pnTF.insertionPoints.item(0).contents = SpecialCharacters.SECTION_MARKER;
            // Use automatic page number
            pnTF.contents = "| ";
            pnTF.insertionPoints.item(-1).contents = SpecialCharacters.AUTO_PAGE_NUMBER;
            try {
                pnTF.paragraphs.item(0).appliedParagraphStyle = stPageNo;
            } catch (e) {}

            // Primary text frames (threaded optional) — guides only via columns;
            // add placeholder frames for EN (left) and AR (right)
            app.activeDocument.activeLayer = layerContent;

            var enFrame = pg.textFrames.add({
                geometricBounds: ["28mm", "16mm", "220mm", "145mm"],
                itemLayer: layerContent
            });
            enFrame.label = "frame_EN";
            enFrame.contents = "EN / Title\rBody text placeholder — English column (left).";
            try {
                enFrame.paragraphs.item(0).appliedParagraphStyle = stEnTitle;
                if (enFrame.paragraphs.length > 1)
                    enFrame.paragraphs.item(1).appliedParagraphStyle = stEnBody;
            } catch (e) {}

            var arFrame = pg.textFrames.add({
                geometricBounds: ["28mm", "155mm", "220mm", "284mm"],
                itemLayer: layerContent
            });
            arFrame.label = "frame_AR";
            arFrame.contents = "عنوان القسم\rنص عربي تجريبي — العمود الأيمن.";
            try {
                arFrame.paragraphs.item(0).appliedParagraphStyle = stArTitle;
                if (arFrame.paragraphs.length > 1)
                    arFrame.paragraphs.item(1).appliedParagraphStyle = stArBody;
                arFrame.paragraphs.everyItem().justification = Justification.RIGHT_ALIGN;
            } catch (e) {}
        })(masterA);

        // Master B — Section opener (full bleed photo friendly)
        var masterB = doc.masterSpreads.add();
        masterB.namePrefix = "B";
        masterB.baseName = "Section Opener";
        masterB.pages.item(0).marginPreferences.properties = {
            top: "0mm",
            bottom: "0mm",
            left: "0mm",
            right: "0mm",
            columnCount: 1,
            columnGutter: "0mm"
        };

        (function buildSectionMaster(ms) {
            var pg = ms.pages.item(0);
            app.activeDocument.activeLayer = layerBG;

            var photoSlot = pg.rectangles.add({
                geometricBounds: ["-3mm", "-3mm", "263mm", "303mm"],
                fillColor: softGrey,
                strokeWeight: 0,
                itemLayer: layerBG
            });
            photoSlot.label = "section_photo";

            // Dark overlay panel left
            app.activeDocument.activeLayer = layerChrome;
            var overlay = pg.rectangles.add({
                geometricBounds: ["-3mm", "-3mm", "263mm", "110mm"],
                fillColor: navy,
                strokeWeight: 0,
                itemLayer: layerChrome
            });
            try { overlay.transparencySettings.blendingSettings.opacity = 75; } catch (e) {}
            overlay.label = "section_overlay";

            app.activeDocument.activeLayer = layerContent;
            var titleAR = pg.textFrames.add({
                geometricBounds: ["90mm", "16mm", "110mm", "100mm"],
                itemLayer: layerContent
            });
            titleAR.contents = "عنوان القسم";
            titleAR.paragraphs.item(0).appliedParagraphStyle = stArTitle;
            try { titleAR.paragraphs.item(0).fillColor = white; } catch (e) {}

            var titleEN = pg.textFrames.add({
                geometricBounds: ["112mm", "16mm", "122mm", "100mm"],
                itemLayer: layerContent
            });
            titleEN.contents = "SECTION TITLE";
            titleEN.paragraphs.item(0).appliedParagraphStyle = stEnTitle;
        })(masterB);

        // Master C — Cover (empty margins, no chrome)
        var masterC = doc.masterSpreads.add();
        masterC.namePrefix = "C";
        masterC.baseName = "Cover";
        masterC.pages.item(0).marginPreferences.properties = {
            top: "0mm",
            bottom: "0mm",
            left: "0mm",
            right: "0mm",
            columnCount: 1
        };

        // Apply masters to starter pages
        // 1 Cover, 2 Basmala-like blank, 3 Section, 4 Content, 5 Section, 6 Content, 7 Section, 8 Content
        var pages = doc.pages;
        pages.item(0).appliedMaster = masterC;
        pages.item(1).appliedMaster = masterC;
        pages.item(2).appliedMaster = masterB;
        pages.item(3).appliedMaster = masterA;
        pages.item(4).appliedMaster = masterB;
        pages.item(5).appliedMaster = masterA;
        pages.item(6).appliedMaster = masterB;
        pages.item(7).appliedMaster = masterA;

        // ---------- View ----------
        try {
            doc.layoutWindows.item(0).screenMode = ScreenModeOptions.PREVIEW_OFF;
            doc.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
            doc.viewPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;
            doc.viewPreferences.rulerOrigin = RulerOrigin.PAGE_ORIGIN;
        } catch (e) {}

        alert(
            "تم إعداد ملف Twin Axis بنجاح.\n\n" +
            "المقاس: 300 × 260 مم\n" +
            "Bleed: 3 مم\n" +
            "Masters: A Content | B Section | C Cover\n" +
            "ألوان: EM Navy / Gold / Wave Blue\n" +
            "Styles: AR + EN جاهزة\n\n" +
            "احفظ الملف باسم:\nExcellence_Makers_Profile_2026_TwinAxis.indd"
        );
    } finally {
        app.scriptPreferences.measurementUnit = oldHU;
        app.scriptPreferences.verticalMeasurementUnits = oldVU;
    }
})();
