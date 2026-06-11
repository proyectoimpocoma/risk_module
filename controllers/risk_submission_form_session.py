import logging

from odoo.http import request

from .risk_submission_form_schema import STEP_FIELDS, STEP_SESSION_KEYS

_logger = logging.getLogger(__name__)


class RiskSubmissionFormSessionMixin:
    def _reset_registration_session(self):
        _logger.debug("Resetting risk registration session user_id=%s", request.env.user.id)
        request.session["risk_vehicle_form"] = {}
        for session_key in STEP_SESSION_KEYS.values():
            request.session[session_key] = {}
        request.session["risk_terms_accepted"] = None
        request.session["risk_submission_id"] = None

    def _merge_persisted_step_data(self, data):
        merged_fields = set()
        for step in sorted(STEP_SESSION_KEYS):
            step_data = request.session.get(STEP_SESSION_KEYS[step]) or {}
            for field, value in step_data.items():
                if value is not None:
                    data[field] = value
                    merged_fields.add(field)
        _logger.debug(
            "Merged persisted risk registration session user_id=%s fields=%s",
            request.env.user.id,
            sorted(merged_fields),
        )

    def _persist_step_data(self, step, data):
        session_key = STEP_SESSION_KEYS.get(step)
        if not session_key:
            _logger.warning("Attempted to persist unknown risk registration step=%s", step)
            return
        request.session[session_key] = {
            field: data.get(field)
            for field in STEP_FIELDS.get(step, ())
        }
        _logger.debug(
            "Persisted risk registration step=%s user_id=%s fields=%s",
            step,
            request.env.user.id,
            list(STEP_FIELDS.get(step, ())),
        )

    def _print_url(self, data):
        submission_id = data.get("submission_id")
        token = data.get("submission_token")
        if not submission_id or not token:
            _logger.debug("Print URL unavailable submission_id=%s token_present=%s", submission_id, bool(token))
            return ""
        return "/registro-conductor/imprimir/%s?token=%s" % (submission_id, token)
