import logging

from odoo import fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


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
        _logger.info(
            "Approval wizard confirmed submission_id=%s decision=%s user_id=%s",
            self.submission_id.id,
            self.decision,
            self.env.user.id,
        )
        if self.decision == "approve":
            self.submission_id.action_confirm_approval(self.approval_note)
        else:
            if not self.rejection_reason or not self.rejection_reason.strip():
                _logger.warning("Approval wizard rejection blocked missing reason submission_id=%s user_id=%s", self.submission_id.id, self.env.user.id)
                raise ValidationError("Debes indicar el motivo del rechazo.")
            self.submission_id.action_confirm_rejection(self.rejection_reason.strip())
        return {"type": "ir.actions.act_window_close"}
