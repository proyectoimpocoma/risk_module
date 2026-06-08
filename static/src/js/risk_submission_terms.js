(function () {
    function initRiskTermsModal() {
        var modal = document.getElementById("risk-terms-modal");
        var openButton = document.getElementById("risk-open-terms");
        var closeButton = document.getElementById("risk-close-terms");
        var understandButton = document.getElementById("risk-understand-terms");
        var checkbox = document.getElementById("risk-terms-check");
        var confirmedInput = document.getElementById("risk-terms-confirmed");
        var submitButton = document.getElementById("risk-submit-button");
        var termsViewed = confirmedInput && confirmedInput.value === "1";

        if (!modal || !openButton || !closeButton || !understandButton || !checkbox || !confirmedInput || !submitButton) {
            return;
        }

        var form = submitButton.closest("form");
        if (!form) {
            return;
        }

        if (termsViewed) {
            checkbox.disabled = false;
            checkbox.checked = true;
        }
        
        function setModal(open) {
            modal.classList.toggle("is-open", open);
        }
        
        function refreshSubmit() {
            submitButton.disabled = !termsViewed || !checkbox.checked;
        }
        
        openButton.addEventListener("click", function () {
            setModal(true);
        });
        closeButton.addEventListener("click", function () {
            setModal(false);
        });
        understandButton.addEventListener("click", function () {
            termsViewed = true;
            checkbox.disabled = false;
            checkbox.checked = true;
            confirmedInput.value = "1";
            setModal(false);
            refreshSubmit();
        });
        checkbox.addEventListener("change", function () {
            confirmedInput.value = checkbox.checked ? "1" : "0";
            refreshSubmit();
        });
        form.addEventListener("submit", function () {
            confirmedInput.value = termsViewed ? (checkbox.checked ? "1" : "0") : "0";
        });
        modal.addEventListener("click", function (event) {
            if (event.target === modal) {
                setModal(false);
            }
        });
        refreshSubmit();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initRiskTermsModal);
    } else {
        initRiskTermsModal();
    }
}());
