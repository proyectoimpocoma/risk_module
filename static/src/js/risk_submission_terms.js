(function () {
    function initRiskTermsModal() {
        var modal = document.getElementById("risk-terms-modal");
        var openButton = document.getElementById("risk-open-terms");
        var closeButton = document.getElementById("risk-close-terms");
        var understandButton = document.getElementById("risk-understand-terms");
        var checkbox = document.getElementById("risk-terms-check");
        var confirmedInput = document.getElementById("risk-terms-confirmed");
        var acceptLabel = document.getElementById("risk-terms-accept");
        var warning = document.getElementById("risk-terms-warning");

        if (!modal || !openButton || !closeButton || !understandButton || !checkbox || !confirmedInput) {
            return;
        }

        var form = checkbox.closest("form");
        if (!form) {
            return;
        }

        // La aceptacion es deliberada en cada visita: la casilla arranca bloqueada y
        // sin marcar aunque la sesion recuerde una aceptacion previa.
        var termsViewed = false;
        checkbox.disabled = true;
        checkbox.checked = false;
        confirmedInput.value = "0";

        var MSG_OPEN = "Primero abre y lee los terminos completos para poder aceptarlos.";
        var MSG_CHECK = "Debes aceptar los terminos para continuar.";

        function setModal(open) {
            modal.classList.toggle("is-open", open);
        }

        function showWarning(message) {
            if (!warning) {
                return;
            }
            warning.textContent = message;
            warning.hidden = false;
        }

        function hideWarning() {
            if (warning) {
                warning.hidden = true;
            }
        }

        // Abrir (y por tanto leer) el modal habilita la casilla de aceptacion.
        function markTermsViewed() {
            termsViewed = true;
            checkbox.disabled = false;
            hideWarning();
        }

        openButton.addEventListener("click", function () {
            markTermsViewed();
            setModal(true);
        });
        closeButton.addEventListener("click", function () {
            setModal(false);
        });
        understandButton.addEventListener("click", function () {
            markTermsViewed();
            setModal(false);
        });
        modal.addEventListener("click", function (event) {
            if (event.target === modal) {
                setModal(false);
            }
        });

        // Bloquea marcar la casilla si aun no se han abierto los terminos.
        if (acceptLabel) {
            acceptLabel.addEventListener("click", function (event) {
                if (checkbox.disabled) {
                    event.preventDefault();
                    showWarning(MSG_OPEN);
                }
            });
        }

        checkbox.addEventListener("change", function () {
            confirmedInput.value = checkbox.checked ? "1" : "0";
            if (checkbox.checked) {
                hideWarning();
            }
        });

        // Al enviar, exige la casilla marcada y muestra el mensaje correspondiente.
        form.addEventListener("submit", function (event) {
            if (!checkbox.checked) {
                event.preventDefault();
                showWarning(termsViewed ? MSG_CHECK : MSG_OPEN);
                return;
            }
            confirmedInput.value = "1";
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initRiskTermsModal);
    } else {
        initRiskTermsModal();
    }
}());
