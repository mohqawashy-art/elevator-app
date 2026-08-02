// Relink selected wave frame OR Master A footer to gold-edge PNG
// Image: D:\Excellence Makers Profile 2026\02_links\footer_wave_gold_edge.png

(function () {
    if (!app.documents.length) {
        alert("Open the document first.");
        return;
    }

    var doc = app.activeDocument;
    var goldWave = new File("D:/Excellence Makers Profile 2026/02_links/footer_wave_gold_edge.png");
    if (!goldWave.exists) {
        alert("Gold-edge image not found:\n" + goldWave.fsName);
        return;
    }

    function relinkFrame(frame) {
        try {
            if (frame.images.length > 0) {
                frame.images.item(0).itemLink.relink(goldWave);
                try { frame.images.item(0).itemLink.update(); } catch (eU) {}
                return true;
            }
            // empty graphic frame
            frame.place(goldWave);
            try {
                frame.fit(FitOptions.FILL_PROPORTIONALLY);
                frame.fit(FitOptions.CENTER_CONTENT);
            } catch (eF) {}
            return true;
        } catch (e) {
            return false;
        }
    }

    var done = 0;

    // 1) If selection: relink selected
    if (app.selection.length) {
        for (var i = 0; i < app.selection.length; i++) {
            var sel = app.selection[i];
            try {
                // if image selected, get parent frame
                if (sel.constructor.name === "Image") sel = sel.parent;
                if (relinkFrame(sel)) done++;
            } catch (e1) {}
        }
    }

    // 2) Else: find footer_wave_graphic on Master A
    if (done === 0) {
        var ms, p, items, j, k;
        for (j = 0; j < doc.masterSpreads.length; j++) {
            ms = doc.masterSpreads.item(j);
            for (k = 0; k < ms.pages.length; k++) {
                p = ms.pages.item(k);
                items = p.pageItems.everyItem().getElements();
                for (var t = 0; t < items.length; t++) {
                    try {
                        if (items[t].label === "footer_wave_graphic") {
                            if (relinkFrame(items[t])) done++;
                        }
                    } catch (e2) {}
                }
            }
        }
    }

    // 3) Fallback: any link matching the old ChatGPT wave filename
    if (done === 0) {
        var links = doc.links;
        for (var L = 0; L < links.length; L++) {
            try {
                var nm = String(links.item(L).name).toLowerCase();
                if (nm.indexOf("12_47_41") >= 0 || nm.indexOf("chatgpt image jul 4") >= 0) {
                    links.item(L).relink(goldWave);
                    try { links.item(L).update(); } catch (e3) {}
                    done++;
                }
            } catch (e4) {}
        }
    }

    try {
        doc.displayPerformancePreferences.defaultDisplaySettings =
            ViewDisplaySettings.HIGH_QUALITY;
    } catch (eD) {}

    if (done > 0) {
        alert(
            "Wave updated with GOLD edge on the top ribbon.\n\n" +
            "Linked: footer_wave_gold_edge.png\n" +
            "Updated items: " + done + "\n\n" +
            "View > Display Performance > High Quality"
        );
    } else {
        alert(
            "Select the wave frame, then run again.\n" +
            "Or place manually:\n" + goldWave.fsName
        );
    }
})();
