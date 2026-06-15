from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..risk_validation_rules import (
    CC_REGEX,
    EMAIL_REGEX,
    NIT_REGEX,
    is_valid_mobile_phone,
)


class RiskSubmissionOwner(models.Model):
    """Additional owner declared on a submission (beyond the primary tenedor
    and the registered owner). Each line is synced to the master data
    (risk.owner + risk.vehicle.owner) when the submission is finalized."""

    _name = "risk.submission.owner"
    _description = "Propietario adicional de la solicitud"
    _order = "submission_id, sequence, id"

    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        required=True,
        index=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Nombres y apellidos / Empresa", required=True)
    document_type = fields.Selection(
        [
            ("cc", "CC"),
            ("nit", "Nit"),
        ],
        string="Tipo de documento",
        default="cc",
        required=True,
    )
    document_number = fields.Char(string="Numero de documento", required=True)
    role = fields.Selection(
        [
            ("owner", "Propietario"),
            ("holder", "Tenedor"),
            ("possessor", "Poseedor"),
        ],
        string="Relacion",
        default="owner",
        required=True,
    )
    phone = fields.Char(string="Celular")
    email = fields.Char(string="Correo electronico")
    address = fields.Char(string="Direccion")
    neighborhood = fields.Char(string="Barrio")
    city = fields.Char(string="Ciudad")

    @api.constrains("document_type", "document_number")
    def _check_document_number(self):
        for record in self:
            if not record.document_number:
                continue
            pattern = NIT_REGEX if record.document_type == "nit" else CC_REGEX
            if not pattern.match(record.document_number):
                if record.document_type == "nit":
                    raise ValidationError(
                        "El NIT del propietario adicional debe tener formato 123456789 o 12345678-0."
                    )
                raise ValidationError(
                    "La cedula del propietario adicional debe contener entre 6 y 10 digitos numericos."
                )

    @api.constrains("phone")
    def _check_phone(self):
        for record in self:
            if record.phone and not is_valid_mobile_phone(record.phone):
                raise ValidationError(
                    "El celular del propietario adicional debe tener 10 digitos e iniciar por 3."
                )

    @api.constrains("email")
    def _check_email(self):
        for record in self:
            if record.email and not EMAIL_REGEX.match(record.email):
                raise ValidationError(
                    "El correo del propietario adicional no tiene un formato valido."
                )


class RiskSubmissionOwnerLink(models.Model):
    _inherit = "risk.module"

    submission_owner_ids = fields.One2many(
        "risk.submission.owner",
        "submission_id",
        string="Propietarios adicionales",
        copy=True,
    )
