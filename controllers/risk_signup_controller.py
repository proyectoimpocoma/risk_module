from odoo import http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request


class RiskSignupController(AuthSignupHome):
    def _ensure_open_signup(self):
        request.env["ir.config_parameter"].sudo().set_param("auth_signup.invitation_scope", "b2c")
        request.env["ir.config_parameter"].sudo().set_param("auth_signup.reset_password", "True")

    def get_auth_signup_config(self):
        self._ensure_open_signup()
        config = super().get_auth_signup_config()
        config.update({
            "signup_enabled": True,
            "reset_password_enabled": True,
        })
        return config

    @http.route()
    def web_login(self, *args, **kw):
        self._ensure_open_signup()
        return super().web_login(*args, **kw)

    @http.route("/web/signup", type="http", auth="public", website=True, sitemap=False, captcha="signup")
    def web_auth_signup(self, *args, **kw):
        self._ensure_open_signup()
        return super().web_auth_signup(*args, **kw)
