from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RiskSubmissionDocument(models.Model):
    _name = "risk.module.document"
    _description = "Documento de solicitud de riesgo"
    _order = "required desc, party, sequence, id"

    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Documento", required=True)
    document_type = fields.Selection([
        ("driver_id", "Cedula del conductor"),
        ("driver_license", "Licencia de conduccion"),
        ("owner_document", "Cedula / NIT del propietario"),
        ("vehicle_registration", "Tarjeta de propiedad"),
        ("soat", "SOAT"),
        ("technical_inspection", "Revision tecnico-mecanica"),
        ("policy", "Poliza"),
        ("owner_security_study", "Estudio de seguridad del propietario"),
        ("driver_security_study", "Estudio de seguridad del conductor"),
        ("semi_registration", "Documento del semi/remolque"),
        ("other", "Otro"),
    ], string="Tipo", required=True, default="other")
    party = fields.Selection([
        ("driver", "Conductor"),
        ("owner", "Propietario"),
        ("vehicle", "Vehiculo"),
        ("semi_trailer", "Semi/Remolque"),
        ("other", "Otro"),
    ], string="Relacionado con", required=True, default="other")
    required = fields.Boolean(string="Obligatorio", default=True)
    file = fields.Binary(string="Archivo", attachment=True)
    filename = fields.Char(string="Nombre de archivo")
    expiration_date = fields.Date(string="Fecha de vencimiento")
    state = fields.Selection([
        ("pending", "Pendiente"),
        ("received", "Recibido"),
        ("approved", "Aprobado"),
        ("rejected", "Rechazado"),
    ], string="Estado", default="pending", required=True)
    observations = fields.Text(string="Observaciones")

    @api.onchange("file")
    def _onchange_file(self):
        if self.file and self.state == "pending":
            self.state = "received"

    @api.constrains("state", "observations")
    def _check_rejection_observations(self):
        for record in self:
            if record.state == "rejected" and not (record.observations or "").strip():
                raise ValidationError("Debes indicar observaciones para rechazar un documento.")

    @api.constrains("state", "file")
    def _check_approved_file(self):
        for record in self:
            if record.state == "approved" and not record.file:
                raise ValidationError("No puedes aprobar un documento sin archivo adjunto.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("file") and vals.get("state", "pending") == "pending":
                vals["state"] = "received"
        return super().create(vals_list)

    def write(self, vals):
        pending_records = self.env["risk.module.document"]
        if vals.get("file") and not vals.get("state"):
            pending_records = self.filtered(lambda record: record.state == "pending")
        result = super().write(vals)
        if pending_records:
            super(RiskSubmissionDocument, pending_records).write({"state": "received"})
        return result

    def action_mark_received(self):
        self.write({"state": "received"})

    def action_approve(self):
        for record in self:
            if not record.file:
                raise ValidationError("No puedes aprobar un documento sin archivo adjunto.")
        self.write({"state": "approved"})

    def action_reject(self):
        for record in self:
            if not (record.observations or "").strip():
                raise ValidationError("Debes indicar observaciones para rechazar un documento.")
        self.write({"state": "rejected"})
