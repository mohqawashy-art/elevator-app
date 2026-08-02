// Place footer wave graphic on Master A (from your .idms snippet)
// Source: ChatGPT Image Jul 4, 2026, 12_47_41 PM copy.png
// Size in snippet ≈ 300 x 48 mm — we place full page width + bleed at bottom

(function () {
    if (!app.documents.length) {
        alert("Open your document first.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    var imgPath = "C:/Users/HOME/Downloads/ChatGPT Image Jul 4, 2026, 12_47_41 PM copy.png";
    var imgFile = new File(imgPath);

    // Fallback: original without "copy"
    if (!imgFile.exists) {
        imgPath = "C:/Users/HOME/Downloads/ChatGPT Image Jul 4, 2026, 12_47_41 PM.png";
        imgFile = new File(imgPath);
    }

    if (!imgFile.exists) {
        alert("Image not found in Downloads:\nChatGPT Image Jul 4, 2026, 12_47_41 PM copy.png");
        app.scriptPreferences.measurementUnit = oldUnit;
        return;
    }

    function getMasterA() {
        for (var i = 0; i < doc.masterSpreads.length; i++) {
            var ms = doc.masterSpreads.item(i);
            if (String(ms.namePrefix) === "A") return ms;
        }
        return doc.masterSpreads.item(0);
    }

    function ensureLayer(name) {
        try {
            var L = doc.layers.itemByName(name);
            if (L.isValid) { L.locked = false; return L; }
        } catch (e) {}
        return doc.layers.add({ name: name });
    }

    try {
        try {
            doc.displayPerformancePreferences.defaultDisplaySettings =
                ViewDisplaySettings.HIGH_QUALITY;
        } catch (e) {}

        var master = getMasterA();
        var page = master.pages.item(0);
        var layerChrome = ensureLayer("03_Chrome");
        doc.activeLayer = layerChrome;

        // Remove previous footer wave from this script
        var items = page.pageItems.everyItem().getElements();
        for (var i = items.length - 1; i >= 0; i--) {
            try {
                if (items[i].label === "footer_wave_graphic") items[i].remove();
            } catch (e) {}
        }

        // Snippet size was ~299 x 48 mm.
        // Place as full-bleed footer band at bottom of 260mm page:
        // height 48mm → from y=212 to y=260 (+bleed to 263)
        var frame = page.rectangles.add();
        frame.geometricBounds = ["212mm", "-3mm", "263mm", "303mm"]; // top, left, bottom, right
        frame.strokeWeight = 0;
        try { frame.strokeColor = doc.swatches.itemByName("None"); } catch (e) {}
        frame.label = "footer_wave_graphic";
        frame.name = "footer_wave_graphic";

        frame.place(imgFile);

        try {
            frame.fit(FitOptions.FILL_PROPORTIONALLY);
            frame.fit(FitOptions.CENTER_CONTENT);
        } catch (e) {}

        try {
            frame.objectDisplaySettings = ViewDisplaySettings.HIGH_QUALITY;
        } catch (e) {}

        // Optional: send to back within layer so logo/URL sit above later
        try { frame.sendToBack(); } catch (e) {}

        try {
            app.activeWindow.activeSpread = master;
            app.activeWindow.zoom(ZoomOptions.FIT_PAGE);
        } catch (e) {}

        alert(
            "Footer wave placed on Master A.\n\n" +
            "Frame: full width + bleed, height ~51mm at bottom\n" +
            "Image: " + imgFile.name + "\n\n" +
            "Next: add URL + page number on top of it."
        );
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
