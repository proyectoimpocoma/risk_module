import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RiskDocumentRejectWizard(models.TransientModel):
    _name = "risk.module.document.reject.wizard"
    _description = "Rechazo de documento de riesgo"

    document_id = fields.Many2one(
        "risk.module.document",
        string="Documento",
        required=True,
        readonly=True,
    )
    rejection_reason = fields.Selection(
        selection=lambda self: self.env["risk.module.document"]._fields[
            "rejection_reason"
        ].selection,
        string="Motivo de rechazo",
        required=True,
    )
    observations = fields.Text(
        string="Mensaje para el usuario",
        required=True,
    )

    def _default_document_id(self):
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if active_model == "risk.module.document" and active_id:
            return active_id
        return False

    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        document_id = values.get("document_id") or self._default_document_id()
        if document_id:
            document = self.env["risk.module.document"].browse(document_id)
            values["document_id"] = document.id
            if document.rejection_reason:
                values["rejection_reason"] = document.rejection_reason
            if document.observations:
                values["observations"] = document.observations
        return values

    def _rejection_message(self, reason):
        return self.env["risk.module.document"]._rejection_reason_message(reason)

    @api.onchange("rejection_reason")
    def _onchange_rejection_reason(self):
        for wizard in self:
            message = wizard._rejection_message(wizard.rejection_reason)
            if message:
                wizard.observations = message

    def action_confirm(self):
        self.ensure_one()
        if not (self.observations or "").strip():
            raise ValidationError("Debes indicar el mensaje que recibira el usuario.")
        _logger.info(
            "Document rejection wizard confirmed document_id=%s reason=%s user_id=%s",
            self.document_id.id,
            self.rejection_reason,
            self.env.user.id,
        )
        self.document_id.write(
            {
                "rejection_reason": self.rejection_reason,
                "observations": self.observations.strip(),
            }
        )
        self.document_id.action_confirm_rejection()
        return {"type": "ir.actions.act_window_close"}
