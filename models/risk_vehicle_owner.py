from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RiskVehicleOwner(models.Model):
    _name = "risk.vehicle.owner"
    _description = "Relacion vehiculo propietario"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "vehicle_id, role, date_from desc, id desc"

    active = fields.Boolean(default=True, tracking=True)
    vehicle_id = fields.Many2one(
        "risk.vehicle",
        string="Vehiculo",
        required=True,
        index=True,
        ondelete="cascade",
    )
    owner_id = fields.Many2one(
        "risk.owner",
        string="Propietario / Tenedor",
        required=True,
        index=True,
        ondelete="restrict",
    )
    role = fields.Selection(
        [
            ("owner", "Propietario"),
            ("holder", "Tenedor"),
            ("possessor", "Poseedor"),
        ],
        string="Relacion",
        default="owner",
        required=True,
        tracking=True,
    )
    date_from = fields.Date(string="Desde", default=fields.Date.context_today)
    date_to = fields.Date(string="Hasta")
    notes = fields.Text(string="Notas")

    @api.constrains("active", "vehicle_id", "owner_id", "role")
    def _check_single_active_relation(self):
        for record in self:
            if not record.active:
                continue
            duplicate = self.search(
                [
                    ("id", "!=", record.id),
                    ("active", "=", True),
                    ("vehicle_id", "=", record.vehicle_id.id),
                    ("owner_id", "=", record.owner_id.id),
                    ("role", "=", record.role),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError("Ya existe una relacion activa igual para este vehiculo.")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError("La fecha final no puede ser anterior a la fecha inicial.")
