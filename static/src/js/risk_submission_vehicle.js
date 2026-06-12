(function () {
    function initSemiTrailerSwitch() {
        var valueInput = document.getElementById("has_semi_trailer");
        var toggle = document.getElementById("has_semi_trailer_toggle");
        var plateInput = document.getElementById("semi_trailer_plate");
        var plateField = document.querySelector("[data-semi-trailer-field='1']");

        if (!valueInput || !toggle || !plateInput || !plateField) {
            return;
        }

        function syncState() {
            var enabled = toggle.checked;
            valueInput.value = enabled ? "yes" : "no";
            plateInput.disabled = !enabled;
            plateInput.required = enabled;
            plateField.classList.toggle("is-disabled", !enabled);

            if (!enabled) {
                plateInput.value = "";
            }
        }

        toggle.addEventListener("change", syncState);
        syncState();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initSemiTrailerSwitch);
    } else {
        initSemiTrailerSwitch();
    }
}());
