import logging

from markupsafe import escape

from odoo import fields, models

_logger = logging.getLogger(__name__)


class RiskSubmissionWorkflow(models.Model):
    _inherit = "risk.module"

    def action_start_risk_review(self):
        _logger.info(
            "Starting risk review submission_ids=%s user_id=%s",
            self.ids,
            self.env.user.id,
        )
        self.write(
            {
                "state": "risk_review",
                "risk_reviewer_id": self.env.user.id,
                "risk_reviewed_at": fields.Datetime.now(),
            }
        )

    def action_skip_external_validation(self):
        _logger.info(
            "Skipping external validation submission_ids=%s user_id=%s",
            self.ids,
            self.env.user.id,
        )
        self.write(
            {
                "state": "manual_approval_pending",
                "risk_reviewer_id": self.env.user.id,
                "risk_reviewed_at": fields.Datetime.now(),
            }
        )

    def action_approve(self):
        self.ensure_one()
        _logger.info(
            "Opening approval wizard submission_id=%s user_id=%s",
            self.id,
            self.env.user.id,
        )
        return self._approval_wizard_action("approve")

    def action_reject(self):
        self.ensure_one()
        _logger.info(
            "Opening rejection wizard submission_id=%s user_id=%s",
            self.id,
            self.env.user.id,
        )
        return self._approval_wizard_action("reject")

    def action_request_correction(self):
        self.ensure_one()
        _logger.info(
            "Opening correction wizard submission_id=%s user_id=%s",
            self.id,
            self.env.user.id,
        )
        return self._approval_wizard_action("correction")

    def action_reset_to_submitted(self):
        _logger.info(
            "Resetting risk submission to submitted submission_ids=%s user_id=%s",
            self.ids,
            self.env.user.id,
        )
        self.write(
            {
                "state": "submitted",
                "approval_user_id": False,
                "approval_date": False,
                "approval_note": False,
                "rejection_user_id": False,
                "rejection_date": False,
                "rejection_reason": False,
                "correction_reason": False,
                "correction_requested_by_id": False,
                "correction_requested_at": False,
                "correction_submitted_at": False,
                "correction_section_vehicle": False,
                "correction_section_owner": False,
                "correction_section_driver": False,
                "correction_section_satellite": False,
                "correction_section_signatures": False,
                "correction_section_terms": False,
                "correction_section_other": False,
            }
        )

    def _approval_wizard_action(self, decision):
        _logger.debug(
            "Building approval wizard action submission_id=%s decision=%s",
            self.id,
            decision,
        )
        return {
            "type": "ir.actions.act_window",
            "name": {
                "approve": "Aprobacion manual",
                "reject": "Rechazo manual",
                "correction": "Solicitar correccion",
            }.get(decision, "Decision manual"),
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
            _logger.info(
                "Confirming approval submission_id=%s user_id=%s",
                record.id,
                self.env.user.id,
            )
            record._check_documents_ready_for_approval()
            record._check_active_vehicle_driver_assignment()
            record.write(
                {
                    "state": "approved",
                    "approval_user_id": self.env.user.id,
                    "approval_date": fields.Datetime.now(),
                    "approval_note": note,
                    "rejection_user_id": False,
                    "rejection_date": False,
                    "rejection_reason": False,
                    "correction_reason": False,
                    "correction_requested_by_id": False,
                    "correction_requested_at": False,
                    "correction_submitted_at": False,
                }
            )
            body = "Solicitud aprobada manualmente."
            if note:
                body = "%s<br/><br/><strong>Comentario:</strong> %s" % (
                    body,
                    escape(note),
                )
            record.message_post(body=body)
            _logger.info(
                "Approval confirmed submission_id=%s user_id=%s",
                record.id,
                self.env.user.id,
            )

    def action_confirm_rejection(self, reason):
        for record in self:
            _logger.info(
                "Confirming rejection submission_id=%s user_id=%s reason_length=%s",
                record.id,
                self.env.user.id,
                len(reason or ""),
            )
            record.write(
                {
                    "state": "rejected",
                    "rejection_user_id": self.env.user.id,
                    "rejection_date": fields.Datetime.now(),
                    "rejection_reason": reason,
                    "approval_user_id": False,
                    "approval_date": False,
                    "approval_note": False,
                    "correction_reason": False,
                    "correction_requested_by_id": False,
                    "correction_requested_at": False,
                    "correction_submitted_at": False,
                }
            )
            notification_body = (
                "Tu solicitud ha sido rechazada.<br/><br/>"
                "<strong>Motivo:</strong> %s"
            ) % escape(reason)
            record.message_post(
                body=notification_body,
                partner_ids=record._submission_rejection_notification_partner_ids(),
                subtype_xmlid="mail.mt_comment",
            )
            record.action_send_submission_rejected_email()
            _logger.info(
                "Rejection confirmed submission_id=%s user_id=%s",
                record.id,
                self.env.user.id,
            )

    def action_confirm_correction_request(self, reason, sections=None):
        sections = sections or {}
        for record in self:
            _logger.info(
                "Confirming correction request submission_id=%s user_id=%s reason_length=%s sections=%s",
                record.id,
                self.env.user.id,
                len(reason or ""),
                sections,
            )
            record.write(
                {
                    "state": "correction_required",
                    "correction_reason": reason,
                    "correction_requested_by_id": self.env.user.id,
                    "correction_requested_at": fields.Datetime.now(),
                    "correction_submitted_at": False,
                    "correction_count": record.correction_count + 1,
                    "correction_section_vehicle": sections.get("vehicle", False),
                    "correction_section_owner": sections.get("owner", False),
                    "correction_section_driver": sections.get("driver", False),
                    "correction_section_satellite": sections.get("satellite", False),
                    "correction_section_signatures": sections.get("signatures", False),
                    "correction_section_terms": sections.get("terms", False),
                    "correction_section_other": sections.get("other", False),
                    "rejection_user_id": False,
                    "rejection_date": False,
                    "rejection_reason": False,
                }
            )
            notification_body = (
                "Tu solicitud requiere correccion.<br/><br/>"
                "<strong>Motivo:</strong> %s"
            ) % escape(reason)
            record.message_post(
                body=notification_body,
                partner_ids=record._submission_rejection_notification_partner_ids(),
                subtype_xmlid="mail.mt_comment",
            )
            record.action_send_correction_requested_email()

    def action_mark_correction_submitted(self):
        for record in self:
            if record.state != "correction_required":
                continue
            record.write(
                {
                    "state": "correction_submitted",
                    "correction_submitted_at": fields.Datetime.now(),
                }
            )
            record.message_post(body="El tercero envio la correccion de la solicitud.")
