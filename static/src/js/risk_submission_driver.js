(function () {
    var DRIVER_VALIDATION_RULES = [
        {
            id: "driver_document_number",
            normalizeDigits: true,
            validate: function (value) {
                return /^[0-9]{6,10}$/.test(value)
                    ? ""
                    : "La cedula debe contener entre 6 y 10 digitos numericos.";
            },
        },
        {
            id: "driver_phone",
            normalizeDigits: true,
            validate: validateRequiredMobile,
        },
        {
            id: "family_reference_phone",
            normalizeDigits: true,
            validate: validateRequiredMobile,
        },
        {
            id: "cargo_reference_phone",
            normalizeDigits: true,
            validate: validateRequiredMobile,
        },
        {
            id: "driver_optional_phone",
            normalizeDigits: true,
            validate: function (value) {
                if (!value) {
                    return "";
                }
                return (/^[0-9]{7}$/.test(value) || /^[36][0-9]{9}$/.test(value))
                    ? ""
                    : "El telefono debe tener 7 digitos o 10 digitos iniciando por 3 o 6.";
            },
        },
        {
            id: "driver_email",
            validate: function (value) {
                return /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/.test(value)
                    ? ""
                    : "Ingresa un correo valido. Ejemplo: conductor@empresa.com.";
            },
        },
    ];

    function validateRequiredMobile(value) {
        return /^3[0-9]{9}$/.test(value)
            ? ""
            : "El celular debe tener 10 digitos e iniciar por 3.";
    }

    function digitsOnly(value) {
        return (value || "").replace(/\D/g, "");
    }

    function getFieldErrorElement(field) {
        var container = field.closest(".risk-vr-field");
        var error;

        if (!container) {
            return null;
        }
        error = container.querySelector(".risk-vr-field-error");
        if (!error) {
            error = document.createElement("p");
            error.className = "risk-vr-field-error";
            error.id = field.id + "-error";
            container.appendChild(error);
            field.setAttribute("aria-describedby", error.id);
        }
        return error;
    }

    function setFieldError(field, message) {
        var error = getFieldErrorElement(field);

        field.setCustomValidity(message || "");
        field.classList.toggle("is-invalid", Boolean(message));
        field.setAttribute("aria-invalid", message ? "true" : "false");
        if (error) {
            error.textContent = message || "";
            error.hidden = !message;
        }
    }

    function validateField(field, rule, showEmpty) {
        var value = field.value.trim();
        var message = "";

        if (rule.normalizeDigits) {
            value = digitsOnly(value).slice(0, Number(field.maxLength) > 0 ? Number(field.maxLength) : 99);
            if (field.value !== value) {
                field.value = value;
            }
        }

        if (!value && !field.required) {
            setFieldError(field, "");
            return true;
        }
        if (!value && field.required) {
            message = showEmpty ? "Este campo es obligatorio." : "";
        } else {
            message = rule.validate(value);
        }

        setFieldError(field, message);
        return !message;
    }

    function getCheckedRadioValue(name) {
        var selected = document.querySelector('input[name="' + name + '"]:checked');
        return selected ? selected.value : "";
    }

    function getRadioErrorElement(groupName) {
        var firstRadio = document.querySelector('input[name="' + groupName + '"]');
        var row = firstRadio ? firstRadio.closest(".risk-vr-declare-row") : null;
        var error;

        if (!row) {
            return null;
        }
        error = row.querySelector(".risk-vr-field-error");
        if (!error) {
            error = document.createElement("p");
            error.className = "risk-vr-field-error";
            row.appendChild(error);
        }
        return error;
    }

    function setRadioGroupError(groupName, message) {
        var radios = Array.prototype.slice.call(document.querySelectorAll('input[name="' + groupName + '"]'));
        var error = getRadioErrorElement(groupName);

        radios.forEach(function (radio) {
            radio.setCustomValidity(message || "");
            radio.setAttribute("aria-invalid", message ? "true" : "false");
        });
        if (error) {
            error.textContent = message || "";
            error.hidden = !message;
        }
    }

    function validateDriverDeclarations() {
        var errors = [
            {
                name: "driver_is_fit",
                message: "Para continuar, confirma que el conductor se encuentra apto fisica, mental y psicotecnicamente para prestar el servicio.",
            },
            {
                name: "driver_is_trained",
                message: "Para continuar, confirma que el conductor esta capacitado y entrenado para contingencias y prevencion de accidentes en carretera.",
            },
        ];
        var valid = true;

        errors.forEach(function (item) {
            var message = getCheckedRadioValue(item.name) === "yes" ? "" : item.message;
            setRadioGroupError(item.name, message);
            if (message) {
                valid = false;
            }
        });
        return valid;
    }

    function initDriverFrontendValidation() {
        var firstDriverField = document.getElementById("driver_document_number");
        var form;

        if (!firstDriverField) {
            return;
        }
        form = firstDriverField.closest("form");

        DRIVER_VALIDATION_RULES.forEach(function (rule) {
            var field = document.getElementById(rule.id);
            if (!field) {
                return;
            }
            field.addEventListener("input", function () {
                validateField(field, rule, false);
            });
            field.addEventListener("blur", function () {
                validateField(field, rule, true);
            });
        });

        ["driver_is_fit", "driver_is_trained"].forEach(function (groupName) {
            Array.prototype.forEach.call(document.querySelectorAll('input[name="' + groupName + '"]'), function (radio) {
                radio.addEventListener("change", validateDriverDeclarations);
            });
        });

        if (form) {
            form.addEventListener("submit", function (event) {
                var firstInvalid = null;
                var isValid = true;

                DRIVER_VALIDATION_RULES.forEach(function (rule) {
                    var field = document.getElementById(rule.id);
                    if (!field) {
                        return;
                    }
                    if (!validateField(field, rule, true)) {
                        isValid = false;
                        firstInvalid = firstInvalid || field;
                    }
                });

                if (!validateDriverDeclarations()) {
                    isValid = false;
                    firstInvalid = firstInvalid || document.querySelector('input[name="driver_is_fit"]');
                }

                if (!isValid) {
                    event.preventDefault();
                    event.stopPropagation();
                    if (firstInvalid && typeof firstInvalid.focus === "function") {
                        firstInvalid.focus();
                    }
                    if (form.reportValidity) {
                        form.reportValidity();
                    }
                }
            });
        }
    }

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
        document.addEventListener("DOMContentLoaded", function () {
            initCopyOwnerToDriver();
            initDriverFrontendValidation();
        });
    } else {
        initCopyOwnerToDriver();
        initDriverFrontendValidation();
    }
}());
