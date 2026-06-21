import logging
from datetime import date

from odoo.http import request

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
        """
        Normalize and cleanup form data before validation or saving.
        
        Args:
            step (int): The current step number of the form.
            data (dict): The raw form data dictionary to be normalized in-place.
        """
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
        if data.get("owner_document_type") == "nit":
            data["single_owner_driver_signature"] = "no"
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
                data["extra_owners"] = []
        if before_plate != data.get("vehicle_plate") or before_semi != data.get("semi_trailer_plate"):
            _logger.debug(
                "Normalized vehicle data step=%s plate=%s semi_present=%s",
                step,
                data.get("vehicle_plate"),
                bool(data.get("semi_trailer_plate")),
            )

    def _validate_step(self, step, data):
        """
        Validate all data for a given form step.
        
        Args:
            step (int): The step number to validate.
            data (dict): The normalized form data.
            
        Returns:
            str or None: Error message if validation fails, None if successful.
        """
        _logger.debug("Validating risk registration step=%s", step)
        length_error = self._validate_text_lengths(data)
        if length_error:
            _logger.warning("Risk registration length/choice validation failed step=%s error=%s", step, length_error)
            return length_error

        if step == 1:
            return self._validate_vehicle_step(data)
        if step == 2:
            owner_error = self._validate_owner_step(data)
            if owner_error:
                return owner_error
            return self._validate_extra_owners(data)
        if step == 3:
            return self._validate_driver_step(data)
        return None

    def _validate_extra_owners(self, data):
        """Validate each additional owner line collected in step 2."""
        owners = data.get("extra_owners") or []
        # Si el tenedor/poseedor NO es el propietario registrado en licencia,
        # debe declararse al menos un propietario adicional.
        if data.get("same_owner_on_license") == "no" and not owners:
            return (
                "Como el propietario registrado en licencia no es el mismo, "
                'debes agregar al menos un propietario en "Otros propietarios".'
            )
        roles = ("owner", "holder", "possessor")
        for index, owner in enumerate(owners, start=1):
            if not owner.get("name"):
                return "El nombre del propietario adicional %s es obligatorio." % index
            document_error = self._validate_document(
                owner.get("document_type"),
                owner.get("document_number"),
                "documento del propietario adicional %s" % index,
            )
            if document_error:
                return document_error
            if owner.get("role") not in roles:
                return "Debes indicar la relacion del propietario adicional %s." % index
            if not (owner.get("phone") or "").strip():
                return "El celular del propietario adicional %s es obligatorio." % index
            phone_error = self._validate_mobile_phone(
                owner.get("phone"), "celular del propietario adicional %s" % index
            )
            if phone_error:
                return phone_error
            if not (owner.get("email") or "").strip():
                return "El correo del propietario adicional %s es obligatorio." % index
            if not EMAIL_REGEX.match(owner.get("email")):
                return "El correo del propietario adicional %s no tiene un formato valido." % index
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
                "ABC123 (3 letras + 3 digitos)."
            )
        active_error = self._validate_no_active_submission_for_plate(data)
        if active_error:
            return active_error
        master_error = self._validate_vehicle_master_state(data)
        if master_error:
            return master_error
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
        if not (data.get("satellite_company") or "").strip():
            return "La empresa satelital es obligatoria."
        if not (data.get("satellite_user") or "").strip():
            return "El usuario de la cuenta satelital es obligatorio."
        if not (data.get("satellite_password") or "").strip():
            return "La clave de la cuenta satelital es obligatoria."
        return None

    def _validate_owner_step(self, data):
        owner_email = (data.get("owner_email") or "").strip()
        owner_document_error = self._validate_document(
            data.get("owner_document_type"),
            data.get("owner_document_number"),
            "documento del propietario",
        )
        if not data.get("owner_name"):
            return "El nombre del propietario, tenedor o empresa es obligatorio."
        if owner_document_error:
            return owner_document_error
        if not (data.get("owner_address") or "").strip():
            return "La direccion del propietario es obligatoria."
        if not (data.get("owner_neighborhood") or "").strip():
            return "El barrio del propietario es obligatorio."
        if not (data.get("owner_city") or "").strip():
            return "La ciudad del propietario es obligatoria."
        if not (data.get("owner_phone") or "").strip():
            return "El celular del propietario es obligatorio."
        phone_error = self._validate_mobile_phone(
            data.get("owner_phone"), "celular del propietario"
        )
        if phone_error:
            return phone_error
        if not owner_email:
            return "El correo del propietario es obligatorio."
        if not EMAIL_REGEX.match(owner_email):
            return "El correo del propietario no tiene un formato valido. Ejemplo: propietario@empresa.com."
        if data.get("advance_payment_to") not in ("driver", "owner"):
            return "Debes indicar a quien se autoriza el pago de anticipos (Conductor o Propietario)."
        if data.get("same_owner_on_license") not in ("yes", "no"):
            return "Debes indicar si el propietario registrado en licencia es el mismo."

        # The registered owner is no longer captured with fixed fields; when the
        # tenedor is not the registered owner, it is declared through the
        # "Otros propietarios" dynamic list. Only validate the legacy fields'
        # format if they happen to carry a value (e.g. older drafts/backoffice).
        registered_owner_document_error = self._validate_document(
            data.get("registered_owner_document_type"),
            data.get("registered_owner_document_number"),
            "documento del propietario registrado",
            required=False,
        )
        if registered_owner_document_error:
            return registered_owner_document_error

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
        for field_name, label in (
            ("driver_address", "la direccion del conductor"),
            ("driver_neighborhood", "el barrio del conductor"),
            ("driver_city", "la ciudad del conductor"),
            ("driver_phone", "el celular del conductor"),
            ("driver_email", "el correo del conductor"),
            ("family_reference_name", "la referencia familiar"),
            ("family_reference_relationship", "el parentesco de la referencia familiar"),
            ("family_reference_phone", "el celular de la referencia familiar"),
            ("cargo_reference_name", "la referencia de transporte de carga"),
            ("cargo_reference_phone", "el celular de la referencia de carga"),
        ):
            if not (data.get(field_name) or "").strip():
                return "Debes diligenciar %s." % label
        driver_assignment_error = self._validate_driver_not_active_on_other_vehicle(data)
        if driver_assignment_error:
            return driver_assignment_error
        master_assignment_error = self._validate_driver_master_assignment(data)
        if master_assignment_error:
            return master_assignment_error

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

    def _validate_vehicle_master_state(self, data):
        plate = data.get("vehicle_plate")
        vehicle = request.env["risk.vehicle"].find_by_plate(plate)
        if not vehicle:
            return None
        if vehicle.status == "blocked":
            return (
                "El vehiculo %s se encuentra bloqueado para nuevas habilitaciones. "
                "Por favor contacta al equipo de riesgo."
            ) % vehicle.plate
        return None

    def _validate_driver_master_assignment(self, data):
        driver_document_number = data.get("driver_document_number")
        vehicle_plate = data.get("vehicle_plate")
        vehicle = request.env["risk.vehicle"].find_by_plate(vehicle_plate)
        if vehicle:
            driver = vehicle.assignment_conflict_for_driver(driver_document_number)
            if driver:
                return (
                    "El vehiculo %s ya se encuentra habilitado con el conductor %s. "
                    "Si necesitas actualizarlo, solicita revision al equipo de riesgo."
                ) % (vehicle.plate, driver.document_number)
        driver = request.env["risk.driver"].find_by_document(driver_document_number)
        if driver:
            conflict_vehicle = driver.assignment_conflict_for_vehicle(vehicle_plate)
            if conflict_vehicle:
                return (
                    "El conductor con cedula %s ya se encuentra habilitado para el "
                    "vehiculo %s. Un conductor solo puede estar activo en un vehiculo."
                ) % (driver.document_number, conflict_vehicle.plate)
        return None

    def _validate_no_active_submission_for_plate(self, data):
        plate = data.get("vehicle_plate")
        submission_id = data.get("submission_id") or request.session.get(
            "risk_submission_id"
        )

        # When the session has no submission_id, recover any own draft for this
        # plate so it is excluded from the duplicate check and can be reused
        # instead of blocking the user (session can be lost when navigating to
        # the start page or on browser reload that clears the POST context).
        own_draft_ids = []
        if not request.env.user._is_public():
            partner = request.env.user.partner_id
            if partner and plate:
                own_drafts = (
                    request.env["risk.module"]
                    .sudo()
                    .search(
                        [
                            ("vehicle_plate", "=", plate),
                            ("state", "=", "draft"),
                            ("partner_id", "=", partner.id),
                        ],
                        order="create_date desc",
                    )
                )
                if own_drafts:
                    own_draft_ids = own_drafts.ids
                    if not submission_id:
                        submission_id = own_drafts[0].id
                        data["submission_id"] = submission_id
                        request.session["risk_submission_id"] = submission_id
                        _logger.info(
                            "Recovered own draft submission submission_id=%s plate=%s user_id=%s",
                            submission_id,
                            plate,
                            request.env.user.id,
                        )

        exclude_ids = set(own_draft_ids)
        if submission_id:
            exclude_ids.add(int(submission_id))

        RiskModule = request.env["risk.module"].sudo()
        domain = [
            ("vehicle_plate", "=", RiskModule._normalize_plate(plate)),
            ("state", "in", RiskModule._active_submission_states()),
        ]
        if exclude_ids:
            domain.append(("id", "not in", list(exclude_ids)))
        duplicate = RiskModule.search(domain, limit=1)

        if duplicate:
            return (
                "Ya existe una solicitud activa para la placa %s. "
                "Finaliza, rechaza o corrige esa solicitud antes de crear una nueva."
            ) % plate
        return None

    def _validate_driver_not_active_on_other_vehicle(self, data):
        driver_document_number = data.get("driver_document_number")
        vehicle_plate = data.get("vehicle_plate")
        if not driver_document_number or not vehicle_plate:
            return None
        submission_id = data.get("submission_id") or request.session.get(
            "risk_submission_id"
        )
        domain = [
            ("state", "=", "approved"),
            ("driver_document_number", "=", driver_document_number),
            ("vehicle_plate", "!=", vehicle_plate),
        ]
        if submission_id:
            domain.append(("id", "!=", int(submission_id)))
        approved = request.env["risk.module"].sudo().search(domain, limit=1)
        if approved:
            return (
                "El conductor con cedula %s ya esta habilitado para el vehiculo %s. "
                "Un conductor solo puede estar activo en un vehiculo."
            ) % (driver_document_number, approved.vehicle_plate)
        return None

    def _validate_text_lengths(self, data):
        """
        Validate that text fields do not exceed maximum lengths and choices are valid.
        
        Args:
            data (dict): The form data.
            
        Returns:
            str or None: Error message if any length or choice is invalid, None otherwise.
        """
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
        """
        Validate document type and number for CC and NIT.
        
        Args:
            document_type (str): 'cc' or 'nit'.
            document_number (str): The document number.
            label (str): Label for error messages (e.g., 'documento del propietario').
            required (bool): Whether the document is mandatory.
            
        Returns:
            str or None: Error message if invalid, None if valid.
        """
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
