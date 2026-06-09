from odoo import fields, models


class RiskSubmissionValiditi(models.Model):
    _inherit = "risk.module"

    def action_mark_external_validation_pending(self):
        for record in self:
            validation = record._ensure_validiti_validation()
            record.write({"state": "external_validation_pending"})
            record.message_post(
                body="Validacion externa pendiente con %s." % validation.provider.title()
            )

    def action_send_external_validation(self):
        for record in self:
            validation = record._ensure_validiti_validation()
            validation.action_send_to_validiti()

    def action_register_external_validation_result(self):
        self.ensure_one()
        validation = self._ensure_validiti_validation()
        return validation.action_open_result_wizard()

    def _ensure_validiti_validation(self):
        self.ensure_one()
        validation = self.external_validation_ids.filtered(
            lambda item: item.provider == "validiti" and item.status in ("pending", "sent", "error")
        )[:1]
        if validation:
            return validation
        return self.env["risk.external.validation"].create({
            "submission_id": self.id,
            "provider": "validiti",
            "profile": "transport_driver_vehicle",
            "status": "pending",
        })

    def _prepare_validiti_payload(self):
        self.ensure_one()
        return {
            "provider": "validiti",
            "profile": "transport_driver_vehicle",
            "submission": {
                "id": self.id,
                "reference": self.name,
                "form_date": self.form_date.isoformat() if self.form_date else None,
            },
            "authorizations": {
                "personal_data_accepted": bool(self.personal_data_accepted),
                "terms_accepted_at": fields.Datetime.to_string(self.terms_accepted_at)
                if self.terms_accepted_at else None,
            },
            "driver": {
                "name": self.driver_name,
                "document_type": "cc",
                "document_number": self.driver_document_number,
                "phone": self.driver_phone,
                "email": self.driver_email,
                "city": self.driver_city,
            },
            "owner": {
                "name": self.owner_name,
                "document_type": self.owner_document_type,
                "document_number": self.owner_document_number,
                "phone": self.owner_phone,
                "email": self.owner_email,
                "city": self.owner_city,
            },
            "registered_owner": {
                "same_owner_on_license": self.same_owner_on_license,
                "name": self.registered_owner_name,
                "document_type": self.registered_owner_document_type,
                "document_number": self.registered_owner_document_number,
                "phone": self.registered_owner_phone,
            },
            "vehicle": {
                "plate": self.vehicle_plate,
                "semi_trailer_plate": self.semi_trailer_plate,
                "satellite_company": self.satellite_company,
            },
        }
