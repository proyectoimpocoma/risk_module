import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RiskExternalValidationResultWizard(models.TransientModel):
    _name = "risk.external.validation.result.wizard"
    _description = "Resultado manual de validacion externa"

    validation_id = fields.Many2one(
        "risk.external.validation",
        string="Validacion",
        required=True,
        readonly=True,
    )
    decision = fields.Selection([
        ("approved", "Aprobado"),
        ("manual_review", "Revision manual"),
        ("rejected", "Rechazado"),
        ("error", "Error"),
    ], string="Decision", required=True)
    external_reference = fields.Char(string="Referencia externa")
    risk_score = fields.Float(string="Puntaje de riesgo")
    message_template_id = fields.Many2one(
        "risk.message.template",
        string="Motivo de rechazo",
        domain="[('category', '=', 'submission_rejection'), ('active', '=', True)]",
    )
    summary = fields.Text(string="Resumen", required=True)
    response_payload = fields.Text(string="Respuesta / evidencia")

    @api.onchange("decision")
    def _onchange_decision(self):
        for wizard in self:
            if wizard.decision != "rejected":
                wizard.message_template_id = False

    @api.onchange("message_template_id")
    def _onchange_message_template_id(self):
        for wizard in self:
            if wizard.message_template_id:
                wizard.summary = wizard.message_template_id.body

    def action_confirm(self):
        self.ensure_one()
        if self.decision == "rejected":
            if not self.message_template_id:
                raise ValidationError("Debes seleccionar un motivo de rechazo.")
            self.summary = (self.message_template_id.body or "").strip()
        if not (self.summary or "").strip():
            _logger.warning(
                "External validation result wizard blocked missing summary validation_id=%s user_id=%s",
                self.validation_id.id,
                self.env.user.id,
            )
            raise ValidationError("Debes escribir un resumen del resultado.")
        _logger.info(
            "External validation result wizard confirmed validation_id=%s submission_id=%s decision=%s user_id=%s",
            self.validation_id.id,
            self.validation_id.submission_id.id,
            self.decision,
            self.env.user.id,
        )
        self.validation_id.apply_manual_result(
            self.decision,
            self.summary.strip(),
            risk_score=self.risk_score,
            response_payload=self.response_payload,
            external_reference=self.external_reference,
        )
        return {"type": "ir.actions.act_window_close"}
