import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


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
            _logger.debug("Document onchange marked received document_id=%s", self.id or "new")
            self.state = "received"

    @api.constrains("state", "observations")
    def _check_rejection_observations(self):
        for record in self:
            if record.state == "rejected" and not (record.observations or "").strip():
                _logger.warning("Document rejection blocked missing observations document_id=%s", record.id)
                raise ValidationError("Debes indicar observaciones para rechazar un documento.")

    @api.constrains("state", "file")
    def _check_approved_file(self):
        for record in self:
            if record.state == "approved" and not record.file:
                _logger.warning("Document approval blocked missing file document_id=%s", record.id)
                raise ValidationError("No puedes aprobar un documento sin archivo adjunto.")

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("Creating risk documents count=%s user_id=%s", len(vals_list), self.env.user.id)
        for vals in vals_list:
            if vals.get("file") and vals.get("state", "pending") == "pending":
                vals["state"] = "received"
        records = super().create(vals_list)
        for record in records:
            _logger.info(
                "Risk document created document_id=%s submission_id=%s type=%s state=%s required=%s",
                record.id,
                record.submission_id.id,
                record.document_type,
                record.state,
                record.required,
            )
        completed_submissions = records.mapped("submission_id").filtered(
            lambda submission: submission.state == "documents_requested"
            and submission._all_required_documents_uploaded()
        )
        if completed_submissions:
            completed_submissions.action_mark_documents_sent_if_complete()
        return records

    def write(self, vals):
        pending_records = self.env["risk.module.document"]
        if vals.get("file") and not vals.get("state"):
            pending_records = self.filtered(lambda record: record.state == "pending")
        old_states = {record.id: record.state for record in self}
        _logger.debug("Writing risk documents ids=%s fields=%s user_id=%s", self.ids, sorted(vals.keys()), self.env.user.id)
        result = super().write(vals)
        if pending_records:
            super(RiskSubmissionDocument, pending_records).write({"state": "received"})
            _logger.info("Risk documents auto-marked received document_ids=%s", pending_records.ids)
        if "state" in vals:
            for record in self:
                _logger.info(
                    "Risk document state changed document_id=%s submission_id=%s old_state=%s new_state=%s user_id=%s",
                    record.id,
                    record.submission_id.id,
                    old_states.get(record.id),
                    record.state,
                    self.env.user.id,
                )
        completed_submissions = self.mapped("submission_id").filtered(
            lambda submission: submission.state == "documents_requested"
            and submission._all_required_documents_uploaded()
        )
        if completed_submissions:
            completed_submissions.action_mark_documents_sent_if_complete()
        return result

    def action_mark_received(self):
        _logger.info("Marking risk documents received document_ids=%s user_id=%s", self.ids, self.env.user.id)
        self.write({"state": "received"})

    def action_approve(self):
        for record in self:
            if not record.file:
                _logger.warning("Document approval action blocked missing file document_id=%s", record.id)
                raise ValidationError("No puedes aprobar un documento sin archivo adjunto.")
        _logger.info("Approving risk documents document_ids=%s user_id=%s", self.ids, self.env.user.id)
        self.write({"state": "approved"})

    def action_reject(self):
        for record in self:
            if not (record.observations or "").strip():
                _logger.warning("Document rejection action blocked missing observations document_id=%s", record.id)
                raise ValidationError("Debes indicar observaciones para rechazar un documento.")
        _logger.info("Rejecting risk documents document_ids=%s user_id=%s", self.ids, self.env.user.id)
        self.write({"state": "rejected"})
        for record in self:
            if record.submission_id:
                record.submission_id.action_send_document_rejected_email(record)
