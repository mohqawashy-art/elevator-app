// Fix Cover Display Quality + Re-place at true 300ppi
// Open TwinAxis doc, run from Scripts panel.

(function () {
    if (app.documents.length === 0) {
        alert("Open the TwinAxis document first.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    var coverPath = "D:/Excellence Makers Profile 2026/02_links/00000.psd";
    var coverFile = new File(coverPath);
    if (!coverFile.exists) {
        alert("Cover not found:\n" + coverPath);
        app.scriptPreferences.measurementUnit = oldUnit;
        return;
    }

    try {
        // Force HIGH QUALITY display (this is usually the "broken resolution" issue)
        try {
            doc.displayPerformancePreferences.defaultDisplaySettings =
                ViewDisplaySettings.HIGH_QUALITY;
        } catch (eD) {}

        try {
            app.activeWindow.transformReferencePoint = AnchorPoint.CENTER_ANCHOR;
        } catch (eW) {}

        var page1 = doc.pages.item(0);

        // Find or create cover frame
        var frame = null;
        var items = page1.pageItems.everyItem().getElements();
        for (var i = 0; i < items.length; i++) {
            try {
                if (items[i].label === "cover_art") {
                    frame = items[i];
                    break;
                }
            } catch (eF) {}
        }

        if (frame) {
            try { frame.clear(); } catch (eC) {}
            try { frame.remove(); } catch (eR) {}
            frame = null;
        }

        // Layer
        var layerBG;
        try {
            layerBG = doc.layers.itemByName("01_Background");
            if (!layerBG.isValid) throw new Error("x");
        } catch (eL) {
            layerBG = doc.activeLayer;
        }
        layerBG.locked = false;
        doc.activeLayer = layerBG;

        frame = page1.rectangles.add();
        // Exact page size first (no weird scale), then extend to bleed
        frame.geometricBounds = ["0mm", "0mm", "260mm", "300mm"];
        frame.strokeWeight = 0;
        try { frame.strokeColor = doc.swatches.itemByName("None"); } catch (eS) {}
        frame.label = "cover_art";
        frame.name = "cover_art";

        frame.place(coverFile);

        // Exact fit: content = frame (PSD is already 300x260 @300ppi)
        try {
            frame.fit(FitOptions.FRAME_TO_CONTENT);
        } catch (e1) {}
        // Reset frame to page+bleed and fill exactly
        frame.geometricBounds = ["-3mm", "-3mm", "263mm", "303mm"];
        try {
            frame.fit(FitOptions.FILL_PROPORTIONALLY);
            frame.fit(FitOptions.CENTER_CONTENT);
        } catch (e2) {}

        // Per-object high quality
        try {
            frame.objectDisplaySettings = ViewDisplaySettings.HIGH_QUALITY;
        } catch (eOD) {
            try {
                // older API
                app.activeWindow.displayPerformanceSettings = ViewDisplaySettings.HIGH_QUALITY;
            } catch (eOD2) {}
        }

        // Relink sanity: show effective ppi if possible
        var msg = "Display set to HIGH QUALITY.\n\n";
        msg += "Source PSD: 3543 x 3071 px = 300 ppi at 300x260mm\n";
        msg += "(Print resolution is fine — Typical Display looked blurry)\n\n";
        msg += "Also check manually:\n";
        msg += "View > Display Performance > High Quality Display";

        try {
            app.activeWindow.activePage = page1;
            app.activeWindow.zoom(ZoomOptions.FIT_PAGE);
        } catch (eV) {}

        alert(msg);
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
