(function () {
    function initCopyOwnerToDriver() {
        var toggle = document.getElementById("risk-copy-owner-toggle");
        var ownerData = document.getElementById("risk-owner-data");
        var feedback = document.getElementById("risk-copy-owner-feedback");

        if (!toggle || !ownerData) {
            return;
        }

        var ownerIsCompany = ownerData.dataset.ownerDocumentType === "nit";

        // dataset key (owner) -> id del input destino (conductor).
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
            feedback.textContent = message || "";
            feedback.classList.toggle("is-error", Boolean(isError));
        }

        function targetFields() {
            return Object.keys(fieldMap)
                .map(function (key) {
                    return document.getElementById(fieldMap[key]);
                })
                .filter(Boolean);
        }

        // Bloqueo con readonly (NO disabled): los disabled no se envian en el POST
        // y se perderia la informacion del conductor.
        function setLocked(locked) {
            targetFields().forEach(function (field) {
                field.readOnly = locked;
            });
        }

        function copyOwnerData() {
            var copied = 0;
            Object.keys(fieldMap).forEach(function (dataKey) {
                var value = ownerData.dataset[dataKey] || "";
                var field = document.getElementById(fieldMap[dataKey]);
                if (!field) {
                    return;
                }
                field.value = value;
                field.dispatchEvent(new Event("input", { bubbles: true }));
                field.dispatchEvent(new Event("change", { bubbles: true }));
                if (value) {
                    copied += 1;
                }
            });
            return copied;
        }

        // Propietario empresa (NIT): no se puede copiar; el conductor es persona natural.
        if (ownerIsCompany) {
            toggle.checked = false;
            toggle.disabled = true;
            setFeedback(
                "El propietario registrado con NIT es una empresa. El conductor debe registrarse con sus propios datos.",
                true
            );
            return;
        }

        toggle.addEventListener("change", function () {
            if (toggle.checked) {
                var copied = copyOwnerData();
                if (!copied) {
                    toggle.checked = false;
                    setFeedback("No hay datos del propietario disponibles para copiar.", true);
                    return;
                }
                setLocked(true);
                setFeedback(
                    "Datos del propietario copiados. Los campos quedan bloqueados; desactiva el interruptor para editarlos.",
                    false
                );
            } else {
                setLocked(false);
                setFeedback("", false);
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCopyOwnerToDriver);
    } else {
        initCopyOwnerToDriver();
    }
}());
