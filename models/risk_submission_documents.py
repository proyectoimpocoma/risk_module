import logging

from odoo import models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RiskSubmissionDocuments(models.Model):
    _inherit = "risk.module"

    _GENERATED_DOCUMENT_TYPES = {
        "driver_license",
        "driver_id",
        "driver_social_security",
        "driver_photo",
        "driver_risk_induction",
        "owner_document",
        "owner_bank_certificate",
        "owner_rut",
        "owner_chamber_commerce",
        "owner_legal_representative_id",
        "vehicle_registration",
        "vehicle_photo",
        "soat",
        "third_party_life_sheet",
        "owner_security_study",
        "driver_security_study",
        "semi_registration",
        "semi_photo",
    }

    def action_request_documents(self):
        """
        Transition the submission to 'documents_requested' state.
        Generates required documents based on rules and sends a notification email.
        """
        for record in self:
            _logger.info("Requesting documents submission_id=%s user_id=%s", record.id, self.env.user.id)
            created_count = record._ensure_required_documents()
            record.state = "documents_requested"
            body = "Documentos solicitados."
            if created_count:
                body = "%s Se generaron %s documentos requeridos." % (body, created_count)
            record.message_post(body=body)
            record.action_send_documents_requested_email()
            _logger.info(
                "Documents requested submission_id=%s created_count=%s total_documents=%s",
                record.id,
                created_count,
                len(record.document_ids),
            )

    def action_start_document_review(self):
        """
        Start the document review phase.
        Raises ValidationError if any required documents are still pending.
        """
        for record in self:
            missing = record.document_ids.filtered(
                lambda doc: doc.required and doc.state == "pending"
            )
            if missing:
                _logger.warning(
                    "Document review blocked submission_id=%s missing_document_ids=%s",
                    record.id,
                    missing.ids,
                )
                raise ValidationError(
                    "No puedes iniciar la revision documental mientras existan documentos obligatorios pendientes."
                )
        _logger.info("Starting document review submission_ids=%s user_id=%s", self.ids, self.env.user.id)
        self.write({"state": "documents_review"})

    def action_add_manual_document(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Agregar documento adicional",
            "res_model": "risk.module.document",
            "view_mode": "form",
            "view_id": self.env.ref("risk_module.view_risk_module_document_form").id,
            "target": "new",
            "context": {
                "default_submission_id": self.id,
                "default_source": "manual",
                "default_required": True,
                "default_document_type": "other",
                "default_party": "other",
                "default_max_file_size_mb": 10.0,
                "default_allowed_file_extensions": "pdf,jpg,jpeg,png",
            },
        }

    def _required_document_templates(self):
        self.ensure_one()
        requirements = self.env["risk.document.requirement"].search(
            [("active", "=", True)],
            order="sequence, id",
        )
        templates = [
            requirement._to_document_template()
            for requirement in requirements
            if requirement._applies_to_submission(self)
        ]
        _logger.debug("Required document templates submission_id=%s count=%s", self.id, len(templates))
        return templates

    def _same_owner_and_driver_person(self):
        """
        Check if the owner and driver are logically the same person.
        
        Returns:
            bool: True if they are the same person, False otherwise.
        """
        self.ensure_one()
        if self.single_owner_driver_signature == "yes":
            return True
        owner_document_number = (self.owner_document_number or "").strip()
        driver_document_number = (self.driver_document_number or "").strip()
        return (
            self.owner_document_type == "cc"
            and owner_document_number
            and owner_document_number == driver_document_number
        )

    def _ensure_required_documents(self):
        self.ensure_one()
        existing_documents = {
            (document.document_type, document.party): document
            for document in self.document_ids
        }
        templates = self._required_document_templates()
        required_keys = {
            (template["document_type"], template["party"]) for template in templates
        }
        configured_document_types = set(
            self.env["risk.document.requirement"]
            .with_context(active_test=False)
            .search([])
            .mapped("document_type")
        )
        generated_document_types = self._GENERATED_DOCUMENT_TYPES | configured_document_types
        obsolete_documents = self.document_ids.filtered(
            lambda document: (
                document.required
                and document.document_type in generated_document_types
                and (document.document_type, document.party) not in required_keys
            )
        )
        if obsolete_documents:
            removable_documents = obsolete_documents.filtered(lambda document: not document.file)
            documents_to_keep = obsolete_documents - removable_documents
            if removable_documents:
                _logger.info(
                    "Removing obsolete generated documents submission_id=%s document_ids=%s",
                    self.id,
                    removable_documents.ids,
                )
                removable_documents.unlink()
            if documents_to_keep:
                _logger.info(
                    "Marking obsolete generated documents as optional submission_id=%s document_ids=%s",
                    self.id,
                    documents_to_keep.ids,
                )
                documents_to_keep.write({"required": False})
        values = []
        for template in templates:
            key = (template["document_type"], template["party"])
            existing_document = existing_documents.get(key)
            metadata = {
                "name": template["name"],
                "sequence": template["sequence"],
                "required": template.get("required", True),
                "source": "generated",
                "validity_required": template.get("validity_required", False),
                "issue_date_required": template.get("issue_date_required", False),
                "reject_expired": template.get("reject_expired", True),
                "max_age_days": template.get("max_age_days", 0),
                "max_file_size_mb": template.get("max_file_size_mb", 10.0),
                "allowed_file_extensions": template.get(
                    "allowed_file_extensions"
                ) or "pdf,jpg,jpeg,png",
                "requires_color": template.get("requires_color", False),
                "requires_both_sides": template.get("requires_both_sides", False),
                "instructions": template.get("instructions"),
            }
            if existing_document:
                existing_document.write(metadata)
                continue
            values.append({
                "submission_id": self.id,
                "document_type": template["document_type"],
                "party": template["party"],
                **metadata,
            })
        if values:
            _logger.info(
                "Creating required documents submission_id=%s document_types=%s",
                self.id,
                [value["document_type"] for value in values],
            )
            self.env["risk.module.document"].create(values)
        else:
            _logger.debug("No required documents to create submission_id=%s", self.id)
        return len(values)

    def _check_documents_ready_for_approval(self):
        """
        Verify that all required documents are approved before submission approval.
        Raises ValidationError if any required document is not approved.
        """
        self.ensure_one()
        if not self.document_ids:
            _logger.warning("Approval blocked without documents submission_id=%s", self.id)
            raise ValidationError(
                "No puedes aprobar la solicitud sin generar y revisar los documentos requeridos."
            )
        blocking_documents = self.document_ids.filtered(
            lambda doc: doc.required and doc.state != "approved"
        )
        if blocking_documents:
            names = ", ".join(blocking_documents.mapped("name"))
            _logger.warning(
                "Approval blocked by documents submission_id=%s blocking_document_ids=%s",
                self.id,
                blocking_documents.ids,
            )
            raise ValidationError(
                "No puedes aprobar la solicitud hasta aprobar todos los documentos obligatorios: %s" % names
            )
        _logger.debug("Documents ready for approval submission_id=%s", self.id)
