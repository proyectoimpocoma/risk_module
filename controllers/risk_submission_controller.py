from datetime import date

from odoo import fields, http
from odoo.http import request


class RiskSubmissionController(http.Controller):
    @http.route("/registro-conductor", type="http", auth="public", website=True, sitemap=True)
    def register_driver(self, **kwargs):
        request.session["risk_vehicle_form"] = {}
        return self._render_step(1)

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
        allowed_fields = {
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
            5: ("message",),
        }

        if step == 4:
            if post.get("terms_accepted") != "1":
                data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
                request.session["risk_vehicle_form"] = data
                return self._render_step(4)

            data.update({
                "banking_info_accepted": True,
                "compensation_accepted": True,
                "personal_data_accepted": True,
                "terms_accepted_at": fields.Datetime.to_string(fields.Datetime.now()),
            })
            data.pop("terms_error", None)
        else:
            for field in allowed_fields.get(step, ()):
                data[field] = post.get(field, "").strip()

        request.session["risk_vehicle_form"] = data

        if step < 5:
            return request.redirect("/registro-conductor/%s" % (step + 1))

        if not data.get("banking_info_accepted") or not data.get("compensation_accepted") or not data.get("personal_data_accepted"):
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)

        plate = data.get("vehicle_plate") or "Sin placa"
        submission = request.env["risk.module"].sudo().create({
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
            "banking_info_accepted": bool(data.get("banking_info_accepted")),
            "compensation_accepted": bool(data.get("compensation_accepted")),
            "personal_data_accepted": bool(data.get("personal_data_accepted")),
            "terms_accepted_at": data.get("terms_accepted_at") or False,
            "message": data.get("message"),
        })

        request.session["risk_vehicle_form"] = {}
        return request.render("risk_module.register_driver_success", {
            "submission": submission,
        })

    def _render_step(self, step):
        if step not in (1, 2, 3, 4, 5):
            return request.redirect("/registro-conductor")

        data = request.session.get("risk_vehicle_form", {})
        if step == 1 and not data.get("form_date"):
            data = dict(data, form_date=date.today().isoformat())
        if step == 5 and not data.get("banking_info_accepted"):
            data["terms_error"] = "Debes leer y aceptar los terminos para continuar."
            request.session["risk_vehicle_form"] = data
            return self._render_step(4)

        return request.render("risk_module.register_driver", {
            "step": step,
            "data": data,
        })
