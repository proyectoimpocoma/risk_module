from odoo import models
from odoo.exceptions import ValidationError


class RiskSubmissionDocuments(models.Model):
    _inherit = "risk.module"

    def action_request_documents(self):
        for record in self:
            created_count = record._ensure_required_documents()
            record.state = "documents_requested"
            body = "Documentos solicitados."
            if created_count:
                body = "%s Se generaron %s documentos requeridos." % (body, created_count)
            record.message_post(body=body)

    def action_start_document_review(self):
        for record in self:
            missing = record.document_ids.filtered(
                lambda doc: doc.required and doc.state == "pending"
            )
            if missing:
                raise ValidationError(
                    "No puedes iniciar la revision documental mientras existan documentos obligatorios pendientes."
                )
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
            self.env["risk.module.document"].create(values)
        return len(values)

    def _check_documents_ready_for_approval(self):
        self.ensure_one()
        if not self.document_ids:
            raise ValidationError(
                "No puedes aprobar la solicitud sin generar y revisar los documentos requeridos."
            )
        blocking_documents = self.document_ids.filtered(
            lambda doc: doc.required and doc.state != "approved"
        )
        if blocking_documents:
            names = ", ".join(blocking_documents.mapped("name"))
            raise ValidationError(
                "No puedes aprobar la solicitud hasta aprobar todos los documentos obligatorios: %s" % names
            )
