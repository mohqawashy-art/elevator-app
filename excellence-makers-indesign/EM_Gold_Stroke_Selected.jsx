// Apply EM Gold stroke to selected frame(s) — for wave polygon etc.
// 1) Select the wave frame in InDesign
// 2) Run this script from Scripts panel

(function () {
    if (!app.documents.length) {
        alert("Open a document first.");
        return;
    }
    if (!app.selection.length) {
        alert("Select the wave frame first, then run the script.");
        return;
    }

    var doc = app.activeDocument;

    function getGold() {
        try {
            var s = doc.swatches.itemByName("EM Gold");
            if (s.isValid) return s;
        } catch (e) {}
        // create if missing
        var c = doc.colors.add();
        c.name = "EM Gold";
        c.model = ColorModel.PROCESS;
        c.space = ColorSpace.CMYK;
        c.colorValue = [15, 30, 90, 5];
        return c;
    }

    var gold = getGold();
    var n = 0;
    var i, item;

    for (i = 0; i < app.selection.length; i++) {
        item = app.selection[i];
        try {
            // rectangles, polygons, ovals, graphic frames
            if (item.hasOwnProperty("strokeColor") || item.constructor.name) {
                item.strokeWeight = 2; // pt — change if you want thicker
                item.strokeColor = gold;
                try {
                    item.strokeAlignment = StrokeAlignment.OUTSIDE_ALIGNMENT;
                } catch (eA) {
                    try { item.strokeAlignment = StrokeAlignment.CENTER_ALIGNMENT; } catch (eA2) {}
                }
                try { item.endJoin = EndJoin.ROUND_END_JOIN; } catch (eJ) {}
                n++;
            }
        } catch (e) {
            // skip text selections etc.
        }
    }

    if (n === 0) {
        alert("Could not apply stroke.\nSelect the frame with the Selection tool (V), not the image inside.");
    } else {
        alert("Gold stroke applied to " + n + " object(s).\nWeight: 2 pt · Color: EM Gold");
    }
})();
