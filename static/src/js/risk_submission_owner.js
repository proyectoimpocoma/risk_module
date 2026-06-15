(function () {
    function initRegisteredOwnerSwitch() {
        var valueInput = document.getElementById("same_owner_on_license");
        var toggle = document.getElementById("same_owner_on_license_toggle");
        var fields = document.querySelectorAll("[data-registered-owner-field='1']");

        if (!valueInput || !toggle || !fields.length) {
            return;
        }

        function fieldInputs() {
            return document.querySelectorAll(
                "input[name='registered_owner_document_type'], " +
                "#registered_owner_document_number, " +
                "#registered_owner_name, " +
                "#registered_owner_phone"
            );
        }

        function syncState() {
            var sameOwner = toggle.checked;
            valueInput.value = sameOwner ? "yes" : "no";

            Array.prototype.forEach.call(fields, function (field) {
                field.classList.toggle("is-disabled", sameOwner);
            });
            Array.prototype.forEach.call(fieldInputs(), function (input) {
                input.disabled = sameOwner;
                input.required = !sameOwner && (
                    input.name === "registered_owner_document_type" ||
                    input.id === "registered_owner_document_number" ||
                    input.id === "registered_owner_name" ||
                    input.id === "registered_owner_phone"
                );
                if (sameOwner) {
                    if (input.type === "radio") {
                        input.checked = false;
                    } else {
                        input.value = "";
                    }
                }
            });
        }

        toggle.addEventListener("change", syncState);
        syncState();
    }

    function initExtraOwners() {
        var list = document.getElementById("extra-owners-list");
        var addBtn = document.getElementById("add-extra-owner");
        var template = document.getElementById("extra-owner-template");

        if (!list || !addBtn || !template) {
            return;
        }

        var rowTemplate = template.querySelector("[data-extra-owner-row='1']");
        if (!rowTemplate) {
            return;
        }

        addBtn.addEventListener("click", function () {
            var clone = rowTemplate.cloneNode(true);
            list.appendChild(clone);
            var firstInput = clone.querySelector("input, select");
            if (firstInput) {
                firstInput.focus();
            }
        });

        list.addEventListener("click", function (event) {
            var removeBtn = event.target.closest("[data-extra-owner-remove='1']");
            if (!removeBtn) {
                return;
            }
            var row = removeBtn.closest("[data-extra-owner-row='1']");
            if (row) {
                row.remove();
            }
        });
    }

    function initOwnerStep() {
        initRegisteredOwnerSwitch();
        initExtraOwners();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initOwnerStep);
    } else {
        initOwnerStep();
    }
}());
