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
        same_owner_driver = self._same_owner_and_driver_person()
        templates = [
            {
                "document_type": "driver_license",
                "name": "Licencia de conduccion",
                "party": "driver",
                "sequence": 10,
                "validity_required": True,
                "requires_color": True,
                "requires_both_sides": True,
                "instructions": "Debe estar vigente, a color y cargada por ambas caras.",
            },
            {
                "document_type": "driver_id",
                "name": "Cedula de ciudadania del conductor",
                "party": "driver",
                "sequence": 20,
                "requires_color": True,
                "requires_both_sides": True,
                "instructions": "Cedula digital, fisica o contraseña. Cargar ultima modificacion si aplica, a color y por ambas caras.",
            },
            {
                "document_type": "driver_social_security",
                "name": "Planilla de pago de seguridad social",
                "party": "driver",
                "sequence": 30,
                "validity_required": True,
                "instructions": "Periodo vigente con cuadro de novedades.",
            },
            {
                "document_type": "driver_photo",
                "name": "Foto actualizada del conductor",
                "party": "driver",
                "sequence": 40,
                "instructions": "Foto de hombros hacia arriba, sin gorra, gafas oscuras, tapabocas u otros accesorios.",
            },
            {
                "document_type": "third_party_life_sheet",
                "name": "Formato Hoja de Vida Habilitacion de Terceros FO-RI-01",
                "party": "driver",
                "sequence": 50,
                "instructions": "Debe estar completamente diligenciado y firmado.",
            },
            {
                "document_type": "driver_risk_induction",
                "name": "Induccion y notificacion general de riesgos Impocoma",
                "party": "driver",
                "sequence": 60,
                "instructions": "Cargar soporte de induccion y notificacion general de riesgos Impocoma.",
            },
            {
                "document_type": "vehicle_registration",
                "name": "Licencia de transito del vehiculo",
                "party": "vehicle",
                "sequence": 100,
                "requires_color": True,
                "instructions": "Licencia de transito del vehiculo a color.",
            },
            {
                "document_type": "vehicle_photo",
                "name": "Foto actualizada del vehiculo",
                "party": "vehicle",
                "sequence": 110,
                "instructions": "Foto de frente y lado izquierdo o derecho, donde se vea la placa y los ejes.",
            },
            {
                "document_type": "soat",
                "name": "SOAT",
                "party": "vehicle",
                "sequence": 120,
                "validity_required": True,
                "instructions": "Seguro obligatorio de accidentes de transito vigente.",
            },
        ]
        if self.owner_document_type == "nit":
            templates.extend([
                {
                    "document_type": "owner_chamber_commerce",
                    "name": "Camara de comercio",
                    "party": "owner",
                    "sequence": 200,
                    "max_age_days": 30,
                    "instructions": "Certificado de camara de comercio con vigencia no mayor a 30 dias.",
                },
                {
                    "document_type": "owner_legal_representative_id",
                    "name": "Cedula del representante legal",
                    "party": "owner",
                    "sequence": 210,
                    "requires_color": True,
                    "instructions": "Cedula digital o contraseña del representante legal o suplente autorizado segun camara de comercio, a color.",
                },
            ])
        elif not same_owner_driver:
            templates.append({
                "document_type": "owner_document",
                "name": "Cedula de ciudadania del propietario o tenedor",
                "party": "owner",
                "sequence": 200,
                "requires_color": True,
                "instructions": "Cedula digital, fisica o contraseña. Cargar ultima modificacion si aplica, a color.",
            })
        templates.extend([
            {
                "document_type": "owner_bank_certificate",
                "name": "Certificacion bancaria",
                "party": "owner",
                "sequence": 220,
                "instructions": "Certificacion bancaria para pagos.",
            },
            {
                "document_type": "owner_rut",
                "name": "Registro Unico Tributario RUT",
                "party": "owner",
                "sequence": 230,
                "instructions": "El RUT debe registrar marca de agua como copia de certificado o certificado unicamente.",
            },
        ])
        if not same_owner_driver:
            templates.append({
                "document_type": "third_party_life_sheet",
                "name": "Formato Hoja de Vida Habilitacion de Terceros FO-RI-01",
                "party": "owner",
                "sequence": 240,
                "instructions": "Debe estar completamente diligenciado y firmado.",
            })
        if self.semi_trailer_plate:
            templates.extend([
                {
                    "document_type": "semi_photo",
                    "name": "Foto del remolque o semirremolque",
                    "party": "semi_trailer",
                    "sequence": 300,
                    "instructions": "Foto donde se vea la placa y los ejes.",
                },
                {
                    "document_type": "semi_registration",
                    "name": "Tarjeta de registro de remolque o semirremolque",
                    "party": "semi_trailer",
                    "sequence": 310,
                    "requires_color": True,
                    "instructions": "Tarjeta de registro del remolque o semirremolque a color.",
                },
            ])
        if self.owner_has_valid_study == "yes" and not same_owner_driver:
            templates.append({
                "document_type": "owner_security_study",
                "name": "Estudio de seguridad vigente del propietario",
                "party": "owner",
                "sequence": 400,
                "validity_required": True,
                "instructions": "Cargar estudio de seguridad vigente del propietario.",
            })
        if self.driver_has_valid_study == "yes":
            templates.append({
                "document_type": "driver_security_study",
                "name": "Estudio de seguridad vigente del conductor",
                "party": "driver",
                "sequence": 410,
                "validity_required": True,
                "instructions": "Cargar estudio de seguridad vigente del conductor.",
            })
        _logger.debug("Required document templates submission_id=%s count=%s", self.id, len(templates))
        return templates

    def _same_owner_and_driver_person(self):
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
        obsolete_documents = self.document_ids.filtered(
            lambda document: (
                document.required
                and document.document_type in self._GENERATED_DOCUMENT_TYPES
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
                "required": True,
                "validity_required": template.get("validity_required", False),
                "max_age_days": template.get("max_age_days", 0),
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
