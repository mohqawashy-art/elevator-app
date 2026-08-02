// Excellence Makers 2026 — Cover graphic (wave + gold filaments)
// Matches the white cover look: navy wave + gold top edge + left/right gold rays
// Run on Cover page or Master C. Page size assumed 300 x 260 mm.

(function () {
    if (!app.documents.length) {
        alert("Open the document first.");
        return;
    }

    var doc = app.activeDocument;
    var oldUnit = app.scriptPreferences.measurementUnit;
    app.scriptPreferences.measurementUnit = MeasurementUnits.MILLIMETERS;

    function swatch(name, cmyk) {
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

    function page() {
        try {
            if (app.activeWindow.activePage) return app.activeWindow.activePage;
        } catch (e) {}
        return doc.pages.item(0);
    }

    function clearLabel(pg, label) {
        var items = pg.pageItems.everyItem().getElements();
        for (var i = items.length - 1; i >= 0; i--) {
            try {
                if (items[i].label === label) items[i].remove();
            } catch (e) {}
        }
    }

    function q(a, b, c, t) {
        var u = 1 - t;
        return u * u * a + 2 * u * t * b + t * t * c;
    }

    function sampleQuad(p0, p1, p2, n) {
        var pts = [];
        for (var i = 0; i <= n; i++) {
            var t = i / n;
            pts.push([
                q(p0[0], p1[0], p2[0], t),
                q(p0[1], p1[1], p2[1], t)
            ]);
        }
        return pts;
    }

    function openStroke(pg, lay, color, pts, weight, opacity) {
        doc.activeLayer = lay;
        var poly = pg.polygons.add();
        poly.fillColor = doc.swatches.itemByName("None");
        poly.strokeColor = color;
        poly.strokeWeight = weight;
        try { poly.endCap = EndCap.ROUND_END_CAP; } catch (e) {}
        try { poly.endJoin = EndJoin.ROUND_END_JOIN; } catch (e2) {}
        try { poly.paths.item(0).pathType = PathType.OPEN_PATH; } catch (e3) {}
        try {
            poly.paths.item(0).entirePath = pts;
        } catch (e4) {
            var path = poly.paths.item(0);
            while (path.pathPoints.length < pts.length) path.pathPoints.add();
            for (var i = 0; i < pts.length; i++) {
                path.pathPoints.item(i).anchor = pts[i];
                path.pathPoints.item(i).leftDirection = pts[i];
                path.pathPoints.item(i).rightDirection = pts[i];
            }
        }
        poly.label = "em_cover_art";
        try {
            if (opacity < 100)
                poly.transparencySettings.blendingSettings.opacity = opacity;
        } catch (e5) {}
        return poly;
    }

    function closedFill(pg, lay, fill, pts) {
        doc.activeLayer = lay;
        var poly = pg.polygons.add();
        poly.fillColor = fill;
        poly.strokeWeight = 0;
        try { poly.strokeColor = doc.swatches.itemByName("None"); } catch (e) {}
        try { poly.paths.item(0).pathType = PathType.CLOSED_PATH; } catch (e2) {}
        try {
            poly.paths.item(0).entirePath = pts;
        } catch (e3) {
            var path = poly.paths.item(0);
            while (path.pathPoints.length < pts.length) path.pathPoints.add();
            for (var i = 0; i < pts.length; i++) {
                path.pathPoints.item(i).anchor = pts[i];
                path.pathPoints.item(i).leftDirection = pts[i];
                path.pathPoints.item(i).rightDirection = pts[i];
            }
        }
        poly.label = "em_cover_art";
        return poly;
    }

    try {
        var pg = page();
        var pw = 300, ph = 260;
        try {
            pw = parseFloat(doc.documentPreferences.pageWidth);
            ph = parseFloat(doc.documentPreferences.pageHeight);
        } catch (e) {}

        var cNavy = swatch("EM Navy", [100, 80, 20, 35]);
        var cWave = swatch("EM Wave", [90, 50, 0, 0]);
        var cGold = swatch("EM Gold", [15, 30, 90, 5]);
        var cSoft = swatch("EM Soft Grey", [0, 0, 0, 18]);

        var layBG = layer("01_Background", true);
        var layArt = layer("02_Content", false);
        var layChrome = layer("03_Chrome", false);

        clearLabel(pg, "em_cover_art");

        // ---------- WAVE top edge curve (control points) ----------
        // Smooth S-curve across page bottom (like reference)
        var edge = sampleQuad(
            [-3, ph - 78],
            [pw * 0.38, ph - 52],
            [pw + 3, ph - 88],
            36
        );
        // Second segment for right lift
        var edge2 = sampleQuad(
            [pw * 0.55, ph - 70],
            [pw * 0.78, ph - 100],
            [pw + 3, ph - 72],
            24
        );
        // Blend: use custom polyline for nicer wave
        var topEdge = [];
        var n = 40;
        for (var i = 0; i <= n; i++) {
            var t = i / n;
            var x = -3 + t * (pw + 6);
            // wave function: base + sine-like undulation
            var y =
                ph -
                70 +
                Math.sin(t * Math.PI * 1.15) * 22 -
                Math.sin(t * Math.PI * 2.1) * 10 +
                (t > 0.55 ? -(t - 0.55) * 28 : 0);
            topEdge.push([x, y]);
        }

        // Closed wave body: topEdge + bottom-right + bottom-left
        var wavePts = topEdge.slice(0);
        wavePts.push([pw + 3, ph + 3]);
        wavePts.push([-3, ph + 3]);

        var wave = closedFill(pg, layBG, cNavy, wavePts);
        wave.name = "cover_wave";

        // Soft inner band (lighter blue accent strip under gold)
        var innerEdge = [];
        for (i = 0; i < topEdge.length; i++) {
            innerEdge.push([topEdge[i][0], topEdge[i][1] + 6]);
        }
        var bandPts = topEdge.slice(0);
        for (i = innerEdge.length - 1; i >= 0; i--) bandPts.push(innerEdge[i]);
        var band = closedFill(pg, layBG, cWave, bandPts);
        band.name = "cover_wave_band";
        try { band.transparencySettings.blendingSettings.opacity = 55; } catch (e) {}

        // Gold stroke on top edge only
        var goldLine = openStroke(pg, layChrome, cGold, topEdge, 1.25, 100);
        goldLine.name = "cover_wave_gold_edge";

        // ---------- LEFT gold filaments (fan up from bottom-left) ----------
        var leftCount = 16;
        for (i = 0; i < leftCount; i++) {
            var u = i / (leftCount - 1);
            var p0 = [-8 + u * 6, ph - 10 - u * 4];
            var p1 = [40 + u * 35, ph - 90 - u * 40];
            var p2 = [90 + u * 95, 35 + u * 55];
            var pts = sampleQuad(p0, p1, p2, 26);
            openStroke(
                pg,
                layArt,
                cGold,
                pts,
                0.3 + (1 - u) * 0.25,
                45 + (1 - u) * 40
            );
        }

        // ---------- RIGHT gold filaments ----------
        var rightCount = 14;
        for (i = 0; i < rightCount; i++) {
            u = i / (rightCount - 1);
            p0 = [pw + 6 - u * 5, ph - 12 - u * 3];
            p1 = [pw - 50 - u * 40, ph - 95 - u * 35];
            p2 = [pw - 100 - u * 80, 40 + u * 50];
            pts = sampleQuad(p0, p1, p2, 26);
            openStroke(
                pg,
                layArt,
                cGold,
                pts,
                0.3 + (1 - u) * 0.22,
                40 + (1 - u) * 40
            );
        }

        // ---------- Soft gray filaments (behind, fewer) ----------
        var grayCount = 8;
        for (i = 0; i < grayCount; i++) {
            u = i / (grayCount - 1);
            p0 = [20 + u * 30, ph - 20];
            p1 = [100 + u * 60, ph - 80 - u * 20];
            p2 = [180 + u * 70, 80 + u * 40];
            pts = sampleQuad(p0, p1, p2, 22);
            openStroke(pg, layArt, cSoft, pts, 0.35, 35);
        }

        // Small gold accent square top-right (optional brand mark)
        doc.activeLayer = layChrome;
        var sq = pg.rectangles.add();
        sq.geometricBounds = ["0mm", pw - 14 + "mm", "12mm", pw + 3 + "mm"];
        sq.fillColor = cGold;
        sq.strokeWeight = 0;
        sq.label = "em_cover_art";
        sq.name = "cover_gold_tab";

        try {
            app.activeWindow.activePage = pg;
            app.activeWindow.zoom(ZoomOptions.FIT_PAGE);
        } catch (eV) {}

        alert(
            "Cover graphic built.\n\n" +
            "• Navy wave + blue band\n" +
            "• Gold edge on wave\n" +
            "• Gold filaments L/R\n" +
            "• Soft gray accents\n" +
            "• Gold tab top-right\n\n" +
            "Add logo/text on top. Re-run replaces previous cover art."
        );
    } catch (err) {
        alert("Error:\n" + err.message + "\nLine: " + err.line);
    } finally {
        app.scriptPreferences.measurementUnit = oldUnit;
    }
})();
