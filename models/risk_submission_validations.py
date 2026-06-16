from odoo import api, models
from odoo.exceptions import ValidationError

from ..risk_validation_rules import (
    CC_REGEX,
    EMAIL_REGEX,
    NIT_REGEX,
    PLATE_REGEX,
    SEMI_TRAILER_PLATE_REGEX,
)


class RiskSubmissionValidations(models.Model):
    _inherit = "risk.module"

    @api.constrains("vehicle_plate", "state")
    def _check_single_active_submission_per_plate(self):
        """Avoid more than one active onboarding request per vehicle plate."""
        for record in self:
            if (
                not record.vehicle_plate
                or record.state not in record._active_submission_states()
            ):
                continue
            duplicate = record._find_active_submission_for_plate(
                record.vehicle_plate,
                exclude_id=record.id,
            )
            if duplicate:
                raise ValidationError(
                    "Ya existe una solicitud activa para la placa %s. "
                    "Finaliza, rechaza o corrige esa solicitud antes de crear una nueva."
                    % record.vehicle_plate
                )

    @api.constrains(
        "single_owner_driver_signature",
        "owner_document_type",
        "owner_document_number",
        "driver_document_number",
    )
    def _check_single_signature_matches_owner_and_driver(self):
        """Require same natural-person document before using one signature."""
        for record in self:
            if record.single_owner_driver_signature != "yes":
                continue
            owner_document_number = (record.owner_document_number or "").strip()
            driver_document_number = (record.driver_document_number or "").strip()
            if (
                record.owner_document_type != "cc"
                or not owner_document_number
                or not driver_document_number
                or owner_document_number != driver_document_number
            ):
                raise ValidationError(
                    "Para usar firma unica, el propietario y el conductor deben "
                    "ser la misma persona y tener el mismo numero de cedula."
                )

    @api.constrains("owner_email")
    def _check_owner_email(self):
        """Valida que el correo del propietario tenga un formato valido."""
        for record in self:
            if record.owner_email and not EMAIL_REGEX.match(record.owner_email.strip()):
                raise ValidationError(
                    f'El correo "{record.owner_email}" no tiene un formato valido.\n'
                    "Ejemplo: propietario@empresa.com"
                )

    @api.constrains("driver_email")
    def _check_driver_email(self):
        """Valida que el correo del conductor tenga un formato valido."""
        for record in self:
            if record.driver_email and not EMAIL_REGEX.match(
                record.driver_email.strip()
            ):
                raise ValidationError(
                    f'El correo "{record.driver_email}" no tiene un formato valido.\n'
                    "Ejemplo: conductor@empresa.com"
                )

    @api.constrains("owner_document_number", "owner_document_type")
    def _check_owner_document_number(self):
        """Valida el numero de documento del propietario segun el tipo."""
        for record in self:
            num = record.owner_document_number
            if not num:
                continue
            num = num.strip()
            if record.owner_document_type == "cc":
                if not CC_REGEX.fullmatch(num):
                    raise ValidationError(
                        f'La cedula "{num}" debe contener entre 6 y 10 digitos numericos.'
                    )
            elif record.owner_document_type == "nit":
                if not NIT_REGEX.fullmatch(num):
                    raise ValidationError(
                        f'El NIT "{num}" debe tener el formato: 123456789 o 123456789-0'
                    )

    @api.constrains("driver_document_number")
    def _check_driver_document_number(self):
        """Valida la cedula del conductor."""
        for record in self:
            if record.driver_document_number and not CC_REGEX.fullmatch(record.driver_document_number.strip()):
                raise ValidationError(
                    f'La cedula del conductor "{record.driver_document_number}" debe contener entre 6 y 10 digitos numericos.'
                )

    @api.constrains(
        "owner_phone",
        "registered_owner_phone",
        "driver_phone",
        "family_reference_phone",
        "cargo_reference_phone",
    )
    def _check_mobile_phones(self):
        """Valida celulares colombianos."""
        labels = {
            "owner_phone": "celular del propietario",
            "registered_owner_phone": "celular del propietario registrado",
            "driver_phone": "celular del conductor",
            "family_reference_phone": "celular de referencia familiar",
            "cargo_reference_phone": "celular de referencia de carga",
        }
        for record in self:
            for field_name, label in labels.items():
                value = getattr(record, field_name)
                if value and not self._is_valid_mobile_phone(value):
                    raise ValidationError(
                        f"El {label} debe ser un celular colombiano de 10 digitos que inicia por 3."
                    )

    @api.constrains("driver_optional_phone")
    def _check_optional_phone(self):
        """Valida telefono opcional fijo o movil."""
        for record in self:
            if record.driver_optional_phone and not self._is_valid_phone(
                record.driver_optional_phone
            ):
                raise ValidationError(
                    "El telefono opcional debe tener 7 digitos o 10 digitos iniciando por 3 o 6."
                )

    @api.constrains("vehicle_plate", "semi_trailer_plate")
    def _check_plate_format(self):
        """Valida que las placas tengan el formato colombiano valido."""
        for record in self:
            for field_name, label in [
                ("vehicle_plate", "Placa del vehiculo"),
                ("semi_trailer_plate", "Placa del semi/remolque"),
            ]:
                plate = getattr(record, field_name)
                if not plate:
                    continue
                normalized = self._normalize_plate(plate)
                if field_name == "vehicle_plate":
                    valid = PLATE_REGEX.match(normalized)
                else:
                    valid = SEMI_TRAILER_PLATE_REGEX.match(normalized)
                if not valid:
                    if field_name == "vehicle_plate":
                        raise ValidationError(
                            f'{label} "{normalized}" no tiene el formato colombiano valido.\n'
                            "Formato aceptado: ABC123 (3 letras + 3 digitos)."
                        )
                    raise ValidationError(
                        f'{label} "{normalized}" no tiene el formato valido.\n'
                        "Formato aceptado: A12345 (una letra y cinco digitos)."
                    )

    @api.onchange("vehicle_plate")
    def _onchange_vehicle_plate(self):
        """Normaliza la placa a mayusculas y advierte si el formato es invalido."""
        if not self.vehicle_plate:
            return
        self.vehicle_plate = self._normalize_plate(self.vehicle_plate)
        if not PLATE_REGEX.match(self.vehicle_plate):
            return {
                "warning": {
                    "title": "Formato de placa invalido",
                    "message": (
                        f'La placa "{self.vehicle_plate}" no tiene el formato colombiano valido.\n\n'
                        "Formato aceptado: ABC123 (3 letras + 3 digitos)."
                    ),
                }
            }
        return None

    @api.onchange("semi_trailer_plate")
    def _onchange_semi_trailer_plate(self):
        """Normaliza la placa del semi a mayusculas y advierte si el formato es invalido."""
        if not self.semi_trailer_plate:
            return
        self.semi_trailer_plate = self._normalize_plate(self.semi_trailer_plate)
        if not SEMI_TRAILER_PLATE_REGEX.match(self.semi_trailer_plate):
            return {
                "warning": {
                    "title": "Formato de semi/remolque invalido",
                    "message": (
                        f'La placa "{self.semi_trailer_plate}" debe tener el formato A12345.\n'
                        "Una letra seguida de cinco digitos."
                    ),
                }
            }
        return None

    def _approved_vehicle_driver_conflict(self):
        """Return an approved submission for the same plate with another driver."""
        self.ensure_one()
        if not self.vehicle_plate or not self.driver_document_number:
            return self.browse()
        approved_for_plate = self.search(
            [
                ("id", "!=", self.id),
                ("state", "=", "approved"),
                ("vehicle_plate", "=", self.vehicle_plate),
            ],
            order="approval_date desc, id desc",
            limit=20,
        )
        return approved_for_plate.filtered(
            lambda item: item.driver_document_number
            and item.driver_document_number != self.driver_document_number
        )[:1]

    def _approved_driver_vehicle_conflict(self):
        """Return an approved submission for the same driver with another plate."""
        self.ensure_one()
        if not self.vehicle_plate or not self.driver_document_number:
            return self.browse()
        approved_for_driver = self.search(
            [
                ("id", "!=", self.id),
                ("state", "=", "approved"),
                ("driver_document_number", "=", self.driver_document_number),
            ],
            order="approval_date desc, id desc",
            limit=20,
        )
        return approved_for_driver.filtered(
            lambda item: item.vehicle_plate and item.vehicle_plate != self.vehicle_plate
        )[:1]

    def _check_active_vehicle_driver_assignment(self):
        """Validate one active driver per vehicle and one active vehicle per driver."""
        for record in self:
            record._check_master_assignment_conflicts()
            vehicle_conflict = record._approved_vehicle_driver_conflict()
            if vehicle_conflict:
                raise ValidationError(
                    "El vehiculo %s ya se encuentra habilitado con el conductor "
                    "%s. Para continuar debes cerrar o reemplazar la habilitacion "
                    "anterior."
                    % (
                        record.vehicle_plate,
                        vehicle_conflict.driver_document_number,
                    )
                )
            driver_conflict = record._approved_driver_vehicle_conflict()
            if driver_conflict:
                raise ValidationError(
                    "El conductor con cedula %s ya esta habilitado para el "
                    "vehiculo %s. Un conductor solo puede estar activo en un "
                    "vehiculo."
                    % (
                        record.driver_document_number,
                        driver_conflict.vehicle_plate,
                    )
                )
