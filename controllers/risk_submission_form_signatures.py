from odoo import fields
from odoo.http import request

from .risk_submission_form_schema import CC_REGEX


class RiskSubmissionFormSignatureMixin:
    def _clean_signature_data(self, signature):
        if not signature:
            return ""
        prefix = "data:image/png;base64,"
        if signature.startswith(prefix):
            return signature[len(prefix):]
        return signature

    def _update_signature_data(self, data, post):
        owner_signature_document = post.get("owner_signature_document", "").strip()
        driver_signature_document = post.get("driver_signature_document", "").strip()
        owner_signature = self._clean_signature_data(post.get("owner_signature", ""))
        driver_signature = self._clean_signature_data(post.get("driver_signature", ""))
        data.update({
            "owner_has_valid_study": post.get("owner_has_valid_study", data.get("owner_has_valid_study") or "").strip(),
            "owner_signature": owner_signature or data.get("owner_signature"),
            "owner_signature_document": owner_signature_document or data.get("owner_signature_document") or data.get("owner_document_number"),
            "driver_has_valid_study": post.get("driver_has_valid_study", data.get("driver_has_valid_study") or "").strip(),
            "driver_signature": driver_signature or data.get("driver_signature"),
            "driver_signature_document": driver_signature_document or data.get("driver_signature_document") or data.get("driver_document_number"),
        })

    def _validate_signature_step(self, data):
        if data.get("owner_has_valid_study") not in ("yes", "no"):
            return "Debes indicar si el propietario cuenta con estudio vigente."
        if data.get("driver_has_valid_study") not in ("yes", "no"):
            return "Debes indicar si el conductor cuenta con estudio vigente."
        if not self._signatures_are_valid(data):
            return self._signature_error_message(data)
        return None

    def _stamp_signature_metadata(self, data):
        now = fields.Datetime.to_string(fields.Datetime.now())
        remote_addr = request.httprequest.remote_addr
        user_agent = request.httprequest.user_agent.string
        if data.get("owner_has_valid_study") != "yes":
            data.update({
                "owner_signed_at": now,
                "owner_signature_ip": remote_addr,
                "owner_signature_user_agent": user_agent,
            })
        if data.get("driver_has_valid_study") != "yes":
            data.update({
                "driver_signed_at": now,
                "driver_signature_ip": remote_addr,
                "driver_signature_user_agent": user_agent,
            })

    def _signatures_are_valid(self, data):
        owner_required = data.get("owner_has_valid_study") != "yes"
        driver_required = data.get("driver_has_valid_study") != "yes"
        owner_document_ok = data.get("owner_signature_document") and CC_REGEX.match(data.get("owner_signature_document"))
        driver_document_ok = data.get("driver_signature_document") and CC_REGEX.match(data.get("driver_signature_document"))
        owner_ok = not owner_required or (data.get("owner_signature") and owner_document_ok)
        driver_ok = not driver_required or (data.get("driver_signature") and driver_document_ok)
        return owner_ok and driver_ok

    def _signature_error_message(self, data):
        missing = []
        if data.get("owner_has_valid_study") != "yes":
            if not data.get("owner_signature"):
                missing.append("firma del propietario")
            if not data.get("owner_signature_document") or not CC_REGEX.match(data.get("owner_signature_document")):
                missing.append("cedula del propietario valida")
        if data.get("driver_has_valid_study") != "yes":
            if not data.get("driver_signature"):
                missing.append("firma del conductor")
            if not data.get("driver_signature_document") or not CC_REGEX.match(data.get("driver_signature_document")):
                missing.append("cedula del conductor valida")
        if missing:
            return "Debes completar: %s." % ", ".join(missing)
        return "Debes completar la firma y cedula cuando el propietario o conductor no cuenta con estudio vigente."
