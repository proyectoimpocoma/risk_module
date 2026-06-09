from markupsafe import escape

from odoo import fields, models


class RiskSubmissionWorkflow(models.Model):
    _inherit = "risk.module"

    def action_start_risk_review(self):
        self.write({"state": "risk_review"})

    def action_skip_external_validation(self):
        self.write({
            "state": "manual_approval_pending",
            "risk_reviewer_id": self.env.user.id,
            "risk_reviewed_at": fields.Datetime.now(),
        })

    def action_approve(self):
        self.ensure_one()
        return self._approval_wizard_action("approve")

    def action_reject(self):
        self.ensure_one()
        return self._approval_wizard_action("reject")

    def action_reset_to_submitted(self):
        self.write({
            "state": "submitted",
            "approval_user_id": False,
            "approval_date": False,
            "approval_note": False,
            "rejection_user_id": False,
            "rejection_date": False,
            "rejection_reason": False,
        })

    def _approval_wizard_action(self, decision):
        return {
            "type": "ir.actions.act_window",
            "name": "Aprobacion manual" if decision == "approve" else "Rechazo manual",
            "res_model": "risk.approval.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_submission_id": self.id,
                "default_decision": decision,
            },
        }

    def action_confirm_approval(self, note=False):
        for record in self:
            record._check_documents_ready_for_approval()
            record.write({
                "state": "approved",
                "approval_user_id": self.env.user.id,
                "approval_date": fields.Datetime.now(),
                "approval_note": note,
                "rejection_user_id": False,
                "rejection_date": False,
                "rejection_reason": False,
            })
            body = "Solicitud aprobada manualmente."
            if note:
                body = "%s<br/><br/><strong>Comentario:</strong> %s" % (body, escape(note))
            record.message_post(body=body)

    def action_confirm_rejection(self, reason):
        for record in self:
            record.write({
                "state": "rejected",
                "rejection_user_id": self.env.user.id,
                "rejection_date": fields.Datetime.now(),
                "rejection_reason": reason,
                "approval_user_id": False,
                "approval_date": False,
                "approval_note": False,
            })
            record.message_post(
                body="Solicitud rechazada manualmente.<br/><br/><strong>Motivo:</strong> %s" % escape(reason)
            )
