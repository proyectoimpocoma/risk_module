from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..risk_validation_rules import PLATE_REGEX, SEMI_TRAILER_PLATE_REGEX


class RiskVehicle(models.Model):
    _name = "risk.vehicle"
    _description = "Vehiculo de riesgo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "plate"
    _order = "plate"

    active = fields.Boolean(default=True)
    plate = fields.Char(string="Placa", required=True, index=True, tracking=True)
    semi_trailer_plate = fields.Char(string="Semi/Remolque", tracking=True)
    current_driver_id = fields.Many2one(
        "risk.driver",
        string="Conductor actual",
        tracking=True,
        copy=False,
    )
    owner_link_ids = fields.One2many(
        "risk.vehicle.owner",
        "vehicle_id",
        string="Propietarios / tenedores",
    )
    status = fields.Selection(
        [
            ("available", "Disponible"),
            ("enabled", "Habilitado"),
            ("blocked", "Bloqueado"),
        ],
        string="Estado",
        default="available",
        required=True,
        tracking=True,
    )

    _sql_constraints = [
        ("plate_unique", "unique(plate)", "Ya existe un vehiculo con esta placa."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_vehicle_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._normalize_vehicle_vals(vals)
        return super().write(vals)

    @api.constrains("plate")
    def _check_plate(self):
        for record in self:
            if record.plate and not PLATE_REGEX.match(record.plate):
                raise ValidationError("La placa del vehiculo debe tener formato ABC123 o ABC12.")

    @api.constrains("semi_trailer_plate")
    def _check_semi_trailer_plate(self):
        for record in self:
            if record.semi_trailer_plate and not SEMI_TRAILER_PLATE_REGEX.match(record.semi_trailer_plate):
                raise ValidationError("La placa del semi/remolque debe tener formato A12345.")

    @api.constrains("current_driver_id")
    def _check_current_driver_assignment(self):
        for record in self:
            driver = record.current_driver_id
            if driver and driver.current_vehicle_id and driver.current_vehicle_id != record:
                raise ValidationError(
                    "El conductor ya esta asignado al vehiculo %s."
                    % driver.current_vehicle_id.display_name
                )

    @api.model
    def _normalize_vehicle_vals(self, vals):
        if "plate" in vals and vals.get("plate"):
            vals["plate"] = vals["plate"].strip().upper()
        if "semi_trailer_plate" in vals and vals.get("semi_trailer_plate"):
            vals["semi_trailer_plate"] = vals["semi_trailer_plate"].strip().upper()

    @api.model
    def find_by_plate(self, plate):
        plate = (plate or "").strip().upper()
        if not plate:
            return self.browse()
        return self.sudo().with_context(active_test=False).search(
            [("plate", "=", plate)],
            limit=1,
        )

    def assignment_conflict_for_driver(self, driver_document_number):
        self.ensure_one()
        driver_document_number = (driver_document_number or "").strip()
        if (
            not self.current_driver_id
            or not driver_document_number
            or self.current_driver_id.document_number == driver_document_number
        ):
            return False
        return self.current_driver_id
