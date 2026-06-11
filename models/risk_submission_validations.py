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
                            "Formatos aceptados:\n"
                            "  • Vehiculo / carga: ABC123 (3 letras + 3 digitos)\n"
                            "  • Motocicleta     : ABC12  (3 letras + 2 digitos)"
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
                        "Formatos aceptados:\n"
                        "  • Vehiculo / carga: ABC123 (3 letras + 3 digitos)\n"
                        "  • Motocicleta     : ABC12  (3 letras + 2 digitos)"
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
