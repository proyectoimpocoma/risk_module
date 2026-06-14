from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError

from .common import RiskModuleTestCase


class TestRiskSubmission(RiskModuleTestCase):
    def setUp(self):
        super().setUp()
        self.portal_user = self.make_portal_user(self.TEST_PORTAL_A, "Portal A")
        self.other_portal_user = self.make_portal_user(
            self.TEST_PORTAL_B, "Portal B"
        )
        self.submission = self.make_submission(owner=self.portal_user)

    def test_create_normalizes_plate(self):
        self.assertEqual(self.submission.vehicle_plate, "ABC123")

    def test_portal_ownership_values_are_assigned(self):
        self.assertEqual(self.submission.partner_id, self.portal_user.partner_id)
        self.assertEqual(self.submission.portal_user_id, self.portal_user)
        self.assertEqual(self.submission.submitted_by_id, self.portal_user)

    def test_portal_ownership_blocks_other_users(self):
        self.assertTrue(self.submission._portal_is_owned_by(self.portal_user))
        self.assertFalse(self.submission._portal_is_owned_by(self.other_portal_user))

    def test_master_records_are_synced_from_submission(self):
        self.submission.write(
            {
                "same_owner_on_license": "no",
                "registered_owner_document_type": "cc",
                "registered_owner_document_number": "87654321",
                "registered_owner_name": "Propietario Registrado",
                "registered_owner_phone": "3001112233",
            }
        )

        self.submission._sync_master_records()

        self.assertEqual(self.submission.vehicle_id.plate, "ABC123")
        self.assertEqual(self.submission.driver_id.document_number, "12345678")
        self.assertEqual(self.submission.owner_id.document_number, "123456789-0")
        self.assertEqual(self.submission.vehicle_owner_link_id.role, "holder")
        registered_owner = self.env["risk.owner"].search(
            [
                ("document_type", "=", "cc"),
                ("document_number", "=", "87654321"),
            ],
            limit=1,
        )
        self.assertTrue(registered_owner)
        self.assertTrue(
            self.env["risk.vehicle.owner"].search(
                [
                    ("vehicle_id", "=", self.submission.vehicle_id.id),
                    ("owner_id", "=", registered_owner.id),
                    ("role", "=", "owner"),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )

    def test_master_assignment_is_activated_on_approval(self):
        self.submission._sync_master_records(activate_assignment=True)

        self.assertEqual(self.submission.vehicle_id.current_driver_id, self.submission.driver_id)
        self.assertEqual(self.submission.driver_id.current_vehicle_id, self.submission.vehicle_id)
        self.assertEqual(self.submission.vehicle_id.status, "enabled")

    def test_portal_state_labels(self):
        expected = {
            "draft": "En revision",
            "submitted": "En revision",
            "risk_review": "En revision",
            "external_validation_pending": "En revision",
            "manual_approval_pending": "En revision",
            "documents_requested": "Documentos solicitados",
            "documents_review": "Documentos enviados",
            "approved": "Aprobada",
            "rejected": "Rechazada",
        }
        for state, label in expected.items():
            self.submission.state = state
            self.assertEqual(self.submission.portal_state_label, label)

    def test_submission_confirmation_email_is_queued_when_submitted(self):
        self.submission.with_context(risk_send_mail_immediately=True).write(
            {"state": "submitted"}
        )

        self.assertEqual(self.submission.submission_email_status, "sent")
        self.assertEqual(
            self.submission.submission_email_sent_to, "portal-a@example.com"
        )
        self.assertTrue(self.submission.submission_email_sent_at)
        mail = self.env["mail.mail"].search(
            [
                ("subject", "=", "Solicitud recibida - ABC123"),
            ],
            limit=1,
        )
        self.assertEqual(mail.email_from, "reporte@impocoma.com")
        self.assertEqual(mail.reply_to, "reporte@impocoma.com")
        self.assertEqual(mail.email_to, "portal-a@example.com")
        self.assertFalse(mail.recipient_ids)

    def test_submission_rejection_email_is_queued_when_rejected(self):
        self.submission.with_context(
            risk_send_mail_immediately=True
        ).action_confirm_rejection("Datos incompletos")

        self.assertEqual(self.submission.state, "rejected")
        mail = self.env["mail.mail"].search(
            [
                ("subject", "=", "Solicitud rechazada - ABC123"),
            ],
            limit=1,
        )
        self.assertEqual(mail.email_from, "reporte@impocoma.com")
        self.assertEqual(mail.reply_to, "reporte@impocoma.com")
        self.assertEqual(mail.email_to, "portal-a@example.com")
        self.assertFalse(mail.recipient_ids)

    def test_document_rejection_email_is_queued_when_document_rejected(self):
        document = self.make_document(
            self.submission,
            document_type="vehicle_registration",
            party="vehicle",
            state="received",
            observations="No es legible",
        )

        document.with_context(risk_send_mail_immediately=True).action_confirm_rejection()

        self.assertEqual(document.state, "rejected")
        mail = self.env["mail.mail"].search(
            [
                ("subject", "=", "Documento rechazado - Tarjeta de propiedad"),
            ],
            limit=1,
        )
        self.assertEqual(mail.email_from, "reporte@impocoma.com")
        self.assertEqual(mail.reply_to, "reporte@impocoma.com")
        self.assertEqual(mail.email_to, "portal-a@example.com")
        self.assertFalse(mail.recipient_ids)

    def test_owner_signature_code_email_is_queued(self):
        result = self.submission.with_context(
            risk_send_mail_immediately=True
        ).send_owner_signature_code()

        self.assertTrue(result["ok"])
        self.assertEqual(self.submission.owner_signature_verification_state, "sent")
        self.assertEqual(
            self.submission.owner_signature_email, "operaciones@example.com"
        )
        self.assertTrue(self.submission.owner_signature_code_hash)
        self.assertTrue(self.submission.owner_signature_code_expires_at)
        mail = self.env["mail.mail"].search(
            [
                ("subject", "=", "Codigo de verificacion para firma del propietario"),
            ],
            limit=1,
        )
        self.assertEqual(mail.email_from, "reporte@impocoma.com")
        self.assertEqual(mail.reply_to, "reporte@impocoma.com")
        self.assertEqual(mail.email_to, "operaciones@example.com")

    def test_driver_signature_code_verification(self):
        code = "123456"
        self.submission.write(
            {
                "driver_signature_email": "conductor@example.com",
                "driver_signature_code_hash": self.submission._signature_code_hash(
                    "driver", code
                ),
                "driver_signature_code_expires_at": fields.Datetime.now()
                + timedelta(minutes=5),
                "driver_signature_verification_state": "sent",
            }
        )

        wrong = self.submission.verify_driver_signature_code(
            "000000", ip_address="127.0.0.1"
        )
        self.assertFalse(wrong["ok"])
        self.assertEqual(self.submission.driver_signature_code_attempts, 1)
        self.assertEqual(self.submission.driver_signature_verification_state, "sent")

        result = self.submission.verify_driver_signature_code(
            code, ip_address="127.0.0.1"
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            self.submission.driver_signature_verification_state, "verified"
        )
        self.assertEqual(self.submission.driver_signature_verified_ip, "127.0.0.1")
        self.assertTrue(
            self.submission._signature_email_verified_for(
                "driver", "conductor@example.com"
            )
        )

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
        document = self.submission.document_ids.filtered(
            lambda item: item.state == "pending"
        )[:1]

        self.assertTrue(self.submission._portal_document_upload_allowed(document))
        self.assertTrue(
            self.submission._portal_document_upload_allowed(document, self.portal_user)
        )
        self.assertFalse(
            self.submission._portal_document_upload_allowed(
                document, self.other_portal_user
            )
        )

        document.state = "received"
        self.assertFalse(
            self.submission._portal_document_upload_allowed(document, self.portal_user)
        )

        document.state = "pending"
        self.submission.state = "documents_review"
        self.assertFalse(
            self.submission._portal_document_upload_allowed(document, self.portal_user)
        )

    def test_portal_can_replace_rejected_document_during_review(self):
        self.submission.action_request_documents()
        rejected_document = self.submission.document_ids.filtered(
            lambda item: item.state == "pending"
        )[:1]
        pending_document = (self.submission.document_ids - rejected_document)[:1]
        self.submission.state = "documents_review"
        rejected_document.write(
            {
                "state": "rejected",
                "observations": "No es legible",
            }
        )

        self.assertTrue(
            self.submission._portal_document_upload_allowed(
                rejected_document, self.portal_user
            )
        )
        self.assertFalse(
            self.submission._portal_document_upload_allowed(
                pending_document, self.portal_user
            )
        )

    def test_autotransition_to_documents_review_when_last_required_document_uploaded(
        self,
    ):
        self.submission.action_request_documents()
        self.assertEqual(self.submission.state, "documents_requested")

        required_docs = self.submission.document_ids.filtered(lambda doc: doc.required)
        self.assertTrue(required_docs)

        for document in required_docs[:-1]:
            document.write(
                {
                    "file": "ZHVtbXk=",
                    "filename": "documento.pdf",
                }
            )
        self.assertEqual(self.submission.state, "documents_requested")

        required_docs[-1].write(
            {
                "file": "ZHVtbXk=",
                "filename": "documento_final.pdf",
            }
        )
        self.assertEqual(self.submission.state, "documents_review")

    def test_cannot_approve_without_approved_documents(self):
        self.submission.action_request_documents()

        with self.assertRaises(ValidationError):
            self.submission.action_confirm_approval("Ok")

    def test_approval_after_documents_are_approved(self):
        self.submission.action_request_documents()
        for document in self.submission.document_ids:
            self.approve_document(document)
        self.submission.write({"state": "documents_review"})

        self.submission.action_confirm_approval("Documentos completos")

        self.assertEqual(self.submission.state, "approved")
        self.assertEqual(self.submission.approval_user_id, self.env.user)
        self.assertFalse(self.submission.rejection_user_id)

    def test_validiti_manual_approval_moves_to_manual_approval(self):
        validation = self.make_validation(self.submission)

        validation.apply_manual_result(
            decision="approved",
            summary="Sin hallazgos",
            risk_score=5.0,
            external_reference="VALIDITI-1",
        )

        self.assertEqual(validation.status, "approved")
        self.assertEqual(self.submission.state, "manual_approval_pending")
        self.assertEqual(self.submission.risk_reviewer_id, self.env.user)

    def test_cannot_create_second_active_submission_for_same_plate(self):
        self.make_submission(owner=self.portal_user, state="submitted", plate="DUP123")

        with self.assertRaises(ValidationError):
            self.make_submission(
                owner=self.other_portal_user,
                state="draft",
                plate="DUP123",
            )

    def test_closed_submission_does_not_block_new_active_submission_for_same_plate(self):
        self.make_submission(owner=self.portal_user, state="rejected", plate="OLD123")

        submission = self.make_submission(
            owner=self.other_portal_user,
            state="submitted",
            plate="OLD123",
        )

        self.assertEqual(submission.vehicle_plate, "OLD123")

    def test_single_signature_requires_same_owner_and_driver_document(self):
        with self.assertRaises(ValidationError):
            self.make_submission(
                owner=self.portal_user,
                plate="SIG123",
                owner_document_type="cc",
                owner_document_number="11111111",
                driver_document_number="22222222",
                single_owner_driver_signature="yes",
            )

    def test_approval_blocks_vehicle_with_another_active_driver(self):
        self.make_submission(
            owner=self.portal_user,
            state="approved",
            plate="VEH123",
            driver_document_number="11111111",
        )
        current = self.make_submission(
            owner=self.other_portal_user,
            state="documents_review",
            plate="VEH123",
            driver_document_number="22222222",
        )
        self.approve_document(self.make_document(current))

        with self.assertRaises(ValidationError):
            current.action_confirm_approval("Revision completa")

    def test_approval_blocks_driver_with_another_active_vehicle(self):
        self.make_submission(
            owner=self.portal_user,
            state="approved",
            plate="DRV123",
            driver_document_number="33333333",
        )
        current = self.make_submission(
            owner=self.other_portal_user,
            state="documents_review",
            plate="DRV124",
            driver_document_number="33333333",
        )
        self.approve_document(self.make_document(current))

        with self.assertRaises(ValidationError):
            current.action_confirm_approval("Revision completa")

    def test_approval_blocks_master_vehicle_with_another_active_driver(self):
        driver = self.env["risk.driver"].create(
            {
                "name": "Conductor Actual",
                "document_number": "55555555",
            }
        )
        self.env["risk.vehicle"].create(
            {
                "plate": "MST123",
                "status": "enabled",
                "current_driver_id": driver.id,
            }
        )
        current = self.make_submission(
            owner=self.other_portal_user,
            state="documents_review",
            plate="MST123",
            driver_document_number="66666666",
        )
        self.approve_document(self.make_document(current))

        with self.assertRaises(ValidationError):
            current.action_confirm_approval("Revision completa")

    def test_approval_blocks_master_driver_with_another_active_vehicle(self):
        vehicle = self.env["risk.vehicle"].create(
            {
                "plate": "MST124",
                "status": "enabled",
            }
        )
        self.env["risk.driver"].create(
            {
                "name": "Conductor Actual",
                "document_number": "77777777",
                "current_vehicle_id": vehicle.id,
            }
        )
        current = self.make_submission(
            owner=self.other_portal_user,
            state="documents_review",
            plate="MST125",
            driver_document_number="77777777",
        )
        self.approve_document(self.make_document(current))

        with self.assertRaises(ValidationError):
            current.action_confirm_approval("Revision completa")

    def test_owner_driver_same_deduplicates_same_document_type_templates(self):
        submission = self.make_submission(
            owner=self.portal_user,
            plate="DOC123",
            owner_document_type="cc",
            owner_document_number="44444444",
            driver_document_number="44444444",
            single_owner_driver_signature="yes",
        )
        templates = [
            {
                "document_type": "third_party_life_sheet",
                "party": "driver",
                "name": "Formato conductor",
            },
            {
                "document_type": "third_party_life_sheet",
                "party": "owner",
                "name": "Formato propietario",
            },
            {
                "document_type": "owner_rut",
                "party": "owner",
                "name": "RUT",
            },
        ]

        result = submission._deduplicate_owner_driver_document_templates(templates)

        self.assertEqual(
            [(item["document_type"], item["party"]) for item in result],
            [
                ("third_party_life_sheet", "driver"),
                ("owner_rut", "owner"),
            ],
        )
