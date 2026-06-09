from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRiskSubmission(TransactionCase):
    def setUp(self):
        super().setUp()
        self.submission = self.env["risk.module"].create({
            "vehicle_plate": "abc123",
            "form_date": "2026-05-09",
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

    def test_create_normalizes_plate(self):
        self.assertEqual(self.submission.vehicle_plate, "ABC123")

    def test_request_documents_generates_required_templates(self):
        self.submission.action_request_documents()

        self.assertEqual(self.submission.state, "documents_requested")
        document_types = set(self.submission.document_ids.mapped("document_type"))
        self.assertIn("driver_id", document_types)
        self.assertIn("vehicle_registration", document_types)
        self.assertIn("owner_security_study", document_types)
        self.assertIn("driver_security_study", document_types)

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
