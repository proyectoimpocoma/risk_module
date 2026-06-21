import logging

from odoo.http import request

_logger = logging.getLogger(__name__)


class RiskSubmissionFormMapperMixin:
    def _submission_values(self, data, state):
        """
        Map session data to Odoo model fields for creating or updating a submission.
        
        Args:
            data (dict): The session data.
            state (str): The state to assign to the submission.
            
        Returns:
            dict: Values ready to be written to risk.module.
        """
        self._merge_persisted_step_data(data)
        plate = data.get("vehicle_plate") or "Sin placa"
        return {
            "state": state,
            "name": "Habilitacion vehiculo %s" % plate,
            "form_date": data.get("form_date") or False,
            "vehicle_plate": plate,
            "semi_trailer_plate": data.get("semi_trailer_plate"),
            "satellite_company": data.get("satellite_company"),
            "satellite_url": data.get("satellite_url"),
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
            "single_owner_driver_signature": data.get("single_owner_driver_signature")
            or "no",
            "owner_has_valid_study": data.get("owner_has_valid_study"),
            "owner_signature": data.get("owner_signature"),
            "owner_signature_document": data.get("owner_signature_document"),
            "owner_signed_at": data.get("owner_signed_at") or False,
            "owner_signature_ip": data.get("owner_signature_ip"),
            "owner_signature_user_agent": data.get("owner_signature_user_agent"),
            "owner_signature_email": data.get("owner_signature_email"),
            "owner_signature_code_sent_at": data.get("owner_signature_code_sent_at") or False,
            "owner_signature_code_expires_at": data.get("owner_signature_code_expires_at") or False,
            "owner_signature_verified_at": data.get("owner_signature_verified_at") or False,
            "owner_signature_verified_ip": data.get("owner_signature_verified_ip"),
            "owner_signature_code_attempts": int(data.get("owner_signature_code_attempts") or 0),
            "owner_signature_verification_state": data.get("owner_signature_verification_state") or "not_sent",
            "driver_has_valid_study": data.get("driver_has_valid_study"),
            "driver_signature": data.get("driver_signature"),
            "driver_signature_document": data.get("driver_signature_document"),
            "driver_signed_at": data.get("driver_signed_at") or False,
            "driver_signature_ip": data.get("driver_signature_ip"),
            "driver_signature_user_agent": data.get("driver_signature_user_agent"),
            "driver_signature_email": data.get("driver_signature_email"),
            "driver_signature_code_sent_at": data.get("driver_signature_code_sent_at") or False,
            "driver_signature_code_expires_at": data.get("driver_signature_code_expires_at") or False,
            "driver_signature_verified_at": data.get("driver_signature_verified_at") or False,
            "driver_signature_verified_ip": data.get("driver_signature_verified_ip"),
            "driver_signature_code_attempts": int(data.get("driver_signature_code_attempts") or 0),
            "driver_signature_verification_state": data.get("driver_signature_verification_state") or "not_sent",
            "message": data.get("message"),
            "submission_owner_ids": self._extra_owner_commands(data),
            **request.env["risk.module"]._portal_ownership_values(request.env.user),
        }

    def _extra_owner_commands(self, data):
        """Build One2many write commands for the additional owners: clear the
        existing lines and recreate them from the session data."""
        commands = [(5, 0, 0)]
        if data.get("same_owner_on_license") == "yes":
            return commands
        for index, owner in enumerate(data.get("extra_owners") or []):
            commands.append(
                (
                    0,
                    0,
                    {
                        "sequence": (index + 1) * 10,
                        "name": owner.get("name"),
                        "document_type": owner.get("document_type") or "cc",
                        "document_number": owner.get("document_number"),
                        "role": owner.get("role") or "owner",
                        "phone": owner.get("phone") or False,
                        "email": owner.get("email") or False,
                        "address": owner.get("address") or False,
                        "neighborhood": owner.get("neighborhood") or False,
                        "city": owner.get("city") or False,
                    },
                )
            )
        return commands

    def _create_or_update_submission(self, data, state):
        """
        Create a new risk.module submission or update the existing one based on session data.
        
        Args:
            data (dict): The current session data.
            state (str): The state to save the submission in.
            
        Returns:
            record or bool: The created/updated submission record, or False if denied by ownership.
        """
        self._merge_persisted_step_data(data)
        submission_id = data.get("submission_id") or request.session.get("risk_submission_id")
        RiskSubmission = request.env["risk.module"].sudo().with_context(
            skip_risk_form_lock=True
        )
        submission = RiskSubmission.browse(int(submission_id or 0)).exists()
        if submission and submission.partner_id and not submission._portal_is_owned_by(request.env.user):
            _logger.warning(
                "Risk submission create/update denied by ownership submission_id=%s user_id=%s partner_id=%s owner_partner_id=%s",
                submission.id,
                request.env.user.id,
                request.env.user.partner_id.id,
                submission.partner_id.id,
            )
            return False
        values = self._submission_values(data, state)
        if submission:
            _logger.info(
                "Updating risk submission submission_id=%s state=%s user_id=%s fields=%s",
                submission.id,
                state,
                request.env.user.id,
                sorted(values.keys()),
            )
            submission.with_context(skip_risk_form_lock=True).write(values)
        else:
            # Before creating a new record, look for an existing own draft for
            # this plate.  This prevents duplicates when the session is lost
            # (e.g. the user navigated to the start page) or when the "send
            # code" button is double-clicked before the session is saved.
            plate = values.get("vehicle_plate") or ""
            partner = request.env.user.partner_id
            recovered = RiskSubmission.browse()
            if plate and partner:
                recovered = RiskSubmission.search(
                    [
                        ("vehicle_plate", "=", plate),
                        ("state", "=", "draft"),
                        ("partner_id", "=", partner.id),
                    ],
                    limit=1,
                    order="create_date desc",
                )
            if recovered:
                _logger.info(
                    "Reusing own draft submission submission_id=%s state=%s user_id=%s plate=%s",
                    recovered.id,
                    state,
                    request.env.user.id,
                    plate,
                )
                submission = recovered
                submission.with_context(skip_risk_form_lock=True).write(values)
            else:
                _logger.info(
                    "Creating risk submission state=%s user_id=%s partner_id=%s plate=%s",
                    state,
                    request.env.user.id,
                    request.env.user.partner_id.id,
                    values.get("vehicle_plate"),
                )
                submission = RiskSubmission.create(values)
        if state in ("submitted", "correction_submitted"):
            submission._sync_master_records()
        data["submission_id"] = submission.id
        data["submission_token"] = submission.access_token
        _logger.debug("Risk submission mapped submission_id=%s token_present=%s", submission.id, bool(submission.access_token))
        return submission
