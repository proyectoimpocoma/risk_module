import base64

from odoo import http
from odoo.http import request


class RiskSubmissionPortalController(http.Controller):
    def _get_portal_submission(self, submission_id):
        submission = request.env["risk.module"].sudo().browse(submission_id).exists()
        if not submission or not submission._portal_is_owned_by(request.env.user):
            return request.env["risk.module"]
        return submission

    def _get_portal_document(self, submission, document_id):
        document = request.env["risk.module.document"].sudo().browse(document_id).exists()
        if not document or document.submission_id != submission:
            return request.env["risk.module.document"]
        return document

    @http.route("/mis-solicitudes-riesgo", type="http", auth="user", website=True, sitemap=False)
    def portal_risk_submissions(self, **kwargs):
        submissions = request.env["risk.module"].sudo().search(
            [("partner_id", "=", request.env.user.partner_id.id)],
            order="create_date desc",
        )
        return request.render("risk_module.portal_risk_submission_list", {
            "submissions": submissions,
        })

    @http.route("/mis-solicitudes-riesgo/<int:submission_id>", type="http", auth="user", website=True, sitemap=False)
    def portal_risk_submission_detail(self, submission_id, **kwargs):
        submission = self._get_portal_submission(submission_id)
        if not submission:
            return request.not_found()
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
            return request.not_found()

        upload = request.httprequest.files.get("document_file")
        if not upload or not upload.filename:
            return request.redirect("/mis-solicitudes-riesgo/%s?upload_error=missing" % submission.id)

        document.write({
            "file": base64.b64encode(upload.read()).decode("ascii"),
            "filename": upload.filename,
            "state": "received",
        })
        submission.message_post(
            body="Documento cargado desde portal: %s" % document.name,
        )
        return request.redirect("/mis-solicitudes-riesgo/%s?upload_success=1" % submission.id)
