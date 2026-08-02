// Excellence Makers 2026 — Place new brochure COVER art
// File: D:\Excellence Makers Profile 2026\02_links\em-brochure-cover-30x26.jpg
// Open document, go to cover page (or leave on page 1), then run.

(function () {
    if (!app.documents.length) {
        alert("Open the TwinAxis / brochure document first.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    var coverPath = "D:/Excellence Makers Profile 2026/02_links/em-brochure-cover-30x26.jpg";
    var coverFile = new File(coverPath);

    // Fallback: Cursor assets copy if links folder missing
    if (!coverFile.exists) {
        coverPath = "C:/Users/HOME/.cursor/projects/d-New-folder-elevator-app/assets/em-brochure-cover-30x26.jpg";
        coverFile = new File(coverPath);
    }

    if (!coverFile.exists) {
        alert("Cover image not found:\n" + coverPath);
        app.scriptPreferences.measurementUnit = oldUnit;
        return;
    }

    function ensureLayer(name, atEnd) {
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

    function getCoverMaster() {
        var i, ms;
        for (i = 0; i < doc.masterSpreads.length; i++) {
            ms = doc.masterSpreads.item(i);
            if (String(ms.namePrefix) === "C") return ms;
            if (String(ms.baseName).toLowerCase().indexOf("cover") >= 0) return ms;
        }
        return null;
    }

    try {
        try {
            doc.displayPerformancePreferences.defaultDisplaySettings =
                ViewDisplaySettings.HIGH_QUALITY;
        } catch (eD) {}

        while (doc.pages.length < 1) doc.pages.add();

        var page1 = doc.pages.item(0);
        var coverMaster = getCoverMaster();
        if (coverMaster) {
            try { page1.appliedMaster = coverMaster; } catch (eM) {}
        }

        var layerBG = ensureLayer("01_Background", true);
        doc.activeLayer = layerBG;

        // Remove previous cover from this script
        var items = page1.pageItems.everyItem().getElements();
        for (var i = items.length - 1; i >= 0; i--) {
            try {
                if (items[i].label === "cover_art_new" || items[i].label === "cover_art") {
                    items[i].remove();
                }
            } catch (eR) {}
        }

        var frame = page1.rectangles.add();
        // Full page + 3mm bleed (300 x 260)
        frame.geometricBounds = ["-3mm", "-3mm", "263mm", "303mm"];
        frame.strokeWeight = 0;
        try { frame.strokeColor = doc.swatches.itemByName("None"); } catch (eS) {}
        frame.label = "cover_art_new";
        frame.name = "cover_art_new";

        frame.place(coverFile);

        try {
            frame.fit(FitOptions.FILL_PROPORTIONALLY);
            frame.fit(FitOptions.CENTER_CONTENT);
        } catch (eF) {
            try { frame.fit(FitOptions.PROPORTIONALLY); } catch (eF2) {}
        }

        try {
            frame.objectDisplaySettings = ViewDisplaySettings.HIGH_QUALITY;
        } catch (eOD) {}

        // Keep cover behind other page items if any
        try { frame.sendToBack(); } catch (eB) {}

        try {
            app.activeWindow.activePage = page1;
            app.activeWindow.zoom(ZoomOptions.FIT_PAGE);
        } catch (eV) {}

        alert(
            "New cover placed on Page 1.\n\n" +
            "File: em-brochure-cover-30x26.jpg\n" +
            "Frame: full bleed 300x260 + 3mm\n\n" +
            "View > Display Performance > High Quality"
        );
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
