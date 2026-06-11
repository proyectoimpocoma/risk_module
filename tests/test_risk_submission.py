from odoo.fields import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRiskSubmission(TransactionCase):
    def setUp(self):
        super().setUp()
        self.portal_group = self.env.ref("base.group_portal")
        self.portal_user = self._create_portal_user("portal-a@example.com", "Portal A")
        self.other_portal_user = self._create_portal_user("portal-b@example.com", "Portal B")
        self.submission = self.env["risk.module"].create({
            "vehicle_plate": "abc123",
            "form_date": "2026-05-09",
            **self.env["risk.module"]._portal_ownership_values(self.portal_user),
            "owner_name": "Transportes Demo",
            "owner_document_type": "nit",
            "owner_document_number": "123456789-0",
            "owner_phone": "3001234567",
            "owner_email": "operaciones@example.com",
            "driver_name": "Conductor Demo",
            "driver_document_number": "12345678",
            "driver_phone": "3007654321",
            "driver_email": "conductor@example.com",
            "driver_is_fit": "yes",
            "driver_is_trained": "yes",
            "owner_has_valid_study": "yes",
            "driver_has_valid_study": "yes",
        })

    def _create_portal_user(self, login, name):
        return self.env["res.users"].with_context(no_reset_password=True).create({
            "name": name,
            "login": login,
            "email": login,
            "group_ids": [Command.set([self.portal_group.id])],
        })

    def test_create_normalizes_plate(self):
        self.assertEqual(self.submission.vehicle_plate, "ABC123")

    def test_portal_ownership_values_are_assigned(self):
        self.assertEqual(self.submission.partner_id, self.portal_user.partner_id)
        self.assertEqual(self.submission.portal_user_id, self.portal_user)
        self.assertEqual(self.submission.submitted_by_id, self.portal_user)

    def test_portal_ownership_blocks_other_users(self):
        self.assertTrue(self.submission._portal_is_owned_by(self.portal_user))
        self.assertFalse(self.submission._portal_is_owned_by(self.other_portal_user))

    def test_portal_state_labels(self):
        expected = {
            "draft": "En revision",
            "submitted": "En revision",
            "risk_review": "En revision",
            "external_validation_pending": "En revision",
            "manual_approval_pending": "En revision",
            "documents_requested": "Documentos solicitados",
            "documents_review": "Documentos en revision",
            "approved": "Aprobada",
            "rejected": "Rechazada",
        }
        for state, label in expected.items():
            self.submission.state = state
            self.assertEqual(self.submission.portal_state_label, label)

    def test_submission_confirmation_email_is_queued_when_submitted(self):
        self.submission.write({"state": "submitted"})

        self.assertEqual(self.submission.submission_email_status, "sent")
        self.assertEqual(self.submission.submission_email_sent_to, "portal-a@example.com")
        self.assertTrue(self.submission.submission_email_sent_at)
        mail = self.env["mail.mail"].search([
            ("subject", "=", "Solicitud recibida - ABC123"),
        ], limit=1)
        self.assertEqual(mail.email_from, "reporte@impocoma.com")
        self.assertEqual(mail.reply_to, "reporte@impocoma.com")
        self.assertEqual(mail.email_to, "portal-a@example.com")
        self.assertFalse(mail.recipient_ids)

    def test_request_documents_generates_required_templates(self):
        self.submission.action_request_documents()

        self.assertEqual(self.submission.state, "documents_requested")
        document_types = set(self.submission.document_ids.mapped("document_type"))
        self.assertIn("driver_id", document_types)
        self.assertIn("vehicle_registration", document_types)
        self.assertIn("owner_security_study", document_types)
        self.assertIn("driver_security_study", document_types)

    def test_portal_document_upload_allowed_only_when_documents_requested(self):
        self.submission.action_request_documents()
        document = self.submission.document_ids.filtered(lambda item: item.state == "pending")[:1]

        self.assertTrue(self.submission._portal_document_upload_allowed(document))
        self.assertTrue(self.submission._portal_document_upload_allowed(document, self.portal_user))
        self.assertFalse(self.submission._portal_document_upload_allowed(document, self.other_portal_user))

        document.state = "received"
        self.assertFalse(self.submission._portal_document_upload_allowed(document, self.portal_user))

        document.state = "pending"
        self.submission.state = "documents_review"
        self.assertFalse(self.submission._portal_document_upload_allowed(document, self.portal_user))

    def test_cannot_approve_without_approved_documents(self):
        self.submission.action_request_documents()

        with self.assertRaises(ValidationError):
            self.submission.action_confirm_approval("Ok")

    def test_approval_after_documents_are_approved(self):
        self.submission.action_request_documents()
        self.submission.document_ids.write({
            "file": "ZHVtbXk=",
            "filename": "documento.pdf",
            "state": "approved",
        })
        self.submission.write({"state": "documents_review"})

        self.submission.action_confirm_approval("Documentos completos")

        self.assertEqual(self.submission.state, "approved")
        self.assertEqual(self.submission.approval_user_id, self.env.user)
        self.assertFalse(self.submission.rejection_user_id)

    def test_validiti_manual_approval_moves_to_manual_approval(self):
        validation = self.submission._ensure_validiti_validation()

        validation.apply_manual_result(
            decision="approved",
            summary="Sin hallazgos",
            risk_score=5.0,
            external_reference="VALIDITI-1",
        )

        self.assertEqual(validation.status, "approved")
        self.assertEqual(self.submission.state, "manual_approval_pending")
        self.assertEqual(self.submission.risk_reviewer_id, self.env.user)
