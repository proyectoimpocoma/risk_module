import logging

from odoo import fields
from odoo.http import request

from .risk_submission_form_schema import CC_REGEX

_logger = logging.getLogger(__name__)


class RiskSubmissionFormSignatureMixin:
    def _clean_signature_data(self, signature):
        if not signature:
            return ""
        prefix = "data:image/png;base64,"
        if signature.startswith(prefix):
            return signature[len(prefix) :]
        return signature

    def _update_signature_data(self, data, post):
        owner_signature_document = post.get("owner_signature_document", "").strip()
        driver_signature_document = post.get("driver_signature_document", "").strip()
        owner_signature = self._clean_signature_data(post.get("owner_signature", ""))
        driver_signature = self._clean_signature_data(post.get("driver_signature", ""))
        data.update(
            {
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
        _logger.debug(
            "Updated signature data user_id=%s owner_signature_present=%s driver_signature_present=%s owner_study=%s driver_study=%s",
            request.env.user.id,
            bool(data.get("owner_signature")),
            bool(data.get("driver_signature")),
            data.get("owner_has_valid_study"),
            data.get("driver_has_valid_study"),
        )

    def _validate_signature_step(self, data):
        if data.get("owner_has_valid_study") not in ("yes", "no"):
            _logger.warning("Signature validation missing owner study flag user_id=%s", request.env.user.id)
            return "Debes indicar si el propietario cuenta con estudio vigente."
        if data.get("driver_has_valid_study") not in ("yes", "no"):
            _logger.warning("Signature validation missing driver study flag user_id=%s", request.env.user.id)
            return "Debes indicar si el conductor cuenta con estudio vigente."
        if not self._signatures_are_valid(data):
            _logger.warning("Combined signature validation failed user_id=%s", request.env.user.id)
            return self._signature_error_message(data)
        return None

    def _stamp_signature_metadata(self, data):
        now = fields.Datetime.to_string(fields.Datetime.now())
        remote_addr = request.httprequest.remote_addr
        user_agent = request.httprequest.user_agent.string
        if data.get("owner_has_valid_study") != "yes":
            _logger.info("Owner signature metadata stamped user_id=%s ip=%s", request.env.user.id, remote_addr)
            data.update(
                {
                    "owner_signed_at": now,
                    "owner_signature_ip": remote_addr,
                    "owner_signature_user_agent": user_agent,
                }
            )
        if data.get("driver_has_valid_study") != "yes":
            _logger.info("Driver signature metadata stamped user_id=%s ip=%s", request.env.user.id, remote_addr)
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
            _logger.info("Owner signature metadata stamped user_id=%s ip=%s", request.env.user.id, remote_addr)
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
            _logger.info("Driver signature metadata stamped user_id=%s ip=%s", request.env.user.id, remote_addr)
            data.update(
                {
                    "driver_signed_at": now,
                    "driver_signature_ip": remote_addr,
                    "driver_signature_user_agent": user_agent,
                }
            )

    def _signatures_are_valid(self, data):
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
        _logger.debug(
            "Signature validity evaluated user_id=%s owner_required=%s owner_ok=%s driver_required=%s driver_ok=%s",
            request.env.user.id,
            owner_required,
            bool(owner_ok),
            driver_required,
            bool(driver_ok),
        )
        return owner_ok and driver_ok

    def _validate_owner_signature_step(self, data):
        """Valida únicamente los datos de firma del propietario."""
        if data.get("owner_has_valid_study") not in ("yes", "no"):
            _logger.warning("Owner signature validation missing study flag user_id=%s", request.env.user.id)
            return "Debes indicar si el propietario cuenta con estudio vigente."
        if data.get("owner_has_valid_study") != "yes":
            if not data.get("owner_signature"):
                _logger.warning("Owner signature validation missing signature user_id=%s", request.env.user.id)
                return "Debes firmar como propietario."
            if not data.get("owner_signature_document") or not CC_REGEX.match(
                data.get("owner_signature_document")
            ):
                _logger.warning("Owner signature validation invalid document user_id=%s", request.env.user.id)
                return "Debes ingresar una cédula válida del propietario."
        return None

    def _validate_driver_signature_step(self, data):
        """Valida únicamente los datos de firma del conductor."""
        if data.get("driver_has_valid_study") not in ("yes", "no"):
            _logger.warning("Driver signature validation missing study flag user_id=%s", request.env.user.id)
            return "Debes indicar si el conductor cuenta con estudio vigente."
        if data.get("driver_has_valid_study") != "yes":
            if not data.get("driver_signature"):
                _logger.warning("Driver signature validation missing signature user_id=%s", request.env.user.id)
                return "Debes firmar como conductor."
            if not data.get("driver_signature_document") or not CC_REGEX.match(
                data.get("driver_signature_document")
            ):
                _logger.warning("Driver signature validation invalid document user_id=%s", request.env.user.id)
                return "Debes ingresar una cédula válida del conductor."
        return None

    def _signature_error_message(self, data):
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
            _logger.warning("Signature error message generated user_id=%s missing=%s", request.env.user.id, missing)
            return "Debes completar: %s." % ", ".join(missing)
        return "Debes completar la firma y cedula cuando el propietario o conductor no cuenta con estudio vigente."
