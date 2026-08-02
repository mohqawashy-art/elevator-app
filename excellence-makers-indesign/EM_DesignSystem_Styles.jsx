// Excellence Makers 2026 — Design System ONLY
// Colors + Paragraph Styles + Character Styles
// Run from: Window > Utilities > Scripts > User > EM_DesignSystem_Styles.jsx
// Does NOT build masters — styles first, masters later.

(function () {
    if (app.documents.length === 0) {
        alert("Open your Twin Axis document first, then run this script.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    try {
        // =========================================================
        // 1) COLORS (CMYK)
        // =========================================================
        function ensureColor(name, cmyk) {
            var sw;
            try {
                sw = doc.swatches.itemByName(name);
                if (sw.isValid && sw.name === name) {
                    try {
                        sw.colorValue = cmyk;
                        return sw;
                    } catch (eUp) {
                        return sw;
                    }
                }
            } catch (eFind) {}
            sw = doc.colors.add();
            sw.name = name;
            sw.model = ColorModel.PROCESS;
            sw.space = ColorSpace.CMYK;
            sw.colorValue = cmyk;
            return sw;
        }

        var cNavy     = ensureColor("EM / Navy",        [100, 80, 20, 35]);
        var cGold     = ensureColor("EM / Gold",        [15, 30, 90, 5]);
        var cWave     = ensureColor("EM / Wave Blue",   [90, 50, 0, 0]);
        var cBody     = ensureColor("EM / Body",        [0, 0, 0, 75]);
        var cMuted    = ensureColor("EM / Muted",       [0, 0, 0, 45]);
        var cRule     = ensureColor("EM / Rule Soft",   [0, 0, 0, 15]);
        var cPaper    = doc.swatches.itemByName("Paper");
        var cNone     = doc.swatches.itemByName("None");
        var cBlack    = doc.swatches.itemByName("Black");

        // =========================================================
        // 2) FONTS (pick first available)
        // =========================================================
        function font(name) {
            try {
                var f = app.fonts.itemByName(name);
                if (f.isValid) return f;
            } catch (eF) {}
            return null;
        }

        var AR_REG = font("Adobe Arabic\tRegular") ||
            font("Traditional Arabic\tRegular") ||
            font("Arial\tRegular") ||
            app.fonts.item(0);

        var AR_BOLD = font("Adobe Arabic\tBold") ||
            font("Traditional Arabic\tBold") ||
            font("Arial\tBold") ||
            AR_REG;

        var EN_REG = font("Myriad Pro\tRegular") ||
            font("Helvetica Neue\tRegular") ||
            font("Arial\tRegular") ||
            app.fonts.item(0);

        var EN_MED = font("Myriad Pro\tSemibold") ||
            font("Myriad Pro\tBold") ||
            font("Helvetica Neue\tMedium") ||
            font("Arial\tBold") ||
            EN_REG;

        var EN_LIGHT = font("Myriad Pro\tLight") ||
            font("Helvetica Neue\tLight") ||
            EN_REG;

        // =========================================================
        // 3) PARAGRAPH STYLES
        // =========================================================
        function para(name) {
            try {
                var p = doc.paragraphStyles.itemByName(name);
                if (p.isValid) return p;
            } catch (eP) {}
            return doc.paragraphStyles.add({ name: name });
        }

        function setWorldReady(style) {
            try { style.composer = "Adobe World-Ready Paragraph Composer"; } catch (eC) {}
        }

        // --- Groups via naming convention (InDesign style folders need UI;
        //     we use clear prefixes instead) ---

        // AR titles
        var arH1 = para("01 AR / H1 Section");
        arH1.appliedFont = AR_BOLD;
        arH1.pointSize = 22;
        arH1.leading = 28;
        arH1.fillColor = cNavy;
        arH1.justification = Justification.RIGHT_ALIGN;
        arH1.spaceAfter = "5mm";
        arH1.spaceBefore = "0mm";
        setWorldReady(arH1);
        try { arH1.paragraphDirection = ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION; } catch (eD1) {}

        var arH2 = para("02 AR / H2 Subhead");
        arH2.appliedFont = AR_BOLD;
        arH2.pointSize = 14;
        arH2.leading = 20;
        arH2.fillColor = cNavy;
        arH2.justification = Justification.RIGHT_ALIGN;
        arH2.spaceBefore = "4mm";
        arH2.spaceAfter = "2mm";
        setWorldReady(arH2);
        try { arH2.paragraphDirection = ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION; } catch (eD2) {}

        var arBody = para("03 AR / Body");
        arBody.appliedFont = AR_REG;
        arBody.pointSize = 10;
        arBody.leading = 17;
        arBody.fillColor = cBody;
        arBody.justification = Justification.LEFT_JUSTIFIED;
        arBody.spaceAfter = "3mm";
        arBody.firstLineIndent = "0mm";
        setWorldReady(arBody);
        try { arBody.paragraphDirection = ParagraphDirectionOptions.RIGHT_TO_LEFT_DIRECTION; } catch (eD3) {}
        try {
            arBody.hyphenation = false;
            arBody.justification = Justification.FULLY_JUSTIFIED;
        } catch (eJ) {}

        var arName = para("04 AR / Person Name");
        arName.appliedFont = AR_BOLD;
        arName.pointSize = 12;
        arName.leading = 16;
        arName.fillColor = cNavy;
        arName.justification = Justification.RIGHT_ALIGN;
        arName.spaceBefore = "4mm";
        arName.spaceAfter = "1mm";
        setWorldReady(arName);

        var arRole = para("05 AR / Person Role");
        arRole.appliedFont = AR_REG;
        arRole.pointSize = 9;
        arRole.leading = 12;
        arRole.fillColor = cMuted;
        arRole.justification = Justification.RIGHT_ALIGN;
        arRole.spaceAfter = "2mm";
        setWorldReady(arRole);

        // EN titles
        var enH1 = para("11 EN / H1 Section");
        enH1.appliedFont = EN_MED;
        enH1.pointSize = 11;
        enH1.leading = 14;
        enH1.fillColor = cGold;
        enH1.justification = Justification.LEFT_ALIGN;
        enH1.tracking = 100;
        enH1.capitalization = Capitalization.ALL_CAPS;
        enH1.spaceAfter = "5mm";

        var enH2 = para("12 EN / H2 Subhead");
        enH2.appliedFont = EN_MED;
        enH2.pointSize = 10;
        enH2.leading = 13;
        enH2.fillColor = cNavy;
        enH2.justification = Justification.LEFT_ALIGN;
        enH2.tracking = 40;
        enH2.capitalization = Capitalization.ALL_CAPS;
        enH2.spaceBefore = "4mm";
        enH2.spaceAfter = "2mm";

        var enBody = para("13 EN / Body");
        enBody.appliedFont = EN_REG;
        enBody.pointSize = 9.5;
        enBody.leading = 15;
        enBody.fillColor = cBody;
        enBody.justification = Justification.LEFT_JUSTIFIED;
        enBody.spaceAfter = "3mm";
        try {
            enBody.hyphenation = true;
            enBody.hyphenateAfterFirst = 3;
            enBody.hyphenateBeforeLast = 3;
        } catch (eH) {}

        var enName = para("14 EN / Person Name");
        enName.appliedFont = EN_MED;
        enName.pointSize = 11;
        enName.leading = 14;
        enName.fillColor = cNavy;
        enName.justification = Justification.LEFT_ALIGN;
        enName.spaceBefore = "4mm";
        enName.spaceAfter = "1mm";

        var enRole = para("15 EN / Person Role");
        enRole.appliedFont = EN_REG;
        enRole.pointSize = 8.5;
        enRole.leading = 11;
        enRole.fillColor = cMuted;
        enRole.justification = Justification.LEFT_ALIGN;
        enRole.capitalization = Capitalization.ALL_CAPS;
        enRole.tracking = 40;
        enRole.spaceAfter = "2mm";

        // Chrome
        var footURL = para("21 Chrome / Footer URL");
        footURL.appliedFont = EN_LIGHT;
        footURL.pointSize = 8;
        footURL.leading = 10;
        footURL.fillColor = cPaper;
        footURL.justification = Justification.LEFT_ALIGN;

        var pageNo = para("22 Chrome / Page Number");
        pageNo.appliedFont = EN_MED;
        pageNo.pointSize = 9;
        pageNo.leading = 11;
        pageNo.fillColor = cGold;
        pageNo.justification = Justification.RIGHT_ALIGN;
        pageNo.tracking = 40;

        var caption = para("23 Chrome / Caption");
        caption.appliedFont = EN_REG;
        caption.pointSize = 8;
        caption.leading = 11;
        caption.fillColor = cMuted;
        caption.justification = Justification.LEFT_ALIGN;

        // =========================================================
        // 4) CHARACTER STYLES
        // =========================================================
        function ch(name) {
            try {
                var c = doc.characterStyles.itemByName(name);
                if (c.isValid) return c;
            } catch (eCh) {}
            return doc.characterStyles.add({ name: name });
        }

        var chBrandAR = ch("C01 AR / Brand Bold");
        chBrandAR.appliedFont = AR_BOLD;
        chBrandAR.fillColor = cNavy;

        var chBrandEN = ch("C02 EN / Brand Bold");
        chBrandEN.appliedFont = EN_MED;
        chBrandEN.fillColor = cNavy;

        var chGold = ch("C03 Accent / Gold");
        chGold.fillColor = cGold;

        // =========================================================
        // 5) BASIC OBJECT STYLES (for later master work)
        // =========================================================
        function obj(name) {
            try {
                var o = doc.objectStyles.itemByName(name);
                if (o.isValid) return o;
            } catch (eO) {}
            return doc.objectStyles.add({ name: name });
        }

        var osGoldSq = obj("O01 Accent / Gold Square");
        try {
            osGoldSq.enableFill = true;
            osGoldSq.fillColor = cGold;
            osGoldSq.enableStroke = true;
            osGoldSq.strokeWeight = 0;
            osGoldSq.strokeColor = cNone;
        } catch (eOS1) {}

        var osDivider = obj("O02 Accent / Gold Spine");
        try {
            osDivider.enableFill = true;
            osDivider.fillColor = cGold;
            osDivider.enableStroke = true;
            osDivider.strokeWeight = 0;
        } catch (eOS2) {}

        var osFooter = obj("O03 Chrome / Footer Bar");
        try {
            osFooter.enableFill = true;
            osFooter.fillColor = cNavy;
            osFooter.enableStroke = true;
            osFooter.strokeWeight = 0;
        } catch (eOS3) {}

        alert(
            "Design System applied.\n\n" +
            "SWATCHES:\n" +
            "EM / Navy · Gold · Wave Blue · Body · Muted\n\n" +
            "PARAGRAPH STYLES:\n" +
            "01-05 AR | 11-15 EN | 21-23 Chrome\n\n" +
            "CHARACTER + OBJECT styles ready.\n\n" +
            "NEXT: build Master pages using these styles."
        );
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
