import base64
import logging
from datetime import timedelta

from odoo import http
from odoo import fields
from odoo.http import request

_logger = logging.getLogger(__name__)

DEFAULT_MAX_PORTAL_UPLOAD_SIZE = 10 * 1024 * 1024
DEFAULT_ALLOWED_PORTAL_UPLOAD_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_PORTAL_UPLOAD_MIMETYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


class RiskSubmissionPortalController(http.Controller):
    def _get_portal_submission(self, submission_id):
        submission = request.env["risk.module"].sudo().browse(submission_id).exists()
        if not submission or not submission._portal_is_owned_by(request.env.user):
            _logger.warning(
                "Portal risk submission access denied submission_id=%s user_id=%s exists=%s",
                submission_id,
                request.env.user.id,
                bool(submission),
            )
            return request.env["risk.module"]
        return submission

    def _get_portal_document(self, submission, document_id):
        document = request.env["risk.module.document"].sudo().browse(document_id).exists()
        if not document or document.submission_id != submission:
            _logger.warning(
                "Portal risk document access denied submission_id=%s document_id=%s user_id=%s exists=%s",
                submission.id if submission else None,
                document_id,
                request.env.user.id,
                bool(document),
            )
            return request.env["risk.module.document"]
        return document

    @http.route("/mis-solicitudes-riesgo", type="http", auth="user", website=True, sitemap=False)
    def portal_risk_submissions(self, **kwargs):
        submissions = request.env["risk.module"].sudo().search(
            [("partner_id", "=", request.env.user.partner_id.id)],
            order="create_date desc",
        )
        _logger.info(
            "Portal risk submissions listed user_id=%s partner_id=%s count=%s",
            request.env.user.id,
            request.env.user.partner_id.id,
            len(submissions),
        )
        return request.render("risk_module.portal_risk_submission_list", {
            "submissions": submissions,
        })

    @http.route("/mis-solicitudes-riesgo/<int:submission_id>", type="http", auth="user", website=True, sitemap=False)
    def portal_risk_submission_detail(self, submission_id, **kwargs):
        submission = self._get_portal_submission(submission_id)
        if not submission:
            return request.not_found()
        _logger.info(
            "Portal risk submission detail opened submission_id=%s user_id=%s state=%s",
            submission.id,
            request.env.user.id,
            submission.state,
        )
        return request.render("risk_module.portal_risk_submission_detail", {
            "submission": submission,
        })

    @http.route(
        "/mis-solicitudes-riesgo/<int:submission_id>/documentos/<int:document_id>/subir",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        sitemap=False,
    )
    def portal_upload_document(self, submission_id, document_id, **post):
        submission = self._get_portal_submission(submission_id)
        if not submission:
            return request.not_found()

        document = self._get_portal_document(submission, document_id)
        if not document:
            return request.not_found()

        if not submission._portal_document_upload_allowed(document, request.env.user):
            _logger.warning(
                "Portal document upload denied submission_id=%s document_id=%s user_id=%s submission_state=%s document_state=%s",
                submission.id,
                document.id,
                request.env.user.id,
                submission.state,
                document.state,
            )
            return self._redirect_upload_error(submission, "not_allowed")

        upload = request.httprequest.files.get("document_file")
        if not upload or not upload.filename:
            _logger.warning(
                "Portal document upload missing file submission_id=%s document_id=%s user_id=%s",
                submission.id,
                document.id,
                request.env.user.id,
            )
            return self._redirect_upload_error(submission, "missing")

        upload_error = self._validate_portal_upload(upload, document)
        if upload_error:
            _logger.warning(
                "Portal document upload rejected submission_id=%s document_id=%s user_id=%s filename=%s error=%s mimetype=%s content_length=%s",
                submission.id,
                document.id,
                request.env.user.id,
                upload.filename,
                upload_error,
                upload.mimetype,
                request.httprequest.content_length,
            )
            return self._redirect_upload_error(submission, upload_error)

        date_error, date_values = self._validate_portal_document_dates(document, post)
        if date_error:
            _logger.warning(
                "Portal document upload rejected by date validation submission_id=%s document_id=%s user_id=%s error=%s validity_required=%s max_age_days=%s",
                submission.id,
                document.id,
                request.env.user.id,
                date_error,
                document.validity_required,
                document.max_age_days,
            )
            return self._redirect_upload_error(submission, date_error)

        _logger.info(
            "Portal document upload received submission_id=%s document_id=%s user_id=%s filename=%s content_length=%s",
            submission.id,
            document.id,
            request.env.user.id,
            upload.filename,
            request.httprequest.content_length,
        )
        document.write({
            "file": base64.b64encode(upload.read()).decode("ascii"),
            "filename": upload.filename,
            "state": "received",
            **date_values,
        })
        submission.message_post(
            body="Documento cargado desde portal: %s" % document.name,
        )
        submission.action_mark_documents_sent_if_complete()
        return request.redirect("/mis-solicitudes-riesgo/%s?upload_success=1" % submission.id)

    def _validate_portal_upload(self, upload, document):
        content_length = request.httprequest.content_length or 0
        max_size = DEFAULT_MAX_PORTAL_UPLOAD_SIZE
        if document.max_file_size_mb:
            max_size = int(document.max_file_size_mb * 1024 * 1024)
        if content_length > max_size:
            return "too_large"

        filename = upload.filename or ""
        extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed_extensions = document._allowed_file_extension_set()
        if not allowed_extensions:
            allowed_extensions = DEFAULT_ALLOWED_PORTAL_UPLOAD_EXTENSIONS
        if extension not in allowed_extensions:
            return "invalid_type"
        if upload.mimetype and upload.mimetype not in ALLOWED_PORTAL_UPLOAD_MIMETYPES:
            return "invalid_type"
        return None

    def _validate_portal_document_dates(self, document, post):
        values = {}
        today = fields.Date.context_today(document)

        if document.issue_date_required or document.max_age_days:
            issue_date = post.get("issue_date")
            if not issue_date:
                return "missing_issue_date", values
            try:
                parsed_issue_date = fields.Date.to_date(issue_date)
            except (TypeError, ValueError):
                return "invalid_date", values
            if not parsed_issue_date:
                return "invalid_date", values
            limit_date = today - timedelta(days=document.max_age_days)
            if document.max_age_days and parsed_issue_date < limit_date:
                return "old_issue_date", values
            values["issue_date"] = parsed_issue_date

        if document.validity_required:
            expiration_date = post.get("expiration_date")
            if not expiration_date:
                return "missing_expiration_date", values
            try:
                parsed_expiration_date = fields.Date.to_date(expiration_date)
            except (TypeError, ValueError):
                return "invalid_date", values
            if not parsed_expiration_date:
                return "invalid_date", values
            if document.reject_expired and parsed_expiration_date < today:
                return "expired_date", values
            values["expiration_date"] = parsed_expiration_date

        return None, values

    def _redirect_upload_error(self, submission, error_code):
        return request.redirect(
            "/mis-solicitudes-riesgo/%s?upload_error=%s" % (submission.id, error_code)
        )
