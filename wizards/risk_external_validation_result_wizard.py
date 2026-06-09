from odoo import fields, models
from odoo.exceptions import ValidationError


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
    summary = fields.Text(string="Resumen", required=True)
    response_payload = fields.Text(string="Respuesta / evidencia")

    def action_confirm(self):
        self.ensure_one()
        if not (self.summary or "").strip():
            raise ValidationError("Debes escribir un resumen del resultado.")
        self.validation_id.apply_manual_result(
            self.decision,
            self.summary.strip(),
            risk_score=self.risk_score,
            response_payload=self.response_payload,
            external_reference=self.external_reference,
        )
        return {"type": "ir.actions.act_window_close"}
