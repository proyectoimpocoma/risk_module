(function () {
    function initRiskPrintPreview() {
        var printButton = document.getElementById("risk-print-preview");
        var printFrame = document.getElementById("risk-print-frame");
        if (!printButton || !printFrame) {
            return;
        }

        printButton.addEventListener("click", function () {
            if (printFrame.contentWindow) {
                printFrame.contentWindow.focus();
                printFrame.contentWindow.print();
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initRiskPrintPreview);
    } else {
        initRiskPrintPreview();
    }
}());
