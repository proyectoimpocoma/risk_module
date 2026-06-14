from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..risk_validation_rules import CC_REGEX, EMAIL_REGEX, is_valid_mobile_phone, is_valid_phone


class RiskDriver(models.Model):
    _name = "risk.driver"
    _description = "Conductor de riesgo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, document_number"

    active = fields.Boolean(default=True)
    name = fields.Char(string="Nombres y apellidos", required=True, tracking=True)
    document_number = fields.Char(string="Cedula", required=True, index=True, tracking=True)
    phone = fields.Char(string="Celular", tracking=True)
    optional_phone = fields.Char(string="Telefono opcional")
    email = fields.Char(string="Correo electronico")
    current_vehicle_id = fields.Many2one(
        "risk.vehicle",
        string="Vehiculo actual",
        tracking=True,
        copy=False,
    )

    _sql_constraints = [
        (
            "document_number_unique",
            "unique(document_number)",
            "Ya existe un conductor con esta cedula.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_driver_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_driver_vals(vals)
        return super().write(vals)

    @api.constrains("document_number")
    def _check_document_number(self):
        for record in self:
            if record.document_number and not CC_REGEX.match(record.document_number):
                raise ValidationError("La cedula del conductor debe tener entre 6 y 10 numeros.")

    @api.constrains("phone")
    def _check_phone(self):
        for record in self:
            if record.phone and not is_valid_mobile_phone(record.phone):
                raise ValidationError("El celular del conductor debe tener 10 digitos e iniciar por 3.")

    @api.constrains("optional_phone")
    def _check_optional_phone(self):
        for record in self:
            if record.optional_phone and not is_valid_phone(record.optional_phone):
                raise ValidationError("El telefono opcional del conductor no tiene un formato valido.")

    @api.constrains("email")
    def _check_email(self):
        for record in self:
            if record.email and not EMAIL_REGEX.match(record.email):
                raise ValidationError("El correo electronico del conductor no tiene un formato valido.")

    @api.constrains("current_vehicle_id")
    def _check_current_vehicle_assignment(self):
        for record in self:
            vehicle = record.current_vehicle_id
            if vehicle and vehicle.current_driver_id and vehicle.current_driver_id != record:
                raise ValidationError(
                    "El vehiculo ya esta asignado al conductor %s."
                    % vehicle.current_driver_id.display_name
                )

    @api.model
    def _normalize_driver_vals(self, vals):
        if "name" in vals and vals.get("name"):
            vals["name"] = vals["name"].strip()
        if "document_number" in vals and vals.get("document_number"):
            vals["document_number"] = vals["document_number"].strip()
        if "email" in vals and vals.get("email"):
            vals["email"] = vals["email"].strip().lower()
