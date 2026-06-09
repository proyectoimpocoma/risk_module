from odoo.http import request

from .risk_submission_form_schema import STEP_FIELDS, STEP_SESSION_KEYS


class RiskSubmissionFormSessionMixin:
    def _reset_registration_session(self):
        request.session["risk_vehicle_form"] = {}
        for session_key in STEP_SESSION_KEYS.values():
            request.session[session_key] = {}
        request.session["risk_terms_accepted"] = None
        request.session["risk_submission_id"] = None

    def _merge_persisted_step_data(self, data):
        for step in sorted(STEP_SESSION_KEYS):
            step_data = request.session.get(STEP_SESSION_KEYS[step]) or {}
            for field, value in step_data.items():
                if value is not None:
                    data[field] = value

    def _persist_step_data(self, step, data):
        session_key = STEP_SESSION_KEYS.get(step)
        if not session_key:
            return
        request.session[session_key] = {
            field: data.get(field)
            for field in STEP_FIELDS.get(step, ())
        }

    def _print_url(self, data):
        submission_id = data.get("submission_id")
        token = data.get("submission_token")
        if not submission_id or not token:
            return ""
        return "/registro-conductor/imprimir/%s?token=%s" % (submission_id, token)
