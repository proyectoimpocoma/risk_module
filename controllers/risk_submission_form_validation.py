import logging
from datetime import date

from ..risk_validation_rules import is_valid_mobile_phone, is_valid_phone, phone_digits
from .risk_submission_form_schema import (
    CC_REGEX,
    CHOICE_VALUES,
    EMAIL_REGEX,
    NIT_REGEX,
    PLATE_REGEX,
    SEMI_TRAILER_PLATE_REGEX,
    TEXT_LIMITS,
)

_logger = logging.getLogger(__name__)


class RiskSubmissionFormValidationMixin:
    def _normalize_step_data(self, step, data):
        before_plate = data.get("vehicle_plate")
        before_semi = data.get("semi_trailer_plate")
        if step == 1:
            for field in ("vehicle_plate", "semi_trailer_plate"):
                if data.get(field):
                    data[field] = data[field].strip().upper()
            if data.get("has_semi_trailer") not in ("yes", "no"):
                data["has_semi_trailer"] = "yes" if data.get("semi_trailer_plate") else "no"
            if data.get("has_semi_trailer") != "yes":
                data["semi_trailer_plate"] = ""
        if step in (2, 3):
            for field in ("owner_city", "driver_city"):
                if data.get(field):
                    data[field] = data[field].strip().title()
        if step == 2:
            if data.get("same_owner_on_license") not in ("yes", "no"):
                data["same_owner_on_license"] = "yes"
            if data.get("same_owner_on_license") == "yes":
                for field in (
                    "registered_owner_document_type",
                    "registered_owner_document_number",
                    "registered_owner_name",
                    "registered_owner_phone",
                ):
                    data[field] = ""
        if before_plate != data.get("vehicle_plate") or before_semi != data.get("semi_trailer_plate"):
            _logger.debug(
                "Normalized vehicle data step=%s plate=%s semi_present=%s",
                step,
                data.get("vehicle_plate"),
                bool(data.get("semi_trailer_plate")),
            )

    def _validate_step(self, step, data):
        _logger.debug("Validating risk registration step=%s", step)
        length_error = self._validate_text_lengths(data)
        if length_error:
            _logger.warning("Risk registration length/choice validation failed step=%s error=%s", step, length_error)
            return length_error

        if step == 1:
            return self._validate_vehicle_step(data)
        if step == 2:
            return self._validate_owner_step(data)
        if step == 3:
            return self._validate_driver_step(data)
        return None

    def _validate_vehicle_step(self, data):
        vehicle_plate = data.get("vehicle_plate")
        has_semi_trailer = data.get("has_semi_trailer")
        semi_trailer_plate = data.get("semi_trailer_plate")
        form_date = data.get("form_date")
        if not form_date:
            return "La fecha es obligatoria."
        try:
            parsed_date = date.fromisoformat(form_date)
        except ValueError:
            return "La fecha no tiene un formato valido."
        if parsed_date > date.today():
            return "La fecha no puede ser futura."
        if not vehicle_plate:
            return "La placa del vehiculo es obligatoria."
        if not PLATE_REGEX.match(vehicle_plate):
            return (
                "La placa del vehiculo debe tener formato colombiano valido: "
                "ABC123 para vehiculo/carga o ABC12 para motocicleta."
            )
        if has_semi_trailer not in ("yes", "no"):
            return "Debes indicar si el vehiculo tiene semi/remolque."
        if has_semi_trailer == "yes" and not semi_trailer_plate:
            return "Debes diligenciar la placa del semi/remolque."
        if semi_trailer_plate and not SEMI_TRAILER_PLATE_REGEX.match(
            semi_trailer_plate
        ):
            return (
                "La placa del semi/remolque debe tener formato valido: "
                "A12345 (una letra y cinco numeros)."
            )
        return None

    def _validate_owner_step(self, data):
        owner_email = data.get("owner_email")
        owner_document_error = self._validate_document(
            data.get("owner_document_type"),
            data.get("owner_document_number"),
            "documento del propietario",
        )
        if not data.get("owner_name"):
            return "El nombre del propietario, tenedor o empresa es obligatorio."
        if owner_document_error:
            return owner_document_error
        if owner_email and not EMAIL_REGEX.match(owner_email):
            return "El correo del propietario no tiene un formato valido. Ejemplo: propietario@empresa.com."

        phone_error = self._validate_mobile_phone(
            data.get("owner_phone"), "celular del propietario"
        )
        if phone_error:
            return phone_error
        if data.get("same_owner_on_license") not in ("yes", "no"):
            return "Debes indicar si el propietario registrado en licencia es el mismo."

        registered_owner_document_error = self._validate_document(
            data.get("registered_owner_document_type"),
            data.get("registered_owner_document_number"),
            "documento del propietario registrado",
            required=data.get("same_owner_on_license") == "no",
        )
        if registered_owner_document_error:
            return registered_owner_document_error
        if data.get("same_owner_on_license") == "no" and not data.get("registered_owner_name"):
            return "Debes diligenciar los nombres y apellidos del propietario registrado."
        if data.get("same_owner_on_license") == "no" and not data.get("registered_owner_phone"):
            return "Debes diligenciar el celular del propietario registrado."

        return self._validate_mobile_phone(
            data.get("registered_owner_phone"),
            "celular del propietario registrado",
        )

    def _validate_driver_step(self, data):
        if not data.get("driver_name"):
            return "El nombre del conductor es obligatorio."
        if not data.get("driver_document_number"):
            return "La cedula del conductor es obligatoria."
        if not CC_REGEX.match(data.get("driver_document_number")):
            return (
                "La cedula del conductor debe contener entre 6 y 10 digitos numericos."
            )

        for phone, label, validator in (
            (
                data.get("driver_phone"),
                "celular del conductor",
                self._validate_mobile_phone,
            ),
            (
                data.get("driver_optional_phone"),
                "telefono opcional",
                self._validate_phone,
            ),
            (
                data.get("family_reference_phone"),
                "celular de referencia familiar",
                self._validate_mobile_phone,
            ),
            (
                data.get("cargo_reference_phone"),
                "celular de referencia de carga",
                self._validate_mobile_phone,
            ),
        ):
            phone_error = validator(phone, label)
            if phone_error:
                return phone_error

        if data.get("driver_email") and not EMAIL_REGEX.match(data.get("driver_email")):
            return "El correo del conductor no tiene un formato valido. Ejemplo: conductor@empresa.com."
        if data.get("driver_is_fit") not in ("yes", "no"):
            return "Debes indicar si el conductor es apto fisica, mental y psicotecnicamente."
        if data.get("driver_is_fit") != "yes":
            return (
                "Para continuar, el conductor debe confirmar que se encuentra apto fisica, mental y psicotecnicamente para prestar el servicio."
            )
        if data.get("driver_is_trained") not in ("yes", "no"):
            return "Debes indicar si el conductor esta capacitado y entrenado."
        if data.get("driver_is_trained") != "yes":
            return "Para continuar, el conductor debe confirmar que esta capacitado y entrenado para contingencias y prevencion de accidentes en carretera."
        return None

    def _validate_text_lengths(self, data):
        for field, max_length in TEXT_LIMITS.items():
            value = data.get(field)
            if value and len(value) > max_length:
                return "El campo %s no puede superar %s caracteres." % (
                    field,
                    max_length,
                )
        for field, allowed_values in CHOICE_VALUES.items():
            value = data.get(field)
            if value and value not in allowed_values:
                return "El campo %s tiene una opcion invalida." % field
        return None

    def _validate_document(self, document_type, document_number, label, required=True):
        if not document_type and not document_number and not required:
            return None
        if not document_type:
            return "Debes seleccionar CC o NIT para el %s." % label
        if not document_number:
            return "Debes diligenciar el numero del %s." % label
        if document_type == "cc" and not CC_REGEX.match(document_number):
            return (
                "La cedula del %s debe contener entre 6 y 10 digitos numericos." % label
            )
        if document_type == "nit" and not NIT_REGEX.match(document_number):
            return "El NIT del %s debe tener formato 123456789 o 12345678-0." % label
        return None

    def _phone_digits(self, phone):
        return phone_digits(phone)

    def _validate_mobile_phone(self, phone, label):
        if phone and not is_valid_mobile_phone(phone):
            return (
                "El %s debe ser un celular colombiano de 10 digitos que inicia por 3."
                % label
            )
        return None

    def _validate_phone(self, phone, label):
        if not phone or is_valid_phone(phone):
            return None
        return "El %s debe tener 7 digitos o 10 digitos iniciando por 3 o 6." % label
