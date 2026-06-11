import base64
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


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
        if not document or not submission._portal_document_upload_allowed(document, request.env.user):
            _logger.warning(
                "Portal document upload denied submission_id=%s document_id=%s user_id=%s submission_state=%s document_state=%s",
                submission.id,
                document_id,
                request.env.user.id,
                submission.state,
                document.state if document else None,
            )
            return request.not_found()

        upload = request.httprequest.files.get("document_file")
        if not upload or not upload.filename:
            _logger.warning(
                "Portal document upload missing file submission_id=%s document_id=%s user_id=%s",
                submission.id,
                document.id,
                request.env.user.id,
            )
            return request.redirect("/mis-solicitudes-riesgo/%s?upload_error=missing" % submission.id)

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
        })
        submission.message_post(
            body="Documento cargado desde portal: %s" % document.name,
        )
        return request.redirect("/mis-solicitudes-riesgo/%s?upload_success=1" % submission.id)
