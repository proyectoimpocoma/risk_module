import logging

from odoo import fields
from odoo.http import request

from .risk_submission_form_schema import CC_REGEX

_logger = logging.getLogger(__name__)
_signature_logger = logging.getLogger("risk_module.signatures")


class RiskSubmissionFormSignatureMixin:
    def _signature_verification_config(self, party):
        """
        Get the configuration keys for email verification of a given party.
        """
        configs = {
            "owner": {
                "label": "propietario",
                "email_field": "owner_email",
                "verified_email": "owner_signature_email",
                "verified_at": "owner_signature_verified_at",
                "state": "owner_signature_verification_state",
            },
            "driver": {
                "label": "conductor",
                "email_field": "driver_email",
                "verified_email": "driver_signature_email",
                "verified_at": "driver_signature_verified_at",
                "state": "driver_signature_verification_state",
            },
        }
        return configs[party]

    def _signature_email_verification_error(self, data, party):
        """
        Validate if the email verification step was successfully completed for the party.
        Returns an error string if incomplete, otherwise None.
        """
        if party == "driver" and data.get("single_owner_driver_signature") == "yes":
            party = "owner"
        config = self._signature_verification_config(party)
        email = (data.get(config["email_field"]) or "").strip()
        if not email:
            return "Debes ingresar el correo del %s antes de firmar." % config["label"]
        if (
            data.get(config["state"]) != "verified"
            or not data.get(config["verified_at"])
            or data.get(config["verified_email"]) != email
        ):
            return "Debes verificar el correo del %s con el codigo enviado antes de continuar." % config["label"]
        return None

    def _clean_signature_data(self, signature):
        """
        Strip base64 prefix from signature image data if present.
        """
        if not signature:
            return ""
        prefix = "data:image/png;base64,"
        if signature.startswith(prefix):
            return signature[len(prefix) :]
        return signature

    def _update_signature_data(self, data, post):
        """
        Update the session data dictionary with signature data submitted from the form.
        """
        owner_signature_document = post.get("owner_signature_document", "").strip()
        driver_signature_document = post.get("driver_signature_document", "").strip()
        owner_signature = self._clean_signature_data(post.get("owner_signature", ""))
        driver_signature = self._clean_signature_data(post.get("driver_signature", ""))
        data.update(
            {
                "single_owner_driver_signature": post.get(
                    "single_owner_driver_signature",
                    data.get("single_owner_driver_signature") or "no",
                ).strip(),
                "owner_has_valid_study": post.get(
                    "owner_has_valid_study", data.get("owner_has_valid_study") or ""
                ).strip(),
                "owner_signature": owner_signature or data.get("owner_signature"),
                "owner_signature_document": owner_signature_document
                or data.get("owner_signature_document")
                or data.get("owner_document_number"),
                "driver_has_valid_study": post.get(
                    "driver_has_valid_study", data.get("driver_has_valid_study") or ""
                ).strip(),
                "driver_signature": driver_signature or data.get("driver_signature"),
                "driver_signature_document": driver_signature_document
                or data.get("driver_signature_document")
                or data.get("driver_document_number"),
            }
        )
        if data.get("single_owner_driver_signature") not in ("yes", "no"):
            data["single_owner_driver_signature"] = "no"
        _signature_logger.debug(
            "Updated signature data user_id=%s owner_signature_present=%s driver_signature_present=%s owner_study=%s driver_study=%s",
            request.env.user.id,
            bool(data.get("owner_signature")),
            bool(data.get("driver_signature")),
            data.get("owner_has_valid_study"),
            data.get("driver_has_valid_study"),
        )

    def _apply_single_owner_driver_signature(self, data):
        """
        If the owner and driver are the same, copy owner signature data to driver fields.
        """
        if data.get("single_owner_driver_signature") != "yes":
            return
        data.update(
            {
                "driver_has_valid_study": data.get("owner_has_valid_study") or "no",
                "driver_signature": data.get("owner_signature"),
                "driver_signature_document": data.get("owner_signature_document")
                or data.get("owner_document_number")
                or data.get("driver_document_number"),
                "driver_signed_at": data.get("owner_signed_at"),
                "driver_signature_ip": data.get("owner_signature_ip"),
                "driver_signature_user_agent": data.get("owner_signature_user_agent"),
                "driver_signature_email": data.get("owner_signature_email"),
                "driver_signature_code_sent_at": data.get("owner_signature_code_sent_at"),
                "driver_signature_code_expires_at": data.get("owner_signature_code_expires_at"),
                "driver_signature_verified_at": data.get("owner_signature_verified_at"),
                "driver_signature_verified_ip": data.get("owner_signature_verified_ip"),
                "driver_signature_code_attempts": data.get("owner_signature_code_attempts"),
                "driver_signature_verification_state": data.get("owner_signature_verification_state"),
            }
        )
        _signature_logger.info("Single owner/driver signature applied user_id=%s", request.env.user.id)

    def _single_owner_driver_identity_error(self, data):
        if data.get("single_owner_driver_signature") != "yes":
            return None
        owner_document_type = data.get("owner_document_type")
        owner_document_number = (data.get("owner_document_number") or "").strip()
        driver_document_number = (data.get("driver_document_number") or "").strip()
        if (
            owner_document_type != "cc"
            or not owner_document_number
            or not driver_document_number
            or owner_document_number != driver_document_number
        ):
            return (
                "Para usar firma unica, el propietario y el conductor deben "
                "ser la misma persona y tener el mismo numero de cedula."
            )
        return None

    def _validate_signature_step(self, data):
        """
        Perform a combined validation of all signature requirements.
        Returns an error message string if any validation fails.
        """
        identity_error = self._single_owner_driver_identity_error(data)
        if identity_error:
            return identity_error
        if data.get("owner_has_valid_study") not in ("yes", "no"):
            _signature_logger.warning("Signature validation missing owner study flag user_id=%s", request.env.user.id)
            return "Debes indicar si el propietario cuenta con estudio vigente."
        if data.get("driver_has_valid_study") not in ("yes", "no"):
            _signature_logger.warning("Signature validation missing driver study flag user_id=%s", request.env.user.id)
            return "Debes indicar si el conductor cuenta con estudio vigente."
        if not self._signatures_are_valid(data):
            _signature_logger.warning("Combined signature validation failed user_id=%s", request.env.user.id)
            return self._signature_error_message(data)
        return None

    def _stamp_signature_metadata(self, data):
        now = fields.Datetime.to_string(fields.Datetime.now())
        remote_addr = request.httprequest.remote_addr
        user_agent = request.httprequest.user_agent.string
        if data.get("owner_has_valid_study") != "yes":
            _signature_logger.info("Owner signature metadata stamped user_id=%s ip=%s", request.env.user.id, remote_addr)
            data.update(
                {
                    "owner_signed_at": now,
                    "owner_signature_ip": remote_addr,
                    "owner_signature_user_agent": user_agent,
                }
            )
        if data.get("driver_has_valid_study") != "yes":
            _signature_logger.info("Driver signature metadata stamped user_id=%s ip=%s", request.env.user.id, remote_addr)
            data.update(
                {
                    "driver_signed_at": now,
                    "driver_signature_ip": remote_addr,
                    "driver_signature_user_agent": user_agent,
                }
            )

    def _stamp_owner_signature_metadata(self, data):
        now = fields.Datetime.to_string(fields.Datetime.now())
        remote_addr = request.httprequest.remote_addr
        user_agent = request.httprequest.user_agent.string
        if data.get("owner_has_valid_study") != "yes":
            _signature_logger.info("Owner signature metadata stamped user_id=%s ip=%s", request.env.user.id, remote_addr)
            data.update(
                {
                    "owner_signed_at": now,
                    "owner_signature_ip": remote_addr,
                    "owner_signature_user_agent": user_agent,
                }
            )

    def _stamp_driver_signature_metadata(self, data):
        now = fields.Datetime.to_string(fields.Datetime.now())
        remote_addr = request.httprequest.remote_addr
        user_agent = request.httprequest.user_agent.string
        if data.get("driver_has_valid_study") != "yes":
            _signature_logger.info("Driver signature metadata stamped user_id=%s ip=%s", request.env.user.id, remote_addr)
            data.update(
                {
                    "driver_signed_at": now,
                    "driver_signature_ip": remote_addr,
                    "driver_signature_user_agent": user_agent,
                }
            )

    def _signatures_are_valid(self, data):
        """
        Return True if all signature and verification requirements are fully met.
        """
        self._apply_single_owner_driver_signature(data)
        owner_required = data.get("owner_has_valid_study") != "yes"
        driver_required = data.get("driver_has_valid_study") != "yes"
        owner_document_ok = data.get("owner_signature_document") and CC_REGEX.match(
            data.get("owner_signature_document")
        )
        driver_document_ok = data.get("driver_signature_document") and CC_REGEX.match(
            data.get("driver_signature_document")
        )
        owner_ok = not owner_required or (
            data.get("owner_signature") and owner_document_ok
        )
        driver_ok = not driver_required or (
            data.get("driver_signature") and driver_document_ok
        )
        owner_email_ok = not self._signature_email_verification_error(data, "owner")
        driver_email_ok = not self._signature_email_verification_error(data, "driver")
        _signature_logger.debug(
            "Signature validity evaluated user_id=%s owner_required=%s owner_ok=%s owner_email_ok=%s driver_required=%s driver_ok=%s driver_email_ok=%s",
            request.env.user.id,
            owner_required,
            bool(owner_ok),
            owner_email_ok,
            driver_required,
            bool(driver_ok),
            driver_email_ok,
        )
        return owner_ok and driver_ok and owner_email_ok and driver_email_ok

    def _validate_owner_signature_step(self, data):
        """Valida únicamente los datos de firma del propietario."""
        identity_error = self._single_owner_driver_identity_error(data)
        if identity_error:
            return identity_error
        verification_error = self._signature_email_verification_error(data, "owner")
        if verification_error:
            _signature_logger.warning("Owner signature email verification missing user_id=%s", request.env.user.id)
            return verification_error
        if data.get("owner_has_valid_study") not in ("yes", "no"):
            _signature_logger.warning("Owner signature validation missing study flag user_id=%s", request.env.user.id)
            return "Debes indicar si el propietario cuenta con estudio vigente."
        if data.get("owner_has_valid_study") != "yes":
            if not data.get("owner_signature"):
                _signature_logger.warning("Owner signature validation missing signature user_id=%s", request.env.user.id)
                return "Debes firmar como propietario."
            if not data.get("owner_signature_document") or not CC_REGEX.match(
                data.get("owner_signature_document")
            ):
                _signature_logger.warning("Owner signature validation invalid document user_id=%s", request.env.user.id)
                return "Debes ingresar una cédula válida del propietario."
        return None

    def _validate_driver_signature_step(self, data):
        """Valida únicamente los datos de firma del conductor."""
        identity_error = self._single_owner_driver_identity_error(data)
        if identity_error:
            return identity_error
        if data.get("single_owner_driver_signature") == "yes":
            self._apply_single_owner_driver_signature(data)
            return None
        verification_error = self._signature_email_verification_error(data, "driver")
        if verification_error:
            _signature_logger.warning("Driver signature email verification missing user_id=%s", request.env.user.id)
            return verification_error
        if data.get("driver_has_valid_study") not in ("yes", "no"):
            _signature_logger.warning("Driver signature validation missing study flag user_id=%s", request.env.user.id)
            return "Debes indicar si el conductor cuenta con estudio vigente."
        if data.get("driver_has_valid_study") != "yes":
            if not data.get("driver_signature"):
                _signature_logger.warning("Driver signature validation missing signature user_id=%s", request.env.user.id)
                return "Debes firmar como conductor."
            if not data.get("driver_signature_document") or not CC_REGEX.match(
                data.get("driver_signature_document")
            ):
                _signature_logger.warning("Driver signature validation invalid document user_id=%s", request.env.user.id)
                return "Debes ingresar una cédula válida del conductor."
        return None

    def _signature_error_message(self, data):
        """
        Generate a comprehensive error message listing all missing signature requirements.
        """
        missing = []
        if data.get("owner_has_valid_study") != "yes":
            if not data.get("owner_signature"):
                missing.append("firma del propietario")
            if not data.get("owner_signature_document") or not CC_REGEX.match(
                data.get("owner_signature_document")
            ):
                missing.append("cedula del propietario valida")
        if data.get("driver_has_valid_study") != "yes":
            if not data.get("driver_signature"):
                missing.append("firma del conductor")
            if not data.get("driver_signature_document") or not CC_REGEX.match(
                data.get("driver_signature_document")
            ):
                missing.append("cedula del conductor valida")
        if missing:
            _signature_logger.warning("Signature error message generated user_id=%s missing=%s", request.env.user.id, missing)
            return "Debes completar: %s." % ", ".join(missing)
        owner_verification_error = self._signature_email_verification_error(data, "owner")
        if owner_verification_error:
            return owner_verification_error
        driver_verification_error = self._signature_email_verification_error(data, "driver")
        if driver_verification_error:
            return driver_verification_error
        return "Debes completar la firma, cedula y verificacion de correo cuando corresponda."
