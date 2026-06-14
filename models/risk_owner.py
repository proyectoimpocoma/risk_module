from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..risk_validation_rules import CC_REGEX, EMAIL_REGEX, NIT_REGEX, is_valid_mobile_phone


class RiskOwner(models.Model):
    _name = "risk.owner"
    _description = "Propietario o tenedor de riesgo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, document_number"

    active = fields.Boolean(default=True)
    name = fields.Char(string="Nombres y apellidos / Empresa", required=True, tracking=True)
    document_type = fields.Selection(
        [
            ("cc", "CC"),
            ("nit", "Nit"),
        ],
        string="Tipo de documento",
        default="cc",
        required=True,
        tracking=True,
    )
    document_number = fields.Char(string="Numero de documento", required=True, index=True, tracking=True)
    phone = fields.Char(string="Celular", tracking=True)
    email = fields.Char(string="Correo electronico")
    owner_kind = fields.Selection(
        [
            ("natural", "Persona natural"),
            ("company", "Empresa"),
        ],
        string="Tipo de propietario",
        compute="_compute_owner_kind",
        store=True,
    )
    vehicle_link_ids = fields.One2many(
        "risk.vehicle.owner",
        "owner_id",
        string="Vehiculos relacionados",
    )

    _sql_constraints = [
        (
            "document_unique",
            "unique(document_type, document_number)",
            "Ya existe un propietario con este documento.",
        ),
    ]

    @api.depends("document_type")
    def _compute_owner_kind(self):
        for record in self:
            record.owner_kind = "company" if record.document_type == "nit" else "natural"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_owner_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_owner_vals(vals)
        return super().write(vals)

    @api.constrains("document_type", "document_number")
    def _check_document_number(self):
        for record in self:
            if not record.document_number:
                continue
            pattern = NIT_REGEX if record.document_type == "nit" else CC_REGEX
            if not pattern.match(record.document_number):
                if record.document_type == "nit":
                    raise ValidationError("El NIT debe tener entre 6 y 10 numeros y puede incluir digito de verificacion.")
                raise ValidationError("La cedula del propietario debe tener entre 6 y 10 numeros.")

    @api.constrains("phone")
    def _check_phone(self):
        for record in self:
            if record.phone and not is_valid_mobile_phone(record.phone):
                raise ValidationError("El celular del propietario debe tener 10 digitos e iniciar por 3.")

    @api.constrains("email")
    def _check_email(self):
        for record in self:
            if record.email and not EMAIL_REGEX.match(record.email):
                raise ValidationError("El correo electronico del propietario no tiene un formato valido.")

    @api.model
    def _normalize_owner_vals(self, vals):
        if "name" in vals and vals.get("name"):
            vals["name"] = vals["name"].strip()
        if "document_number" in vals and vals.get("document_number"):
            vals["document_number"] = vals["document_number"].strip()
        if "email" in vals and vals.get("email"):
            vals["email"] = vals["email"].strip().lower()
