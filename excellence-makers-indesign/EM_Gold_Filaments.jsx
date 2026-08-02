// Excellence Makers — Golden filament curves (fan from top-left)
// Run on the active page or Master. Selection optional.
// Creates thin gold open-path curves like the brochure accent lines.

(function () {
    if (!app.documents.length) {
        alert("Open a document first.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    function ensureGold() {
        try {
            var s = doc.swatches.itemByName("EM Gold");
            if (s.isValid) return s;
        } catch (e) {}
        var c = doc.colors.add();
        c.name = "EM Gold";
        c.model = ColorModel.PROCESS;
        c.space = ColorSpace.CMYK;
        c.colorValue = [15, 30, 90, 5];
        return c;
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

    function getTargetPage() {
        try {
            if (app.activeWindow.activePage) return app.activeWindow.activePage;
        } catch (e) {}
        try {
            if (app.activeWindow.activeSpread.pages.length)
                return app.activeWindow.activeSpread.pages.item(0);
        } catch (e2) {}
        return doc.pages.item(0);
    }

    // Quadratic point
    function q(a, b, c, t) {
        var u = 1 - t;
        return u * u * a + 2 * u * t * b + t * t * c;
    }

    // Build open curved path as polygon with bezier-ish sampled points
    function addCurve(page, layerRef, gold, p0, p1, p2, weight, opacity) {
        doc.activeLayer = layerRef;

        // Sample curve into smooth polyline (InDesign-friendly)
        var samples = 28;
        var pts = [];
        var t, x, y, i;
        for (i = 0; i <= samples; i++) {
            t = i / samples;
            x = q(p0[0], p1[0], p2[0], t);
            y = q(p0[1], p1[1], p2[1], t);
            pts.push([y + "mm", x + "mm"]); // geometricBounds uses [y,x] later differently
        }

        // Use graphicLine for open stroke paths
        var gl = page.graphicLines.add();
        gl.strokeWeight = weight;
        gl.strokeColor = gold;
        gl.strokeTint = 100;
        try { gl.endCap = EndCap.ROUND_END_CAP; } catch (e) {}
        try { gl.endJoin = EndJoin.ROUND_END_JOIN; } catch (e2) {}
        try { gl.fillColor = doc.swatches.itemByName("None"); } catch (e3) {}

        // graphicLine has 2 points by default — convert path to multi-point
        // Approach: use polygon open path instead for many points
        gl.remove();

        var poly = page.polygons.add();
        poly.fillColor = doc.swatches.itemByName("None");
        poly.strokeColor = gold;
        poly.strokeWeight = weight;
        try { poly.endCap = EndCap.ROUND_END_CAP; } catch (e4) {}
        try { poly.endJoin = EndJoin.ROUND_END_JOIN; } catch (e5) {}

        // entirePath in page coordinates as [x, y] in current units (mm)
        var entire = [];
        for (i = 0; i <= samples; i++) {
            t = i / samples;
            x = q(p0[0], p1[0], p2[0], t);
            y = q(p0[1], p1[1], p2[1], t);
            entire.push([x, y]);
        }

        try {
            poly.paths.item(0).pathType = PathType.OPEN_PATH;
        } catch (e6) {}

        try {
            poly.paths.item(0).entirePath = entire;
        } catch (e7) {
            // fallback: set anchors one by one
            try {
                var path = poly.paths.item(0);
                // ensure enough points
                while (path.pathPoints.length < entire.length) {
                    path.pathPoints.add();
                }
                for (i = 0; i < entire.length; i++) {
                    path.pathPoints.item(i).anchor = entire[i];
                    path.pathPoints.item(i).leftDirection = entire[i];
                    path.pathPoints.item(i).rightDirection = entire[i];
                    try {
                        path.pathPoints.item(i).pointType = PointType.SMOOTH;
                    } catch (e8) {}
                }
            } catch (e9) {
                poly.remove();
                throw e9;
            }
        }

        poly.label = "em_gold_filaments";
        poly.name = "gold_filament";

        try {
            if (opacity < 100) {
                poly.transparencySettings.blendingSettings.opacity = opacity;
            }
        } catch (eOp) {}

        return poly;
    }

    try {
        var page = getTargetPage();
        var gold = ensureGold();
        var layer = ensureLayer("02_Content");
        doc.activeLayer = layer;

        // Clear previous filaments from this script
        var items = page.pageItems.everyItem().getElements();
        for (var r = items.length - 1; r >= 0; r--) {
            try {
                if (items[r].label === "em_gold_filaments") items[r].remove();
            } catch (eR) {}
        }

        // Page size in mm
        var pw = 300;
        var ph = 260;
        try {
            pw = parseFloat(doc.documentPreferences.pageWidth);
            ph = parseFloat(doc.documentPreferences.pageHeight);
        } catch (eS) {}

        /*
         * Fan of curves: start clustered top-left, sweep down-right,
         * ending spaced along lower area (matches reference look).
         * Coordinates: [x_mm, y_mm] from top-left of page.
         */
        var count = 12;
        var i, t, startX, startY, midX, midY, endX, endY, wgt, opac;

        for (i = 0; i < count; i++) {
            t = i / (count - 1); // 0..1

            // Start: top-left cluster
            startX = 8 + t * 10;
            startY = 18 + t * 28;

            // Control: pulls curve into a soft arc
            midX = 55 + t * 70;
            midY = 90 + t * 55;

            // End: fan out toward bottom / mid-lower
            endX = 95 + t * 150;
            endY = ph - 42 - (1 - t) * 8; // near footer band

            // Thinner + slightly lighter toward outer filaments
            wgt = 0.35 + (1 - t) * 0.25; // ~0.35–0.60 pt
            opac = 55 + (1 - t) * 35;     // outer more visible

            addCurve(
                page,
                layer,
                gold,
                [startX, startY],
                [midX, midY],
                [endX, endY],
                wgt,
                opac
            );
        }

        try {
            app.activeWindow.activePage = page;
            app.activeWindow.zoom(ZoomOptions.FIT_PAGE);
        } catch (eV) {}

        alert(
            "Golden filaments created: " + count + " curves.\n\n" +
            "Label: em_gold_filaments\n" +
            "Color: EM Gold\n\n" +
            "Tip: select all filaments and Group (Ctrl+G).\n" +
            "Re-run script to regenerate."
        );
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
