import json

from markupsafe import escape

from odoo import fields, models


class RiskExternalValidation(models.Model):
    _name = "risk.external.validation"
    _description = "Validacion externa de riesgo"
    _order = "create_date desc"

    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        required=True,
        ondelete="cascade",
        index=True,
    )
    provider = fields.Selection([
        ("validiti", "Validiti"),
    ], string="Proveedor", required=True, default="validiti")
    profile = fields.Selection([
        ("transport_driver_vehicle", "Conductor y vehiculo de transporte"),
        ("driver", "Conductor"),
        ("owner_company", "Propietario / Empresa"),
        ("vehicle", "Vehiculo"),
    ], string="Perfil", required=True, default="transport_driver_vehicle")
    status = fields.Selection([
        ("pending", "Pendiente"),
        ("sent", "Enviado"),
        ("approved", "Aprobado"),
        ("rejected", "Rechazado"),
        ("manual_review", "Revision manual"),
        ("error", "Error"),
        ("skipped", "Omitido"),
    ], string="Estado", required=True, default="pending")
    decision = fields.Selection([
        ("approved", "Aprobado"),
        ("rejected", "Rechazado"),
        ("manual_review", "Revision manual"),
        ("error", "Error"),
        ("skipped", "Omitido"),
    ], string="Decision")
    external_reference = fields.Char(string="Referencia externa")
    risk_score = fields.Float(string="Puntaje de riesgo")
    summary = fields.Text(string="Resumen")
    request_payload = fields.Text(string="Payload enviado", readonly=True)
    response_payload = fields.Text(string="Respuesta recibida")
    requested_at = fields.Datetime(string="Fecha de envio", readonly=True)
    completed_at = fields.Datetime(string="Fecha de resultado", readonly=True)
    requested_by_id = fields.Many2one("res.users", string="Enviado por", readonly=True)
    completed_by_id = fields.Many2one("res.users", string="Resultado registrado por", readonly=True)

    def action_send_to_validiti(self):
        for record in self:
            payload = record.submission_id._prepare_validiti_payload()
            record.write({
                "status": "sent",
                "request_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                "requested_at": fields.Datetime.now(),
                "requested_by_id": self.env.user.id,
            })
            record.submission_id.write({"state": "external_validation_pending"})
            record.submission_id.message_post(
                body="Validacion externa enviada a Validiti en modo preparado/manual."
            )

    def action_open_result_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Registrar resultado Validiti",
            "res_model": "risk.external.validation.result.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_validation_id": self.id,
                "default_risk_score": self.risk_score,
                "default_summary": self.summary,
                "default_response_payload": self.response_payload,
            },
        }

    def action_skip(self):
        for record in self:
            record.write({
                "status": "skipped",
                "decision": "skipped",
                "completed_at": fields.Datetime.now(),
                "completed_by_id": self.env.user.id,
                "summary": record.summary or "Validacion externa omitida manualmente.",
            })
            record.submission_id.action_skip_external_validation()
            record.submission_id.message_post(body="Validacion externa omitida manualmente.")

    def apply_manual_result(self, decision, summary, risk_score=0.0, response_payload=False, external_reference=False):
        for record in self:
            values = {
                "status": decision,
                "decision": decision,
                "summary": summary,
                "risk_score": risk_score,
                "response_payload": response_payload,
                "external_reference": external_reference,
                "completed_at": fields.Datetime.now(),
                "completed_by_id": self.env.user.id,
            }
            record.write(values)
            record._apply_result_to_submission(summary)

    def _apply_result_to_submission(self, summary):
        self.ensure_one()
        body = (
            "Resultado Validiti registrado: <strong>%s</strong>.<br/><br/>%s"
            % (dict(self._fields["decision"].selection).get(self.decision), escape(summary))
        )
        self.submission_id.message_post(body=body)
        if self.decision == "approved":
            self.submission_id.action_skip_external_validation()
        elif self.decision == "manual_review":
            self.submission_id.action_skip_external_validation()
        elif self.decision == "rejected":
            self.submission_id.write({
                "state": "rejected",
                "rejection_user_id": self.env.user.id,
                "rejection_date": fields.Datetime.now(),
                "rejection_reason": summary,
            })
        elif self.decision == "error":
            self.submission_id.write({"state": "external_validation_pending"})
