from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..risk_validation_rules import CC_REGEX, EMAIL_REGEX, NIT_REGEX, is_valid_mobile_phone


class RiskOwner(models.Model):
    _name = "risk.owner"
    _description = "Propietario o tenedor de riesgo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, document_number"

    active = fields.Boolean(default=True, tracking=True)
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
    email = fields.Char(string="Correo electronico", tracking=True)
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
    owner_document_ids = fields.Many2many(
        "risk.module.document",
        string="Documentos del propietario",
        compute="_compute_owner_document_ids",
    )

    _sql_constraints = [
        (
            "document_unique",
            "unique(document_type, document_number)",
            "Ya existe un propietario con este documento.",
        ),
    ]

    @api.depends("document_number")
    def _compute_owner_document_ids(self):
        """Gather documents (party owner) from this owner's submissions,
        excluding rejected. Covers the owner both as the primary owner of a
        submission and as a registered/additional owner: the latter are linked
        to the vehicle through risk.vehicle.owner, so we also pull the
        owner-documents of the submissions of those vehicles."""
        Document = self.env["risk.module.document"].sudo()
        Link = self.env["risk.vehicle.owner"].sudo().with_context(active_test=False)
        for record in self:
            if not record.id:
                record.owner_document_ids = False
                continue
            vehicle_ids = Link.search(
                [("owner_id", "=", record.id)]
            ).mapped("vehicle_id").ids
            record.owner_document_ids = Document.search(
                [
                    ("party", "=", "owner"),
                    ("state", "in", ["pending", "received", "approved"]),
                    "|",
                    ("submission_id.owner_id", "=", record.id),
                    ("submission_id.vehicle_id", "in", vehicle_ids),
                ],
                order="submission_id desc, sequence, id",
            )

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
