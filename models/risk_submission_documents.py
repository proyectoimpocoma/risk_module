import logging

from odoo import models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RiskSubmissionDocuments(models.Model):
    _inherit = "risk.module"

    def action_request_documents(self):
        for record in self:
            _logger.info("Requesting documents submission_id=%s user_id=%s", record.id, self.env.user.id)
            created_count = record._ensure_required_documents()
            record.state = "documents_requested"
            body = "Documentos solicitados."
            if created_count:
                body = "%s Se generaron %s documentos requeridos." % (body, created_count)
            record.message_post(body=body)
            _logger.info(
                "Documents requested submission_id=%s created_count=%s total_documents=%s",
                record.id,
                created_count,
                len(record.document_ids),
            )

    def action_start_document_review(self):
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

    def _required_document_templates(self):
        self.ensure_one()
        templates = [
            ("driver_id", "Cedula del conductor", "driver", 10),
            ("driver_license", "Licencia de conduccion", "driver", 20),
            ("owner_document", "Cedula / NIT del propietario", "owner", 30),
            ("vehicle_registration", "Tarjeta de propiedad", "vehicle", 40),
            ("soat", "SOAT", "vehicle", 50),
            ("technical_inspection", "Revision tecnico-mecanica", "vehicle", 60),
            ("policy", "Poliza", "vehicle", 70),
        ]
        if self.owner_has_valid_study == "yes":
            templates.append((
                "owner_security_study",
                "Estudio de seguridad vigente del propietario",
                "owner",
                80,
            ))
        if self.driver_has_valid_study == "yes":
            templates.append((
                "driver_security_study",
                "Estudio de seguridad vigente del conductor",
                "driver",
                90,
            ))
        if self.semi_trailer_plate:
            templates.append((
                "semi_registration",
                "Documento del semi/remolque",
                "semi_trailer",
                100,
            ))
        _logger.debug("Required document templates submission_id=%s count=%s", self.id, len(templates))
        return templates

    def _ensure_required_documents(self):
        self.ensure_one()
        existing_keys = set(self.document_ids.mapped("document_type"))
        values = []
        for document_type, name, party, sequence in self._required_document_templates():
            if document_type in existing_keys:
                continue
            values.append({
                "submission_id": self.id,
                "sequence": sequence,
                "name": name,
                "document_type": document_type,
                "party": party,
                "required": True,
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
