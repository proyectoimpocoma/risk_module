from odoo.http import request


class RiskSubmissionFormMapperMixin:
    def _submission_values(self, data, state):
        self._merge_persisted_step_data(data)
        plate = data.get("vehicle_plate") or "Sin placa"
        return {
            "state": state,
            "name": "Habilitacion vehiculo %s" % plate,
            "form_date": data.get("form_date") or False,
            "vehicle_plate": plate,
            "semi_trailer_plate": data.get("semi_trailer_plate"),
            "satellite_company": data.get("satellite_company"),
            "satellite_user": data.get("satellite_user"),
            "satellite_password": data.get("satellite_password"),
            "owner_name": data.get("owner_name"),
            "owner_document_type": data.get("owner_document_type"),
            "owner_document_number": data.get("owner_document_number"),
            "owner_address": data.get("owner_address"),
            "owner_neighborhood": data.get("owner_neighborhood"),
            "owner_city": data.get("owner_city"),
            "owner_phone": data.get("owner_phone"),
            "owner_email": data.get("owner_email"),
            "advance_payment_to": data.get("advance_payment_to"),
            "same_owner_on_license": data.get("same_owner_on_license"),
            "registered_owner_document_type": data.get("registered_owner_document_type"),
            "registered_owner_document_number": data.get("registered_owner_document_number"),
            "registered_owner_name": data.get("registered_owner_name"),
            "registered_owner_phone": data.get("registered_owner_phone"),
            "driver_name": data.get("driver_name"),
            "driver_document_number": data.get("driver_document_number"),
            "driver_address": data.get("driver_address"),
            "driver_neighborhood": data.get("driver_neighborhood"),
            "driver_city": data.get("driver_city"),
            "driver_phone": data.get("driver_phone"),
            "driver_optional_phone": data.get("driver_optional_phone"),
            "driver_email": data.get("driver_email"),
            "driver_is_fit": data.get("driver_is_fit"),
            "driver_is_trained": data.get("driver_is_trained"),
            "family_reference_name": data.get("family_reference_name"),
            "family_reference_relationship": data.get("family_reference_relationship"),
            "family_reference_phone": data.get("family_reference_phone"),
            "cargo_reference_name": data.get("cargo_reference_name"),
            "cargo_reference_phone": data.get("cargo_reference_phone"),
            "banking_info_accepted": data.get("banking_info_accepted") == "1" or request.session.get("risk_terms_accepted") == "1",
            "compensation_accepted": data.get("compensation_accepted") == "1" or request.session.get("risk_terms_accepted") == "1",
            "personal_data_accepted": data.get("personal_data_accepted") == "1" or request.session.get("risk_terms_accepted") == "1",
            "terms_accepted_at": data.get("terms_accepted_at") or False,
            "owner_has_valid_study": data.get("owner_has_valid_study"),
            "owner_signature": data.get("owner_signature"),
            "owner_signature_document": data.get("owner_signature_document"),
            "owner_signed_at": data.get("owner_signed_at") or False,
            "owner_signature_ip": data.get("owner_signature_ip"),
            "owner_signature_user_agent": data.get("owner_signature_user_agent"),
            "driver_has_valid_study": data.get("driver_has_valid_study"),
            "driver_signature": data.get("driver_signature"),
            "driver_signature_document": data.get("driver_signature_document"),
            "driver_signed_at": data.get("driver_signed_at") or False,
            "driver_signature_ip": data.get("driver_signature_ip"),
            "driver_signature_user_agent": data.get("driver_signature_user_agent"),
            "message": data.get("message"),
            **request.env["risk.module"]._portal_ownership_values(request.env.user),
        }

    def _create_or_update_submission(self, data, state):
        self._merge_persisted_step_data(data)
        submission_id = data.get("submission_id") or request.session.get("risk_submission_id")
        submission = request.env["risk.module"].sudo().browse(int(submission_id or 0)).exists()
        if submission and submission.partner_id and not submission._portal_is_owned_by(request.env.user):
            return False
        values = self._submission_values(data, state)
        if submission:
            submission.write(values)
        else:
            submission = request.env["risk.module"].sudo().create(values)
        data["submission_id"] = submission.id
        data["submission_token"] = submission.access_token
        return submission
