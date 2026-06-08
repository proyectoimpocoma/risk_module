import re
from datetime import date

from odoo import fields, http
from odoo.http import request


class RiskSubmissionController(http.Controller):
    PLATE_REGEX = re.compile(r"^[A-Z]{3}[0-9]{2,3}$")
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
    CC_REGEX = re.compile(r"^[0-9]{6,10}$")
    NIT_REGEX = re.compile(r"^[0-9]{9}(-[0-9])?$")
    CHOICE_VALUES = {
        "owner_document_type": ("cc", "nit"),
        "advance_payment_to": ("driver", "owner"),
        "same_owner_on_license": ("yes", "no"),
        "registered_owner_document_type": ("cc", "nit"),
        "driver_is_fit": ("yes", "no"),
        "driver_is_trained": ("yes", "no"),
        "owner_has_valid_study": ("yes", "no"),
        "driver_has_valid_study": ("yes", "no"),
    }
    TEXT_LIMITS = {
        "satellite_company": 80,
        "satellite_user": 80,
        "satellite_password": 80,
        "owner_name": 140,
        "owner_address": 140,
        "owner_neighborhood": 80,
        "owner_city": 80,
        "registered_owner_name": 140,
        "driver_name": 140,
        "driver_address": 140,
        "driver_neighborhood": 80,
        "driver_city": 80,
        "family_reference_name": 140,
        "family_reference_relationship": 80,
        "cargo_reference_name": 140,
        "message": 1000,
    }

    STEP_FIELDS = {
        1: (
            "form_date",
            "vehicle_plate",
            "semi_trailer_plate",
            "satellite_company",
            "satellite_user",
            "satellite_password",
        ),
        2: (
            "owner_name",
            "owner_document_type",
            "owner_document_number",
            "owner_address",
            "owner_neighborhood",
            "owner_city",
            "owner_phone",
            "owner_email",
            "advance_payment_to",
            "same_owner_on_license",
            "registered_owner_document_type",
            "registered_owner_document_number",
            "registered_owner_name",
            "registered_owner_phone",
        ),
        3: (
            "driver_name",
            "driver_document_number",
            "driver_address",
            "driver_neighborhood",
            "driver_city",
            "driver_phone",
            "driver_optional_phone",
            "driver_email",
            "driver_is_fit",
            "driver_is_trained",
            "family_reference_name",
            "family_reference_relationship",
            "family_reference_phone",
            "cargo_reference_name",
            "cargo_reference_phone",
        ),
        4: (
            "terms_accepted",
            "banking_info_accepted",
            "compensation_accepted",
            "personal_data_accepted",
            "terms_accepted_at",
        ),
        5: (
            "owner_has_valid_study",
            "owner_signature",
            "owner_signature_document",
            "owner_signed_at",
            "owner_signature_ip",
            "owner_signature_user_agent",
            "driver_has_valid_study",
            "driver_signature",
            "driver_signature_document",
            "driver_signed_at",
            "driver_signature_ip",
            "driver_signature_user_agent",
        ),
        6: ("message",),
    }

    STEP_SESSION_KEYS = {
        1: "risk_step_1_form",
        2: "risk_step_2_form",
        3: "risk_step_3_form",
        4: "risk_step_4_form",
        5: "risk_step_5_form",
        6: "risk_step_6_form",
    }

    @http.route("/registro-conductor", type="http", auth="public", website=True, sitemap=True)
    def register_driver(self, **kwargs):
        request.session["risk_vehicle_form"] = {}
        for session_key in self.STEP_SESSION_KEYS.values():
            request.session[session_key] = {}
        request.session["risk_terms_accepted"] = None
        request.session["risk_submission_id"] = None
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
        elif step == 5:
            self._update_signature_data(data, post)
            data.pop("signature_error", None)

            if data.get("owner_has_valid_study") not in ("yes", "no"):
                data["signature_error"] = "Debes indicar si el propietario cuenta con estudio vigente."
                request.session["risk_vehicle_form"] = data
                return self._render_step(5)
            if data.get("driver_has_valid_study") not in ("yes", "no"):
                data["signature_error"] = "Debes indicar si el conductor cuenta con estudio vigente."
                request.session["risk_vehicle_form"] = data
                return self._render_step(5)

            if not self._signatures_are_valid(data):
                data["signature_error"] = self._signature_error_message(data)
                request.session["risk_vehicle_form"] = data
                return self._render_step(5)

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
        else:
            for field in self.STEP_FIELDS.get(step, ()):
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

        request.session["risk_vehicle_form"] = {}
        for session_key in self.STEP_SESSION_KEYS.values():
            request.session[session_key] = {}
        request.session["risk_terms_accepted"] = None
        request.session["risk_submission_id"] = None
        return request.render("risk_module.register_driver_success", {
            "submission": submission,
        })

    def _render_step(self, step):
        if step not in (1, 2, 3, 4, 5, 6):
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

    def _normalize_step_data(self, step, data):
        if step == 1:
            for field in ("vehicle_plate", "semi_trailer_plate"):
                if data.get(field):
                    data[field] = data[field].strip().upper()
        if step in (2, 3):
            for field in ("owner_city", "driver_city"):
                if data.get(field):
                    data[field] = data[field].strip().title()

    def _validate_step(self, step, data):
        length_error = self._validate_text_lengths(data)
        if length_error:
            return length_error

        if step == 1:
            vehicle_plate = data.get("vehicle_plate")
            semi_trailer_plate = data.get("semi_trailer_plate")
            form_date = data.get("form_date")
            if not form_date:
                return "La fecha es obligatoria."
            try:
                parsed_date = date.fromisoformat(form_date)
            except ValueError:
                return "La fecha no tiene un formato valido."
            if parsed_date > date.today():
                return "La fecha no puede ser futura."
            if not vehicle_plate:
                return "La placa del vehiculo es obligatoria."
            if not self.PLATE_REGEX.match(vehicle_plate):
                return (
                    "La placa del vehiculo debe tener formato colombiano valido: "
                    "ABC123 para vehiculo/carga o ABC12 para motocicleta."
                )
            if semi_trailer_plate and not self.PLATE_REGEX.match(semi_trailer_plate):
                return (
                    "La placa del semi/remolque debe tener formato colombiano valido: "
                    "ABC123 o ABC12."
                )

        if step == 2:
            owner_email = data.get("owner_email")
            owner_document_type = data.get("owner_document_type")
            owner_document_number = data.get("owner_document_number")
            if not data.get("owner_name"):
                return "El nombre del propietario, tenedor o empresa es obligatorio."
            owner_document_error = self._validate_document(
                owner_document_type,
                owner_document_number,
                "documento del propietario",
            )
            if owner_document_error:
                return owner_document_error
            if owner_email and not self.EMAIL_REGEX.match(owner_email):
                return "El correo del propietario no tiene un formato valido. Ejemplo: propietario@empresa.com."
            phone_error = self._validate_mobile_phone(data.get("owner_phone"), "celular del propietario")
            if phone_error:
                return phone_error
            registered_owner_document_error = self._validate_document(
                data.get("registered_owner_document_type"),
                data.get("registered_owner_document_number"),
                "documento del propietario registrado",
                required=False,
            )
            if registered_owner_document_error:
                return registered_owner_document_error
            registered_phone_error = self._validate_mobile_phone(
                data.get("registered_owner_phone"),
                "celular del propietario registrado",
            )
            if registered_phone_error:
                return registered_phone_error

        if step == 3:
            if not data.get("driver_name"):
                return "El nombre del conductor es obligatorio."
            if not data.get("driver_document_number"):
                return "La cedula del conductor es obligatoria."
            if not self.CC_REGEX.match(data.get("driver_document_number")):
                return "La cedula del conductor debe contener entre 6 y 10 digitos numericos."
            driver_phone_error = self._validate_mobile_phone(data.get("driver_phone"), "celular del conductor")
            if driver_phone_error:
                return driver_phone_error
            optional_phone_error = self._validate_phone(data.get("driver_optional_phone"), "telefono opcional")
            if optional_phone_error:
                return optional_phone_error
            if data.get("driver_email") and not self.EMAIL_REGEX.match(data.get("driver_email")):
                return "El correo del conductor no tiene un formato valido. Ejemplo: conductor@empresa.com."
            family_phone_error = self._validate_mobile_phone(data.get("family_reference_phone"), "celular de referencia familiar")
            if family_phone_error:
                return family_phone_error
            cargo_phone_error = self._validate_mobile_phone(data.get("cargo_reference_phone"), "celular de referencia de carga")
            if cargo_phone_error:
                return cargo_phone_error
            if data.get("driver_is_fit") not in ("yes", "no"):
                return "Debes indicar si el conductor es apto fisica, mental y psicotecnicamente."
            if data.get("driver_is_trained") not in ("yes", "no"):
                return "Debes indicar si el conductor esta capacitado y entrenado."
        return None

    def _validate_text_lengths(self, data):
        for field, max_length in self.TEXT_LIMITS.items():
            value = data.get(field)
            if value and len(value) > max_length:
                return "El campo %s no puede superar %s caracteres." % (field, max_length)
        for field, allowed_values in self.CHOICE_VALUES.items():
            value = data.get(field)
            if value and value not in allowed_values:
                return "El campo %s tiene una opcion invalida." % field
        return None

    def _validate_document(self, document_type, document_number, label, required=True):
        if not document_type and not document_number and not required:
            return None
        if not document_type:
            return "Debes seleccionar CC o NIT para el %s." % label
        if not document_number:
            return "Debes diligenciar el numero del %s." % label
        if document_type == "cc" and not self.CC_REGEX.match(document_number):
            return "La cedula del %s debe contener entre 6 y 10 digitos numericos." % label
        if document_type == "nit" and not self.NIT_REGEX.match(document_number):
            return "El NIT del %s debe tener formato 123456789 o 123456789-0." % label
        return None

    def _phone_digits(self, phone):
        return re.sub(r"\D", "", phone or "")

    def _validate_mobile_phone(self, phone, label):
        if not phone:
            return None
        digits = self._phone_digits(phone)
        if len(digits) != 10 or not digits.startswith("3"):
            return "El %s debe ser un celular colombiano de 10 digitos que inicia por 3." % label
        return None

    def _validate_phone(self, phone, label):
        if not phone:
            return None
        digits = self._phone_digits(phone)
        if len(digits) == 7:
            return None
        if len(digits) == 10 and digits[0] in ("3", "6"):
            return None
        return "El %s debe tener 7 digitos o 10 digitos iniciando por 3 o 6." % label

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

    def _signatures_are_valid(self, data):
        owner_required = data.get("owner_has_valid_study") != "yes"
        driver_required = data.get("driver_has_valid_study") != "yes"
        owner_document_ok = data.get("owner_signature_document") and self.CC_REGEX.match(data.get("owner_signature_document"))
        driver_document_ok = data.get("driver_signature_document") and self.CC_REGEX.match(data.get("driver_signature_document"))
        owner_ok = not owner_required or (data.get("owner_signature") and owner_document_ok)
        driver_ok = not driver_required or (data.get("driver_signature") and driver_document_ok)
        return owner_ok and driver_ok

    def _signature_error_message(self, data):
        missing = []
        if data.get("owner_has_valid_study") != "yes":
            if not data.get("owner_signature"):
                missing.append("firma del propietario")
            if not data.get("owner_signature_document") or not self.CC_REGEX.match(data.get("owner_signature_document")):
                missing.append("cedula del propietario valida")
        if data.get("driver_has_valid_study") != "yes":
            if not data.get("driver_signature"):
                missing.append("firma del conductor")
            if not data.get("driver_signature_document") or not self.CC_REGEX.match(data.get("driver_signature_document")):
                missing.append("cedula del conductor valida")
        if missing:
            return "Debes completar: %s." % ", ".join(missing)
        return "Debes completar la firma y cedula cuando el propietario o conductor no cuenta con estudio vigente."

    def _submission_values(self, data, state):
        self._merge_persisted_step_data(data)
        plate = data.get("vehicle_plate") or "Sin placa"
        return {
            "state": state,
            "name": "Habilitacion vehiculo %s" % plate,
            "form_date": data.get("form_date") or False,
            "vehicle_plate": plate,
            "semi_trailer_plate": data.get("semi_trailer_plate"),
            "satellite_company": data.get("satellite_company"),
            "satellite_user": data.get("satellite_user"),
            "satellite_password": data.get("satellite_password"),
            "owner_name": data.get("owner_name"),
            "owner_document_type": data.get("owner_document_type"),
            "owner_document_number": data.get("owner_document_number"),
            "owner_address": data.get("owner_address"),
            "owner_neighborhood": data.get("owner_neighborhood"),
            "owner_city": data.get("owner_city"),
            "owner_phone": data.get("owner_phone"),
            "owner_email": data.get("owner_email"),
            "advance_payment_to": data.get("advance_payment_to"),
            "same_owner_on_license": data.get("same_owner_on_license"),
            "registered_owner_document_type": data.get("registered_owner_document_type"),
            "registered_owner_document_number": data.get("registered_owner_document_number"),
            "registered_owner_name": data.get("registered_owner_name"),
            "registered_owner_phone": data.get("registered_owner_phone"),
            "driver_name": data.get("driver_name"),
            "driver_document_number": data.get("driver_document_number"),
            "driver_address": data.get("driver_address"),
            "driver_neighborhood": data.get("driver_neighborhood"),
            "driver_city": data.get("driver_city"),
            "driver_phone": data.get("driver_phone"),
            "driver_optional_phone": data.get("driver_optional_phone"),
            "driver_email": data.get("driver_email"),
            "driver_is_fit": data.get("driver_is_fit"),
            "driver_is_trained": data.get("driver_is_trained"),
            "family_reference_name": data.get("family_reference_name"),
            "family_reference_relationship": data.get("family_reference_relationship"),
            "family_reference_phone": data.get("family_reference_phone"),
            "cargo_reference_name": data.get("cargo_reference_name"),
            "cargo_reference_phone": data.get("cargo_reference_phone"),
            "banking_info_accepted": data.get("banking_info_accepted") == "1" or request.session.get("risk_terms_accepted") == "1",
            "compensation_accepted": data.get("compensation_accepted") == "1" or request.session.get("risk_terms_accepted") == "1",
            "personal_data_accepted": data.get("personal_data_accepted") == "1" or request.session.get("risk_terms_accepted") == "1",
            "terms_accepted_at": data.get("terms_accepted_at") or False,
            "owner_has_valid_study": data.get("owner_has_valid_study"),
            "owner_signature": data.get("owner_signature"),
            "owner_signature_document": data.get("owner_signature_document"),
            "owner_signed_at": data.get("owner_signed_at") or False,
            "owner_signature_ip": data.get("owner_signature_ip"),
            "owner_signature_user_agent": data.get("owner_signature_user_agent"),
            "driver_has_valid_study": data.get("driver_has_valid_study"),
            "driver_signature": data.get("driver_signature"),
            "driver_signature_document": data.get("driver_signature_document"),
            "driver_signed_at": data.get("driver_signed_at") or False,
            "driver_signature_ip": data.get("driver_signature_ip"),
            "driver_signature_user_agent": data.get("driver_signature_user_agent"),
            "message": data.get("message"),
        }

    def _create_or_update_submission(self, data, state):
        self._merge_persisted_step_data(data)
        submission_id = data.get("submission_id") or request.session.get("risk_submission_id")
        submission = request.env["risk.module"].sudo().browse(int(submission_id or 0)).exists()
        values = self._submission_values(data, state)
        if submission:
            submission.write(values)
        else:
            submission = request.env["risk.module"].sudo().create(values)
        data["submission_id"] = submission.id
        data["submission_token"] = submission.access_token
        return submission

    def _merge_persisted_step_data(self, data):
        for step in sorted(self.STEP_SESSION_KEYS):
            step_data = request.session.get(self.STEP_SESSION_KEYS[step]) or {}
            for field, value in step_data.items():
                if value is not None:
                    data[field] = value

    def _persist_step_data(self, step, data):
        session_key = self.STEP_SESSION_KEYS.get(step)
        if not session_key:
            return
        request.session[session_key] = {
            field: data.get(field)
            for field in self.STEP_FIELDS.get(step, ())
        }

    def _print_url(self, data):
        submission_id = data.get("submission_id")
        token = data.get("submission_token")
        if not submission_id or not token:
            return ""
        return "/registro-conductor/imprimir/%s?token=%s" % (submission_id, token)
