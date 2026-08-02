// Twin Axis Document Setup - Excellence Makers 2026
// Run ONLY from: Window > Utilities > Scripts > double-click this file
// Do NOT use File > Open on this .jsx file

(function () {
    if (app.documents.length && !confirm("Create a NEW Twin Axis document?")) {
        return;
    }

    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    try {
        var doc = app.documents.add();

        with (doc.documentPreferences) {
            pageWidth = "300mm";
            pageHeight = "260mm";
            facingPages = false;
            pagesPerDocument = 8;
            documentBleedTopOffset = "3mm";
            documentBleedBottomOffset = "3mm";
            documentBleedInsideOrLeftOffset = "3mm";
            documentBleedOutsideOrRightOffset = "3mm";
        }

        try {
            doc.documentPreferences.pageBinding = PageBindingOptions.RIGHT_TO_LEFT;
        } catch (e1) {}

        function addSwatch(name, c, m, y, k) {
            var s;
            try {
                s = doc.swatches.itemByName(name);
                if (s.isValid) return s;
            } catch (e2) {}
            s = doc.colors.add();
            s.name = name;
            s.model = ColorModel.PROCESS;
            s.space = ColorSpace.CMYK;
            s.colorValue = [c, m, y, k];
            return s;
        }

        var navy = addSwatch("EM Navy", 100, 80, 20, 35);
        var gold = addSwatch("EM Gold", 15, 30, 90, 5);
        var wave = addSwatch("EM Wave Blue", 90, 50, 0, 0);
        var grey = addSwatch("EM Body Grey", 0, 0, 0, 70);
        var soft = addSwatch("EM Soft Grey", 0, 0, 0, 25);
        var paper = doc.swatches.itemByName("Paper");

        function addLayer(name) {
            try {
                var L = doc.layers.itemByName(name);
                if (L.isValid) return L;
            } catch (e3) {}
            return doc.layers.add({ name: name });
        }

        var layerChrome = addLayer("03_Chrome");
        var layerContent = addLayer("02_Content");
        var layerBG = addLayer("01_Background");
        try {
            layerChrome.move(LocationOptions.AT_BEGINNING);
            layerContent.move(LocationOptions.AFTER, layerChrome);
            layerBG.move(LocationOptions.AT_END);
        } catch (e4) {}

        function addPara(name) {
            try {
                var ps = doc.paragraphStyles.itemByName(name);
                if (ps.isValid) return ps;
            } catch (e5) {}
            return doc.paragraphStyles.add({ name: name });
        }

        function fontOrNull(n) {
            try {
                var f = app.fonts.itemByName(n);
                if (f.isValid) return f;
            } catch (e6) {}
            return null;
        }

        var arReg = fontOrNull("Adobe Arabic\tRegular") ||
            fontOrNull("Arial\tRegular") ||
            app.fonts.item(0);
        var arBold = fontOrNull("Adobe Arabic\tBold") ||
            fontOrNull("Arial\tBold") ||
            arReg;
        var enReg = fontOrNull("Myriad Pro\tRegular") ||
            fontOrNull("Arial\tRegular") ||
            app.fonts.item(0);
        var enMed = fontOrNull("Myriad Pro\tSemibold") ||
            fontOrNull("Arial\tBold") ||
            enReg;

        var stArTitle = addPara("AR / Title Section");
        stArTitle.appliedFont = arBold;
        stArTitle.pointSize = 22;
        stArTitle.fillColor = navy;
        stArTitle.justification = Justification.RIGHT_ALIGN;
        stArTitle.spaceAfter = "4mm";
        try { stArTitle.composer = "Adobe World-Ready Paragraph Composer"; } catch (e7) {}

        var stArBody = addPara("AR / Body");
        stArBody.appliedFont = arReg;
        stArBody.pointSize = 10;
        stArBody.leading = 16;
        stArBody.fillColor = grey;
        stArBody.justification = Justification.LEFT_JUSTIFIED;
        stArBody.spaceAfter = "3mm";
        try { stArBody.composer = "Adobe World-Ready Paragraph Composer"; } catch (e8) {}
        try {
            stArBody.paragraphDirection = ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION;
        } catch (e9) {}

        var stEnTitle = addPara("EN / Title Section");
        stEnTitle.appliedFont = enMed;
        stEnTitle.pointSize = 11;
        stEnTitle.fillColor = gold;
        stEnTitle.justification = Justification.LEFT_ALIGN;
        stEnTitle.tracking = 80;
        stEnTitle.capitalization = Capitalization.ALL_CAPS;
        stEnTitle.spaceAfter = "4mm";

        var stEnBody = addPara("EN / Body");
        stEnBody.appliedFont = enReg;
        stEnBody.pointSize = 9.5;
        stEnBody.leading = 14.5;
        stEnBody.fillColor = grey;
        stEnBody.justification = Justification.LEFT_JUSTIFIED;
        stEnBody.spaceAfter = "3mm";

        var stURL = addPara("Chrome / Footer URL");
        stURL.appliedFont = enReg;
        stURL.pointSize = 8;
        stURL.fillColor = paper;
        stURL.justification = Justification.LEFT_ALIGN;

        var stPN = addPara("Chrome / Page Number");
        stPN.appliedFont = enMed;
        stPN.pointSize = 9;
        stPN.fillColor = gold;
        stPN.justification = Justification.RIGHT_ALIGN;

        var marginTop = 18;
        var marginBottom = 28;
        var marginSide = 16;
        var gutter = 10;

        function setPageGrid(pg) {
            pg.marginPreferences.properties = {
                top: marginTop + "mm",
                bottom: marginBottom + "mm",
                left: marginSide + "mm",
                right: marginSide + "mm",
                columnCount: 2,
                columnGutter: gutter + "mm"
            };
        }

        var masterA = doc.masterSpreads.item(0);
        masterA.namePrefix = "A";
        masterA.baseName = "Content TwinAxis";
        setPageGrid(masterA.pages.item(0));

        var i;
        for (i = 0; i < doc.pages.length; i++) {
            setPageGrid(doc.pages.item(i));
            doc.pages.item(i).appliedMaster = masterA;
        }

        // Master A chrome
        var pgA = masterA.pages.item(0);
        doc.activeLayer = layerChrome;

        pgA.rectangles.add({
            geometricBounds: ["12mm", "276mm", "16mm", "280mm"],
            fillColor: gold,
            strokeWeight: 0,
            itemLayer: layerChrome
        });

        pgA.rectangles.add({
            geometricBounds: ["18mm", "149.75mm", "225mm", "150.25mm"],
            fillColor: gold,
            strokeWeight: 0,
            itemLayer: layerChrome
        });

        pgA.rectangles.add({
            geometricBounds: ["238mm", "-3mm", "263mm", "303mm"],
            fillColor: navy,
            strokeWeight: 0,
            itemLayer: layerChrome
        });

        pgA.rectangles.add({
            geometricBounds: ["238mm", "-3mm", "244mm", "120mm"],
            fillColor: wave,
            strokeWeight: 0,
            itemLayer: layerChrome
        });

        var urlBox = pgA.textFrames.add({
            geometricBounds: ["246mm", "16mm", "254mm", "100mm"],
            itemLayer: layerChrome
        });
        urlBox.contents = "www.emakers-sa.com";
        urlBox.paragraphs.item(0).appliedParagraphStyle = stURL;

        var pnBox = pgA.textFrames.add({
            geometricBounds: ["246mm", "265mm", "254mm", "290mm"],
            itemLayer: layerChrome
        });
        pnBox.contents = "| ";
        pnBox.insertionPoints.item(-1).contents = SpecialCharacters.AUTO_PAGE_NUMBER;
        try { pnBox.paragraphs.item(0).appliedParagraphStyle = stPN; } catch (e10) {}

        doc.activeLayer = layerContent;

        var enBox = pgA.textFrames.add({
            geometricBounds: ["28mm", "16mm", "220mm", "145mm"],
            itemLayer: layerContent
        });
        enBox.contents = "ABOUT US\rEnglish body placeholder (left column).";
        try {
            enBox.paragraphs.item(0).appliedParagraphStyle = stEnTitle;
            enBox.paragraphs.item(1).appliedParagraphStyle = stEnBody;
        } catch (e11) {}

        var arBox = pgA.textFrames.add({
            geometricBounds: ["28mm", "155mm", "220mm", "284mm"],
            itemLayer: layerContent
        });
        arBox.contents = "من نحن\rنص عربي تجريبي (العمود الأيمن).";
        try {
            arBox.paragraphs.item(0).appliedParagraphStyle = stArTitle;
            arBox.paragraphs.item(1).appliedParagraphStyle = stArBody;
        } catch (e12) {}

        // Master B - Section
        var masterB = doc.masterSpreads.add();
        masterB.namePrefix = "B";
        masterB.baseName = "Section Opener";
        masterB.pages.item(0).marginPreferences.properties = {
            top: "0mm",
            bottom: "0mm",
            left: "0mm",
            right: "0mm",
            columnCount: 1
        };

        var pgB = masterB.pages.item(0);
        doc.activeLayer = layerBG;
        pgB.rectangles.add({
            geometricBounds: ["-3mm", "-3mm", "263mm", "303mm"],
            fillColor: soft,
            strokeWeight: 0,
            itemLayer: layerBG
        });

        doc.activeLayer = layerChrome;
        var ov = pgB.rectangles.add({
            geometricBounds: ["-3mm", "-3mm", "263mm", "110mm"],
            fillColor: navy,
            strokeWeight: 0,
            itemLayer: layerChrome
        });
        try { ov.transparencySettings.blendingSettings.opacity = 75; } catch (e13) {}

        doc.activeLayer = layerContent;
        var tAR = pgB.textFrames.add({
            geometricBounds: ["90mm", "16mm", "110mm", "100mm"],
            itemLayer: layerContent
        });
        tAR.contents = "عنوان القسم";
        tAR.paragraphs.item(0).appliedParagraphStyle = stArTitle;
        try { tAR.paragraphs.item(0).fillColor = paper; } catch (e14) {}

        var tEN = pgB.textFrames.add({
            geometricBounds: ["112mm", "16mm", "122mm", "100mm"],
            itemLayer: layerContent
        });
        tEN.contents = "SECTION TITLE";
        tEN.paragraphs.item(0).appliedParagraphStyle = stEnTitle;

        // Master C - Cover
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

        doc.pages.item(0).appliedMaster = masterC;
        doc.pages.item(1).appliedMaster = masterC;
        doc.pages.item(2).appliedMaster = masterB;
        doc.pages.item(3).appliedMaster = masterA;
        doc.pages.item(4).appliedMaster = masterB;
        doc.pages.item(5).appliedMaster = masterA;
        doc.pages.item(6).appliedMaster = masterB;
        doc.pages.item(7).appliedMaster = masterA;

        try {
            doc.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.MILLIMETERS;
            doc.viewPreferences.verticalMeasurementUnits = MeasurementUnits.MILLIMETERS;
            doc.viewPreferences.rulerOrigin = RulerOrigin.PAGE_ORIGIN;
        } catch (e15) {}

        alert(
            "Twin Axis setup done.\n\n" +
            "Size: 300 x 260 mm\n" +
            "Bleed: 3 mm\n" +
            "Masters: A Content | B Section | C Cover\n\n" +
            "Save as:\nExcellence_Makers_Profile_2026_TwinAxis.indd"
        );
    } catch (err) {
        alert("Script error:\n" + err.message);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
