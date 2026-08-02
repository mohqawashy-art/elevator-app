// Excellence Makers 2026 — Master Pages ONLY (fixed)
// Open document first, then run from Scripts panel.

(function () {
    if (app.documents.length === 0) {
        alert("Open the document first.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    function getSwatch(name) {
        try {
            var s = doc.swatches.itemByName(name);
            if (s.isValid) return s;
        } catch (e) {}
        return null;
    }

    function ensureColor(name, cmyk) {
        var s = getSwatch(name);
        if (s) return s;
        s = doc.colors.add();
        s.name = name;
        s.model = ColorModel.PROCESS;
        s.space = ColorSpace.CMYK;
        s.colorValue = cmyk;
        return s;
    }

    function getPara(name) {
        try {
            var p = doc.paragraphStyles.itemByName(name);
            if (p.isValid) return p;
        } catch (e) {}
        return null;
    }

    function ensureLayer(name) {
        try {
            var L = doc.layers.itemByName(name);
            if (L.isValid) {
                L.locked = false;
                return L;
            }
        } catch (e) {}
        return doc.layers.add({ name: name });
    }

    function clearPageItems(page) {
        while (page.pageItems.length > 0) {
            try { page.pageItems.item(0).remove(); } catch (e) { break; }
        }
    }

    function addRect(page, bounds, fill, layerRef) {
        doc.activeLayer = layerRef;
        var r = page.rectangles.add();
        r.geometricBounds = bounds;
        r.fillColor = fill;
        r.strokeWeight = 0;
        try { r.strokeColor = doc.swatches.itemByName("None"); } catch (e) {}
        return r;
    }

    function addTF(page, bounds, layerRef) {
        doc.activeLayer = layerRef;
        var t = page.textFrames.add();
        t.geometricBounds = bounds;
        return t;
    }

    try {
        var cNavy  = ensureColor("EM / Navy",      [100, 80, 20, 35]);
        var cGold  = ensureColor("EM / Gold",      [15, 30, 90, 5]);
        var cWave  = ensureColor("EM / Wave Blue", [90, 50, 0, 0]);
        var cSoft  = ensureColor("EM / Soft Grey", [0, 0, 0, 12]);
        var cPaper = doc.swatches.itemByName("Paper");
        var cNone  = doc.swatches.itemByName("None");

        var stURL = getPara("21 Chrome / Footer URL");
        var stPN  = getPara("22 Chrome / Page Number");
        var stArH1 = getPara("01 AR / H1 Section");
        var stEnH1 = getPara("11 EN / H1 Section");

        var layerChrome  = ensureLayer("03_Chrome");
        var layerContent = ensureLayer("02_Content");
        var layerBG      = ensureLayer("01_Background");
        layerChrome.locked = false;
        layerContent.locked = false;
        layerBG.locked = false;

        try {
            layerChrome.move(LocationOptions.AT_BEGINNING);
            layerContent.move(LocationOptions.AFTER, layerChrome);
            layerBG.move(LocationOptions.AT_END);
        } catch (eL) {}

        with (doc.documentPreferences) {
            pageWidth = "300mm";
            pageHeight = "260mm";
            documentBleedTopOffset = "3mm";
            documentBleedBottomOffset = "3mm";
            documentBleedInsideOrLeftOffset = "3mm";
            documentBleedOutsideOrRightOffset = "3mm";
        }
        try {
            doc.documentPreferences.pageBinding = PageBindingOptions.RIGHT_TO_LEFT;
        } catch (eB) {}

        // ========== MASTER A — Content ==========
        var masterA = doc.masterSpreads.item(0);
        masterA.namePrefix = "A";
        masterA.baseName = "Content";
        var pgA = masterA.pages.item(0);
        clearPageItems(pgA);

        pgA.marginPreferences.top = "18mm";
        pgA.marginPreferences.bottom = "28mm";
        pgA.marginPreferences.left = "16mm";
        pgA.marginPreferences.right = "16mm";
        pgA.marginPreferences.columnCount = 1;

        // Gold square (top right)
        var sq = addRect(pgA, ["12mm", "280mm", "16mm", "284mm"], cGold, layerChrome);
        sq.name = "accent_gold_square";

        // Footer bar (with bleed)
        var footer = addRect(pgA, ["238mm", "-3mm", "263mm", "303mm"], cNavy, layerChrome);
        footer.name = "footer_bar";

        var wave = addRect(pgA, ["238mm", "-3mm", "245mm", "115mm"], cWave, layerChrome);
        wave.name = "footer_wave_accent";

        var urlTF = addTF(pgA, ["246mm", "16mm", "255mm", "110mm"], layerChrome);
        urlTF.name = "footer_url";
        urlTF.contents = "www.emakers-sa.com";
        if (stURL) {
            try { urlTF.paragraphs.item(0).appliedParagraphStyle = stURL; } catch (eU) {}
        }

        var pnTF = addTF(pgA, ["246mm", "268mm", "255mm", "292mm"], layerChrome);
        pnTF.name = "footer_page_number";
        pnTF.contents = "| ";
        pnTF.insertionPoints.item(-1).contents = SpecialCharacters.AUTO_PAGE_NUMBER;
        if (stPN) {
            try { pnTF.paragraphs.item(0).appliedParagraphStyle = stPN; } catch (eP) {}
        }

        var logo = addRect(pgA, ["226mm", "270mm", "236mm", "292mm"], cNone, layerChrome);
        logo.name = "logo_placeholder";
        logo.strokeWeight = 0.25;
        logo.strokeColor = cGold;

        // ========== MASTER B — Section ==========
        var masterB;
        try {
            if (doc.masterSpreads.length > 1) {
                masterB = doc.masterSpreads.item(1);
            } else {
                masterB = doc.masterSpreads.add();
            }
        } catch (eMB) {
            masterB = doc.masterSpreads.add();
        }
        masterB.namePrefix = "B";
        masterB.baseName = "Section";
        var pgB = masterB.pages.item(0);
        clearPageItems(pgB);

        pgB.marginPreferences.top = "0mm";
        pgB.marginPreferences.bottom = "0mm";
        pgB.marginPreferences.left = "0mm";
        pgB.marginPreferences.right = "0mm";
        pgB.marginPreferences.columnCount = 1;

        // Photo slot — avoid invalid params: create then set bounds
        var photo = addRect(pgB, ["0mm", "0mm", "260mm", "300mm"], cSoft, layerBG);
        try {
            photo.geometricBounds = ["-3mm", "-3mm", "263mm", "303mm"];
        } catch (eBleed) {
            // keep page-sized bounds if bleed bounds rejected
        }
        photo.name = "section_photo_slot";

        var overlay = addRect(pgB, ["0mm", "0mm", "260mm", "100mm"], cNavy, layerChrome);
        try {
            overlay.geometricBounds = ["-3mm", "-3mm", "263mm", "105mm"];
        } catch (eOv) {}
        overlay.name = "section_overlay";
        try { overlay.transparencySettings.blendingSettings.opacity = 70; } catch (eOp) {}

        var rule = addRect(pgB, ["118mm", "16mm", "118.4mm", "90mm"], cGold, layerChrome);
        rule.name = "section_gold_rule";

        var tAR = addTF(pgB, ["88mm", "16mm", "112mm", "100mm"], layerContent);
        tAR.name = "section_title_AR";
        tAR.contents = "عنوان القسم";
        if (stArH1) {
            try {
                tAR.paragraphs.item(0).appliedParagraphStyle = stArH1;
                tAR.paragraphs.item(0).fillColor = cPaper;
            } catch (eTAR) {}
        }

        var tEN = addTF(pgB, ["122mm", "16mm", "132mm", "100mm"], layerContent);
        tEN.name = "section_title_EN";
        tEN.contents = "SECTION TITLE";
        if (stEnH1) {
            try { tEN.paragraphs.item(0).appliedParagraphStyle = stEnH1; } catch (eTEN) {}
        }

        var urlB = addTF(pgB, ["248mm", "100mm", "256mm", "200mm"], layerChrome);
        urlB.contents = "www.emakers-sa.com";
        if (stURL) {
            try {
                urlB.paragraphs.item(0).appliedParagraphStyle = stURL;
                urlB.paragraphs.item(0).justification = Justification.CENTER_ALIGN;
            } catch (eUB) {}
        }

        // ========== MASTER C — Cover ==========
        var masterC;
        try {
            if (doc.masterSpreads.length > 2) {
                masterC = doc.masterSpreads.item(2);
            } else {
                masterC = doc.masterSpreads.add();
            }
        } catch (eMC) {
            masterC = doc.masterSpreads.add();
        }
        masterC.namePrefix = "C";
        masterC.baseName = "Cover";
        var pgC = masterC.pages.item(0);
        clearPageItems(pgC);
        pgC.marginPreferences.top = "0mm";
        pgC.marginPreferences.bottom = "0mm";
        pgC.marginPreferences.left = "0mm";
        pgC.marginPreferences.right = "0mm";
        pgC.marginPreferences.columnCount = 1;

        try {
            if (doc.pages.length >= 1) doc.pages.item(0).appliedMaster = masterC;
            if (doc.pages.length >= 2) doc.pages.item(1).appliedMaster = masterC;
            if (doc.pages.length >= 3) doc.pages.item(2).appliedMaster = masterB;
            if (doc.pages.length >= 4) doc.pages.item(3).appliedMaster = masterA;
        } catch (eApp) {}

        alert(
            "Master pages ready.\n\n" +
            "A-Content : footer + gold square + page no + logo slot\n" +
            "B-Section : photo slot + titles\n" +
            "C-Cover   : empty\n\n" +
            "Next: Place logo on Master A, then build About Us on a page."
        );
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
