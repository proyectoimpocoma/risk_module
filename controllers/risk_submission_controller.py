from datetime import date

from odoo import fields, http
from odoo.http import request

from .risk_submission_form_mapper import RiskSubmissionFormMapperMixin
from .risk_submission_form_schema import CC_REGEX, STEP_FIELDS, STEP_SESSION_KEYS
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
            return self._redirect_to_signup("/registro-conductor")
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
            or not self._can_access_submission(submission)
        ):
            return request.not_found()

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
            return self._redirect_to_signup("/registro-conductor/%s" % step)
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
            data["step_error"] = validation_error
            request.session["risk_vehicle_form"] = data
            return self._render_step(step)

        data.pop("step_error", None)
        self._persist_step_data(step, data)
        request.session["risk_vehicle_form"] = data

        if step < 7:
            return request.redirect("/registro-conductor/%s" % (step + 1))

        return self._submit_final_step(data)

    def _post_terms_step(self, data, post):
        """Procesa el paso de aceptación de términos del formulario.

        Valida que el usuario haya aceptado los términos y guarda la fecha/hora de aceptación.
        Si la aceptación falta, vuelve a renderizar el paso 4 con un mensaje de error.
        """
        if post.get("terms_accepted") != "1":
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)

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
            data["signature_error"] = validation_error
            request.session["risk_vehicle_form"] = data
            return self._render_step(5)

        self._stamp_owner_signature_metadata(data)
        self._persist_step_data(5, data)
        request.session["risk_vehicle_form"] = data
        return request.redirect("/registro-conductor/6")

    def _post_driver_signatures_step(self, data, post):
        """Procesa el paso de firma del conductor."""
        self._update_signature_data(data, post)
        data.pop("signature_error", None)

        validation_error = self._validate_driver_signature_step(data)
        if validation_error:
            data["signature_error"] = validation_error
            request.session["risk_vehicle_form"] = data
            return self._render_step(6)

        self._stamp_driver_signature_metadata(data)
        self._persist_step_data(6, data)
        submission = self._create_or_update_submission(data, state="draft")
        if not submission:
            return request.not_found()

        data["submission_id"] = submission.id
        data["submission_token"] = submission.access_token
        request.session["risk_vehicle_form"] = data
        request.session["risk_submission_id"] = submission.id
        return request.redirect("/registro-conductor/7")

    def _submit_final_step(self, data):
        """Finaliza el registro y crea la solicitud en estado submitted.

        Valida la aceptación de términos y la validez de las firmas antes de crear
        la solicitud final. Si falla alguna validación, redirige de nuevo al paso correspondiente.
        """
        if (
            data.get("terms_accepted") != "1"
            and request.session.get("risk_terms_accepted") != "1"
        ):
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)

        if not self._signatures_are_valid(data):
            data["signature_error"] = self._signature_error_message(data)
            request.session["risk_vehicle_form"] = data
            return self._render_step(self._first_invalid_signature_step(data))

        self._merge_persisted_step_data(data)
        submission = self._create_or_update_submission(data, state="submitted")
        if not submission:
            return request.not_found()
        self._reset_registration_session()
        return request.render(
            "risk_module.register_driver_success",
            {
                "submission": submission,
            },
        )

    def _first_invalid_signature_step(self, data):
        """Devuelve el primer paso de firma que presenta datos inválidos."""
        if not self._is_owner_signature_valid(data):
            return 5
        if not self._is_driver_signature_valid(data):
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
            return request.redirect("/registro-conductor")

        data = request.session.get("risk_vehicle_form", {})
        if step == 1 and not data.get("form_date"):
            data = dict(data, form_date=date.today().isoformat())
        if step >= 3:
            self._merge_persisted_step_data(data)
        if (
            step >= 5
            and data.get("terms_accepted") != "1"
            and request.session.get("risk_terms_accepted") != "1"
        ):
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)
        if step == 7 and not self._signatures_are_valid(data):
            data["signature_error"] = self._signature_error_message(data)
            request.session["risk_vehicle_form"] = data
            return self._render_step(self._first_invalid_signature_step(data))

        return request.render(
            "risk_module.register_driver",
            {
                "step": step,
                "data": data,
                "print_url": self._print_url(data),
            },
        )

    def _can_access_submission(self, submission):
        """Determina si el usuario actual puede ver la solicitud.

        Devuelve True para usuarios del grupo de riesgo o cuando la solicitud pertenece
        al portal del usuario actual.
        """
        user = request.env.user
        if user.has_group("risk_module.group_risk_user"):
            return True
        return submission._portal_is_owned_by(user)

    def _redirect_to_signup(self, redirect_url):
        """Redirige al usuario al login de Odoo con destino final configurado.

        Actualmente redirige a /web/login?redirect=/mis-solicitudes-riesgo.
        """
        return request.redirect("/web/login?redirect=/mis-solicitudes-riesgo")
