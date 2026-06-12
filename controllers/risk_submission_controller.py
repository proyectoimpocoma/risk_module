import logging
from datetime import date

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from werkzeug.urls import url_encode

from .risk_submission_form_mapper import RiskSubmissionFormMapperMixin
from .risk_submission_form_schema import CC_REGEX, STEP_FIELDS, STEP_SESSION_KEYS
from .risk_submission_form_session import RiskSubmissionFormSessionMixin
from .risk_submission_form_signatures import RiskSubmissionFormSignatureMixin
from .risk_submission_form_validation import RiskSubmissionFormValidationMixin

_logger = logging.getLogger(__name__)


class RiskSubmissionController(
    RiskSubmissionFormSessionMixin,
    RiskSubmissionFormValidationMixin,
    RiskSubmissionFormSignatureMixin,
    RiskSubmissionFormMapperMixin,
    http.Controller,
):
    """Controlador web para el flujo de registro de conductor y solicitudes de riesgo."""

    @http.route(
        "/registro-conductor", type="http", auth="public", website=True, sitemap=True
    )
    def register_driver(self, **kwargs):
        """Inicio del formulario de registro de conductor.

        Si el usuario es anónimo, redirige al login.
        Si el usuario ya está autenticado, reinicia la sesión de registro y muestra el primer paso.
        """
        if request.env.user._is_public():
            _logger.info("Anonymous user redirected from risk registration start")
            return self._redirect_to_signup("/registro-conductor")
        _logger.info(
            "Risk registration started user_id=%s partner_id=%s",
            request.env.user.id,
            request.env.user.partner_id.id,
        )
        self._reset_registration_session()
        return self._render_step(1)

    @http.route(
        "/registro-conductor/imprimir/<int:submission_id>",
        type="http",
        auth="user",
        website=True,
        sitemap=False,
    )
    def register_driver_print(self, submission_id, token=None, **kwargs):
        """Renderiza el informe imprimible de una solicitud de riesgo.

        Verifica existencia de la solicitud, token de acceso y permisos del usuario.
        Devuelve 404 si la solicitud no existe o el usuario no puede acceder.
        """
        submission = request.env["risk.module"].sudo().browse(submission_id).exists()
        if (
            not submission
            or submission.access_token != token
            or not request.env.user.has_group("base.group_user")
            or not self._can_access_submission(submission)
        ):
            _logger.warning(
                "Printable risk submission denied submission_id=%s user_id=%s exists=%s token_match=%s",
                submission_id,
                request.env.user.id,
                bool(submission),
                bool(submission and submission.access_token == token),
            )
            return request.not_found()

        _logger.info(
            "Printable risk submission opened submission_id=%s user_id=%s",
            submission.id,
            request.env.user.id,
        )
        return request.render(
            "risk_module.report_risk_submission_document",
            {
                "docs": submission,
            },
        )

    @http.route(
        "/registro-conductor/<int:step>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def register_driver_step(self, step=1, **kwargs):
        """Muestra un paso específico del formulario de registro.

        La ruta es pública, pero si el usuario es anónimo redirige al login antes de mostrar el paso.
        """
        if request.env.user._is_public():
            _logger.info("Anonymous user redirected from risk registration step=%s", step)
            return self._redirect_to_signup("/registro-conductor/%s" % step)
        _logger.debug(
            "Rendering risk registration step=%s user_id=%s session_submission_id=%s",
            step,
            request.env.user.id,
            request.session.get("risk_submission_id"),
        )
        return self._render_step(step)

    @http.route(
        "/registro-conductor/submit/<int:step>",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def _post_register_driver(self, step=1, **post):
        """Procesa el POST de cada paso del formulario de registro.

        - Si step 4: procesa la aceptación de términos.
        - Si step 5: procesa la firma del propietario.
        - Si step 6: procesa la firma del conductor.
        - Si step 7: procesa el envío final con observaciones.
        """
        data = request.session.get("risk_vehicle_form", {})
        _logger.info(
            "Risk registration POST step=%s user_id=%s posted_fields=%s session_submission_id=%s",
            step,
            request.env.user.id,
            sorted(post.keys()),
            request.session.get("risk_submission_id"),
        )

        if step == 4:
            return self._post_terms_step(data, post)
        if step == 5:
            return self._post_owner_signatures_step(data, post)
        if step == 6:
            return self._post_driver_signatures_step(data, post)

        for field in STEP_FIELDS.get(step, ()):
            data[field] = post.get(field, "").strip()

        self._normalize_step_data(step, data)
        validation_error = self._validate_step(step, data)
        if validation_error:
            _logger.warning(
                "Risk registration validation failed step=%s user_id=%s error=%s",
                step,
                request.env.user.id,
                validation_error,
            )
            data["step_error"] = validation_error
            request.session["risk_vehicle_form"] = data
            return self._render_step(step)

        _logger.debug("Risk registration step=%s validated user_id=%s", step, request.env.user.id)
        data.pop("step_error", None)
        self._persist_step_data(step, data)
        request.session["risk_vehicle_form"] = data

        if step < 7:
            return request.redirect("/registro-conductor/%s" % (step + 1))

        return self._submit_final_step(data)

    @http.route(
        "/registro-conductor/firma/<string:party>/enviar-codigo",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def send_signature_code(self, party, **post):
        if party not in ("owner", "driver"):
            return request.not_found()
        data = request.session.get("risk_vehicle_form", {})
        self._update_signature_data(data, post)
        step = 5 if party == "owner" else 6
        self._persist_step_data(step, data)
        request.session["risk_vehicle_form"] = data

        submission, error_response = self._safe_create_or_update_submission(
            data,
            state="draft",
            error_step=step,
        )
        if error_response:
            return error_response
        if not submission:
            return request.not_found()

        result = (
            submission.sudo().send_owner_signature_code()
            if party == "owner"
            else submission.sudo().send_driver_signature_code()
        )
        self._sync_signature_verification_data(data, submission, party)
        self._persist_step_data(step, data)
        data["signature_info"] = result["message"] if result.get("ok") else ""
        data["signature_error"] = "" if result.get("ok") else result["message"]
        request.session["risk_vehicle_form"] = data
        request.session["risk_submission_id"] = submission.id
        _logger.info(
            "Signature code request processed submission_id=%s party=%s ok=%s user_id=%s",
            submission.id,
            party,
            result.get("ok"),
            request.env.user.id,
        )
        return self._render_step(step)

    @http.route(
        "/registro-conductor/firma/<string:party>/verificar-codigo",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def verify_signature_code(self, party, **post):
        if party not in ("owner", "driver"):
            return request.not_found()
        data = request.session.get("risk_vehicle_form", {})
        self._update_signature_data(data, post)
        step = 5 if party == "owner" else 6
        self._persist_step_data(step, data)
        request.session["risk_vehicle_form"] = data

        submission, error_response = self._safe_create_or_update_submission(
            data,
            state="draft",
            error_step=step,
        )
        if error_response:
            return error_response
        if not submission:
            return request.not_found()

        code = post.get("%s_signature_verification_code" % party, "")
        result = (
            submission.sudo().verify_owner_signature_code(
                code,
                ip_address=request.httprequest.remote_addr,
            )
            if party == "owner"
            else submission.sudo().verify_driver_signature_code(
                code,
                ip_address=request.httprequest.remote_addr,
            )
        )
        self._sync_signature_verification_data(data, submission, party)
        self._persist_step_data(step, data)
        data["signature_info"] = result["message"] if result.get("ok") else ""
        data["signature_error"] = "" if result.get("ok") else result["message"]
        request.session["risk_vehicle_form"] = data
        request.session["risk_submission_id"] = submission.id
        _logger.info(
            "Signature code verification processed submission_id=%s party=%s ok=%s user_id=%s",
            submission.id,
            party,
            result.get("ok"),
            request.env.user.id,
        )
        return self._render_step(step)

    def _post_terms_step(self, data, post):
        """Procesa el paso de aceptación de términos del formulario.

        Valida que el usuario haya aceptado los términos y guarda la fecha/hora de aceptación.
        Si la aceptación falta, vuelve a renderizar el paso 4 con un mensaje de error.
        """
        if post.get("terms_accepted") != "1":
            _logger.warning("Risk registration terms not accepted user_id=%s", request.env.user.id)
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)

        _logger.info("Risk registration terms accepted user_id=%s", request.env.user.id)
        data.update(
            {
                "terms_accepted": "1",
                "banking_info_accepted": "1",
                "compensation_accepted": "1",
                "personal_data_accepted": "1",
                "terms_accepted_at": fields.Datetime.to_string(fields.Datetime.now()),
            }
        )
        data.pop("terms_error", None)
        request.session["risk_terms_accepted"] = "1"
        self._persist_step_data(4, data)
        request.session["risk_vehicle_form"] = data
        return request.render(
            "risk_module.register_driver",
            {
                "step": 5,
                "data": data,
            },
        )

    def _post_owner_signatures_step(self, data, post):
        """Procesa el paso de firma del propietario."""
        self._update_signature_data(data, post)
        data.pop("signature_error", None)

        validation_error = self._validate_owner_signature_step(data)
        if validation_error:
            _logger.warning(
                "Owner signature validation failed user_id=%s error=%s",
                request.env.user.id,
                validation_error,
            )
            data["signature_error"] = validation_error
            request.session["risk_vehicle_form"] = data
            return self._render_step(5)

        _logger.info("Owner signature step completed user_id=%s", request.env.user.id)
        self._stamp_owner_signature_metadata(data)
        if data.get("single_owner_driver_signature") == "yes":
            self._apply_single_owner_driver_signature(data)
            self._persist_step_data(6, data)
            submission, error_response = self._safe_create_or_update_submission(
                data,
                state="draft",
                error_step=5,
            )
            if error_response:
                return error_response
            if not submission:
                _logger.warning(
                    "Risk submission draft blocked by ownership user_id=%s session_submission_id=%s",
                    request.env.user.id,
                    request.session.get("risk_submission_id"),
                )
                return request.not_found()
            data["submission_id"] = submission.id
            data["submission_token"] = submission.access_token
            request.session["risk_submission_id"] = submission.id
        self._persist_step_data(5, data)
        request.session["risk_vehicle_form"] = data
        if data.get("single_owner_driver_signature") == "yes":
            return request.redirect("/registro-conductor/7")
        return request.redirect("/registro-conductor/6")

    def _post_driver_signatures_step(self, data, post):
        """Procesa el paso de firma del conductor."""
        self._update_signature_data(data, post)
        data.pop("signature_error", None)

        validation_error = self._validate_driver_signature_step(data)
        if validation_error:
            _logger.warning(
                "Driver signature validation failed user_id=%s error=%s",
                request.env.user.id,
                validation_error,
            )
            data["signature_error"] = validation_error
            request.session["risk_vehicle_form"] = data
            return self._render_step(6)

        _logger.info("Driver signature step completed user_id=%s", request.env.user.id)
        self._stamp_driver_signature_metadata(data)
        self._persist_step_data(6, data)
        submission, error_response = self._safe_create_or_update_submission(
            data,
            state="draft",
            error_step=6,
        )
        if error_response:
            return error_response
        if not submission:
            _logger.warning(
                "Risk submission draft blocked by ownership user_id=%s session_submission_id=%s",
                request.env.user.id,
                request.session.get("risk_submission_id"),
            )
            return request.not_found()

        _logger.info(
            "Risk submission draft saved submission_id=%s user_id=%s plate=%s",
            submission.id,
            request.env.user.id,
            submission.vehicle_plate,
        )
        data["submission_id"] = submission.id
        data["submission_token"] = submission.access_token
        request.session["risk_vehicle_form"] = data
        request.session["risk_submission_id"] = submission.id
        return request.redirect("/registro-conductor/7")

    def _sync_signature_verification_data(self, data, submission, party=None):
        parties = (party,) if party else ("owner", "driver")
        for item in parties:
            prefix = "owner" if item == "owner" else "driver"
            for field in (
                "signature_email",
                "signature_code_sent_at",
                "signature_code_expires_at",
                "signature_verified_at",
                "signature_verified_ip",
                "signature_code_attempts",
                "signature_verification_state",
            ):
                model_field = "%s_%s" % (prefix, field)
                value = submission[model_field]
                if field.endswith("_at") and value:
                    value = fields.Datetime.to_string(value)
                data[model_field] = value or ""

    def _submit_final_step(self, data):
        """Finaliza el registro y crea la solicitud en estado submitted.

        Valida la aceptación de términos y la validez de las firmas antes de crear
        la solicitud final. Si falla alguna validación, redirige de nuevo al paso correspondiente.
        """
        self._merge_persisted_step_data(data)
        submission_id = data.get("submission_id") or request.session.get("risk_submission_id")
        if submission_id:
            submission = request.env["risk.module"].sudo().browse(int(submission_id)).exists()
            if submission and submission._portal_is_owned_by(request.env.user):
                self._sync_signature_verification_data(data, submission)
                request.session["risk_vehicle_form"] = data

        if (
            data.get("terms_accepted") != "1"
            and request.session.get("risk_terms_accepted") != "1"
        ):
            _logger.warning("Risk submission final blocked by missing terms user_id=%s", request.env.user.id)
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)

        if not self._signatures_are_valid(data):
            _logger.warning(
                "Risk submission final blocked by invalid signatures user_id=%s first_invalid_step=%s",
                request.env.user.id,
                self._first_invalid_signature_step(data),
            )
            data["signature_error"] = self._signature_error_message(data)
            request.session["risk_vehicle_form"] = data
            return self._render_step(self._first_invalid_signature_step(data))

        submission, error_response = self._safe_create_or_update_submission(
            data,
            state="submitted",
            error_step=7,
        )
        if error_response:
            return error_response
        if not submission:
            _logger.warning(
                "Risk submission final blocked by ownership user_id=%s session_submission_id=%s",
                request.env.user.id,
                request.session.get("risk_submission_id"),
            )
            return request.not_found()
        _logger.info(
            "Risk submission submitted submission_id=%s user_id=%s plate=%s",
            submission.id,
            request.env.user.id,
            submission.vehicle_plate,
        )
        self._reset_registration_session()
        return request.render(
            "risk_module.register_driver_success",
            {
                "submission": submission,
            },
        )

    def _first_invalid_signature_step(self, data):
        """Devuelve el primer paso de firma que presenta datos inválidos."""
        if (
            not self._is_owner_signature_valid(data)
            or self._signature_email_verification_error(data, "owner")
        ):
            return 5
        if (
            not self._is_driver_signature_valid(data)
            or self._signature_email_verification_error(data, "driver")
        ):
            return 6
        return 7

    def _is_owner_signature_valid(self, data):
        owner_required = data.get("owner_has_valid_study") != "yes"
        owner_document_ok = data.get("owner_signature_document") and CC_REGEX.match(
            data.get("owner_signature_document")
        )
        return not owner_required or (data.get("owner_signature") and owner_document_ok)

    def _is_driver_signature_valid(self, data):
        driver_required = data.get("driver_has_valid_study") != "yes"
        driver_document_ok = data.get("driver_signature_document") and CC_REGEX.match(
            data.get("driver_signature_document")
        )
        return not driver_required or (
            data.get("driver_signature") and driver_document_ok
        )

    def _render_step(self, step):
        """Renderiza la vista del formulario para el paso indicado.

        Valida que el paso exista, carga los datos de sesión y maneja condiciones
        especiales de los pasos de términos, firmas y revisión antes de renderizar.
        """
        if step not in STEP_SESSION_KEYS:
            _logger.warning("Invalid risk registration step requested step=%s user_id=%s", step, request.env.user.id)
            return request.redirect("/registro-conductor")

        data = request.session.get("risk_vehicle_form", {})
        if step == 1 and not data.get("form_date"):
            data = dict(data, form_date=date.today().isoformat())
        if step >= 3:
            self._merge_persisted_step_data(data)
        submission_id = data.get("submission_id") or request.session.get("risk_submission_id")
        if submission_id:
            submission = request.env["risk.module"].sudo().browse(int(submission_id)).exists()
            if submission and submission._portal_is_owned_by(request.env.user):
                self._sync_signature_verification_data(data, submission)
                request.session["risk_vehicle_form"] = data
        if (
            step >= 5
            and data.get("terms_accepted") != "1"
            and request.session.get("risk_terms_accepted") != "1"
        ):
            _logger.warning(
                "Risk registration step=%s redirected to terms user_id=%s",
                step,
                request.env.user.id,
            )
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)
        if step == 6 and data.get("single_owner_driver_signature") == "yes":
            self._apply_single_owner_driver_signature(data)
            self._persist_step_data(6, data)
            request.session["risk_vehicle_form"] = data
            if self._signatures_are_valid(data):
                return request.redirect("/registro-conductor/7")
            return request.redirect("/registro-conductor/5")
        if step == 7 and not self._signatures_are_valid(data):
            _logger.warning(
                "Risk registration review redirected to invalid signature step=%s user_id=%s",
                self._first_invalid_signature_step(data),
                request.env.user.id,
            )
            data["signature_error"] = self._signature_error_message(data)
            request.session["risk_vehicle_form"] = data
            return self._render_step(self._first_invalid_signature_step(data))

        _logger.debug(
            "Risk registration render step=%s user_id=%s data_keys=%s",
            step,
            request.env.user.id,
            sorted(data.keys()),
        )
        return request.render(
            "risk_module.register_driver",
            {
                "step": step,
                "data": data,
                "print_url": self._print_url(data) if request.env.user.has_group("base.group_user") else "",
            },
        )

    def _can_access_submission(self, submission):
        """Determina si el usuario actual puede ver la solicitud.

        Devuelve True para usuarios del grupo de riesgo o cuando la solicitud pertenece
        al portal del usuario actual.
        """
        user = request.env.user
        if user.has_group("risk_module.group_risk_user"):
            _logger.debug(
                "Risk submission access granted by internal group user_id=%s submission_id=%s",
                user.id,
                submission.id,
            )
            return True
        allowed = submission._portal_is_owned_by(user)
        _logger.debug(
            "Risk submission portal ownership checked user_id=%s submission_id=%s allowed=%s",
            user.id,
            submission.id,
            allowed,
        )
        return allowed

    def _redirect_to_signup(self, redirect_url):
        """Redirige al usuario al registro de Odoo conservando el destino final."""
        _logger.info("Redirecting user to login/signup target=%s", redirect_url)
        return request.redirect("/web/signup?%s" % url_encode({"redirect": redirect_url}))

    def _safe_create_or_update_submission(self, data, state, error_step):
        try:
            return self._create_or_update_submission(data, state), None
        except (ValidationError, UserError) as error:
            _logger.warning(
                "Risk submission save validation failed state=%s user_id=%s error=%s",
                state,
                request.env.user.id,
                error,
            )
            return None, self._render_submission_save_error(data, str(error), error_step)
        except Exception:
            _logger.exception(
                "Unexpected risk submission save failure state=%s user_id=%s",
                state,
                request.env.user.id,
            )
            return None, self._render_submission_save_error(
                data,
                "No pudimos guardar la solicitud en este momento. Intenta nuevamente.",
                error_step,
            )

    def _render_submission_save_error(self, data, message, step):
        data["step_error"] = message
        request.session["risk_vehicle_form"] = data
        return self._render_step(step)
