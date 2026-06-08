from datetime import date

from odoo import http
from odoo.http import request


class RiskModuleController(http.Controller):
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
        }

        for field in allowed_fields.get(step, ()):
            data[field] = post.get(field, "").strip()

        request.session["risk_vehicle_form"] = data

        if step < 3:
            return request.redirect("/registro-conductor/%s" % (step + 1))

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
            "message": data.get("message"),
        })

        request.session["risk_vehicle_form"] = {}
        return request.render("risk_module.register_driver_success", {
            "submission": submission,
        })

    def _render_step(self, step):
        if step not in (1, 2, 3):
            return request.redirect("/registro-conductor")

        data = request.session.get("risk_vehicle_form", {})
        if step == 1 and not data.get("form_date"):
            data = dict(data, form_date=date.today().isoformat())

        return request.render("risk_module.register_driver", {
            "step": step,
            "data": data,
        })
