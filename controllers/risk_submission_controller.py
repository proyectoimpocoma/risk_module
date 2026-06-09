from datetime import date

from odoo import fields, http
from odoo.http import request

from .risk_submission_form_mapper import RiskSubmissionFormMapperMixin
from .risk_submission_form_schema import STEP_FIELDS, STEP_SESSION_KEYS
from .risk_submission_form_session import RiskSubmissionFormSessionMixin
from .risk_submission_form_signatures import RiskSubmissionFormSignatureMixin
from .risk_submission_form_validation import RiskSubmissionFormValidationMixin


class RiskSubmissionController(
    RiskSubmissionFormSessionMixin,
    RiskSubmissionFormValidationMixin,
    RiskSubmissionFormSignatureMixin,
    RiskSubmissionFormMapperMixin,
    http.Controller,
):
    @http.route("/registro-conductor", type="http", auth="public", website=True, sitemap=True)
    def register_driver(self, **kwargs):
        self._reset_registration_session()
        return self._render_step(1)

    @http.route("/registro-conductor/imprimir/<int:submission_id>", type="http", auth="public", website=True, sitemap=False)
    def register_driver_print(self, submission_id, token=None, **kwargs):
        submission = request.env["risk.module"].sudo().browse(submission_id).exists()
        if not submission or submission.access_token != token:
            return request.not_found()

        return request.render("risk_module.report_risk_submission_document", {
            "docs": submission,
        })

    @http.route("/registro-conductor/<int:step>", type="http", auth="public", website=True, sitemap=False)
    def register_driver_step(self, step=1, **kwargs):
        return self._render_step(step)

    @http.route(
        "/registro-conductor/submit/<int:step>",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def _post_register_driver(self, step=1, **post):
        data = request.session.get("risk_vehicle_form", {})

        if step == 4:
            return self._post_terms_step(data, post)
        if step == 5:
            return self._post_signatures_step(data, post)

        for field in STEP_FIELDS.get(step, ()):
            data[field] = post.get(field, "").strip()
        self._normalize_step_data(step, data)
        validation_error = self._validate_step(step, data)
        if validation_error:
            data["step_error"] = validation_error
            request.session["risk_vehicle_form"] = data
            return self._render_step(step)

        data.pop("step_error", None)
        self._persist_step_data(step, data)
        if step == 6:
            self._update_signature_data(data, post)

        request.session["risk_vehicle_form"] = data

        if step < 6:
            return request.redirect("/registro-conductor/%s" % (step + 1))

        return self._submit_final_step(data)

    def _post_terms_step(self, data, post):
        if post.get("terms_accepted") != "1":
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)

        data.update({
            "terms_accepted": "1",
            "banking_info_accepted": "1",
            "compensation_accepted": "1",
            "personal_data_accepted": "1",
            "terms_accepted_at": fields.Datetime.to_string(fields.Datetime.now()),
        })
        data.pop("terms_error", None)
        request.session["risk_terms_accepted"] = "1"
        self._persist_step_data(4, data)
        request.session["risk_vehicle_form"] = data
        return request.render("risk_module.register_driver", {
            "step": 5,
            "data": data,
        })

    def _post_signatures_step(self, data, post):
        self._update_signature_data(data, post)
        data.pop("signature_error", None)

        validation_error = self._validate_signature_step(data)
        if validation_error:
            data["signature_error"] = validation_error
            request.session["risk_vehicle_form"] = data
            return self._render_step(5)

        self._stamp_signature_metadata(data)
        self._persist_step_data(5, data)
        submission = self._create_or_update_submission(data, state="draft")
        data["submission_id"] = submission.id
        data["submission_token"] = submission.access_token
        request.session["risk_vehicle_form"] = data
        request.session["risk_submission_id"] = submission.id
        return request.render("risk_module.register_driver", {
            "step": 6,
            "data": data,
            "print_url": self._print_url(data),
        })

    def _submit_final_step(self, data):
        if data.get("terms_accepted") != "1" and request.session.get("risk_terms_accepted") != "1":
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)

        if not self._signatures_are_valid(data):
            data["signature_error"] = self._signature_error_message(data)
            request.session["risk_vehicle_form"] = data
            return self._render_step(5)

        self._merge_persisted_step_data(data)
        submission = self._create_or_update_submission(data, state="submitted")
        self._reset_registration_session()
        return request.render("risk_module.register_driver_success", {
            "submission": submission,
        })

    def _render_step(self, step):
        if step not in STEP_SESSION_KEYS:
            return request.redirect("/registro-conductor")

        data = request.session.get("risk_vehicle_form", {})
        if step == 1 and not data.get("form_date"):
            data = dict(data, form_date=date.today().isoformat())
        if step >= 3:
            self._merge_persisted_step_data(data)
        if step == 5 and data.get("terms_accepted") != "1" and request.session.get("risk_terms_accepted") != "1":
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)
        if step == 6 and not self._signatures_are_valid(data):
            data["signature_error"] = self._signature_error_message(data)
            request.session["risk_vehicle_form"] = data
            return self._render_step(5)

        return request.render("risk_module.register_driver", {
            "step": step,
            "data": data,
            "print_url": self._print_url(data),
        })
