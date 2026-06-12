(function () {
    function initCopyOwnerToDriver() {
        var button = document.getElementById("risk-copy-owner-to-driver");
        var ownerData = document.getElementById("risk-owner-data");
        var feedback = document.getElementById("risk-copy-owner-feedback");

        if (!button || !ownerData) {
            return;
        }

        var fieldMap = {
            ownerName: "driver_name",
            ownerDocumentNumber: "driver_document_number",
            ownerAddress: "driver_address",
            ownerNeighborhood: "driver_neighborhood",
            ownerCity: "driver_city",
            ownerPhone: "driver_phone",
            ownerEmail: "driver_email",
        };

        function setFeedback(message, isError) {
            if (!feedback) {
                return;
            }
            feedback.textContent = message;
            feedback.classList.toggle("is-error", Boolean(isError));
        }

        function copyValue(dataKey, fieldId) {
            var value = ownerData.dataset[dataKey] || "";
            var field = document.getElementById(fieldId);
            if (!field || !value) {
                return false;
            }
            field.value = value;
            field.dispatchEvent(new Event("input", { bubbles: true }));
            field.dispatchEvent(new Event("change", { bubbles: true }));
            return true;
        }

        button.addEventListener("click", function () {
            var copied = 0;
            Object.keys(fieldMap).forEach(function (dataKey) {
                if (copyValue(dataKey, fieldMap[dataKey])) {
                    copied += 1;
                }
            });

            if (!copied) {
                setFeedback("No hay datos del propietario disponibles para copiar.", true);
                return;
            }
            setFeedback("Datos del propietario copiados. Puedes ajustarlos si el conductor tiene informacion diferente.", false);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCopyOwnerToDriver);
    } else {
        initCopyOwnerToDriver();
    }
}());
