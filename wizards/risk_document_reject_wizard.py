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
    message_template_id = fields.Many2one(
        "risk.message.template",
        string="Motivo",
        domain="[('category', '=', 'document_rejection'), ('active', '=', True)]",
        required=True,
    )
    rejection_reason = fields.Selection(
        selection=lambda self: self.env["risk.module.document"]._fields[
            "rejection_reason"
        ].selection,
        string="Motivo de rechazo",
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
                template = self.env["risk.message.template"].search(
                    [
                        ("category", "=", "document_rejection"),
                        ("code", "=", document.rejection_reason),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
                if template:
                    values["message_template_id"] = template.id
            if document.observations:
                values["observations"] = document.observations
        return values

    @api.onchange("message_template_id")
    def _onchange_message_template_id(self):
        for wizard in self:
            if not wizard.message_template_id:
                continue
            wizard.observations = wizard.message_template_id.body
            if wizard.message_template_id.code in wizard._document_rejection_codes():
                wizard.rejection_reason = wizard.message_template_id.code
            else:
                wizard.rejection_reason = False

    def _document_rejection_codes(self):
        return {
            code
            for code, _label in self.env["risk.module.document"]._fields[
                "rejection_reason"
            ].selection
        }

    def action_confirm(self):
        self.ensure_one()
        if not self.message_template_id:
            raise ValidationError("Debes seleccionar un motivo de rechazo.")
        if not (self.observations or "").strip():
            raise ValidationError("Debes indicar el mensaje que recibira el usuario.")
        _logger.info(
            "Document rejection wizard confirmed document_id=%s template_id=%s user_id=%s",
            self.document_id.id,
            self.message_template_id.id,
            self.env.user.id,
        )
        rejection_reason = False
        if self.message_template_id.code in self._document_rejection_codes():
            rejection_reason = self.message_template_id.code
        self.document_id.write(
            {
                "rejection_reason": rejection_reason,
                "observations": self.observations.strip(),
            }
        )
        self.document_id.action_confirm_rejection()
        return {"type": "ir.actions.act_window_close"}
