from odoo import fields, models
from odoo.exceptions import ValidationError


class RiskApprovalWizard(models.TransientModel):
    _name = "risk.approval.wizard"
    _description = "Decision manual de solicitud de riesgo"

    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        required=True,
        readonly=True,
    )
    decision = fields.Selection([
        ("approve", "Aprobar"),
        ("reject", "Rechazar"),
    ], string="Decision", required=True, readonly=True)
    approval_note = fields.Text(string="Comentario de aprobacion")
    rejection_reason = fields.Text(string="Motivo de rechazo")

    def action_confirm(self):
        self.ensure_one()
        if self.decision == "approve":
            self.submission_id.action_confirm_approval(self.approval_note)
        else:
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValidationError("Debes indicar el motivo del rechazo.")
            self.submission_id.action_confirm_rejection(self.rejection_reason.strip())
        return {"type": "ir.actions.act_window_close"}
