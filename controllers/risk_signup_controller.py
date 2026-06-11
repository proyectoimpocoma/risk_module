import logging
import werkzeug
from werkzeug.urls import url_encode

from markupsafe import Markup

from odoo import http, _
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.models.res_users import SKIP_CAPTCHA_LOGIN
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class RiskSignupController(AuthSignupHome):
    def _ensure_open_signup(self):
        request.env["ir.config_parameter"].sudo().set_param(
            "auth_signup.invitation_scope", "b2c"
        )
        request.env["ir.config_parameter"].sudo().set_param(
            "auth_signup.reset_password", "True"
        )

    def get_auth_signup_config(self):
        self._ensure_open_signup()
        config = super().get_auth_signup_config()
        config.update(
            {
                "signup_enabled": True,
                "reset_password_enabled": True,
            }
        )
        return config

    @http.route()
    def web_login(self, *args, **kw):
        self._ensure_open_signup()
        return super().web_login(*args, **kw)

    @http.route(
        "/web/signup",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        captcha="signup",
    )
    def web_auth_signup(self, *args, **kw):
        self._ensure_open_signup()
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get("token") and not qcontext.get("signup_enabled"):
            raise werkzeug.exceptions.NotFound()

        if "error" not in qcontext and request.httprequest.method == "POST":
            try:
                self.do_signup(qcontext)

                if request.session.uid is None:
                    public_user = request.env.ref("base.public_user")
                    request.update_env(user=public_user)

                User = request.env["res.users"]
                user_sudo = User.sudo().search(
                    User._get_login_domain(qcontext.get("login")),
                    order=User._get_login_order(),
                    limit=1,
                )
                template = request.env.ref(
                    "auth_signup.mail_template_user_signup_account_created",
                    raise_if_not_found=False,
                )
                if user_sudo and template:
                    template.sudo().send_mail(user_sudo.id, force_send=False)

                request.update_context(skip_captcha_login=SKIP_CAPTCHA_LOGIN)
                return self.web_login(*args, **kw)
            except UserError as e:
                qcontext["error"] = e.args[0]
            except (SignupError, AssertionError) as e:
                User = request.env["res.users"]
                if (
                    User.sudo()
                    .with_context(active_test=False)
                    .search_count(
                        User._get_login_domain(qcontext.get("login")), limit=1
                    )
                ):
                    qcontext["error"] = _(
                        "Another user is already registered using this email address."
                    )
                else:
                    _logger.warning("%s", e)
                    qcontext["error"] = (
                        _("Could not create a new account.") + Markup("<br/>") + str(e)
                    )

        elif "signup_email" in qcontext:
            user = (
                request.env["res.users"]
                .sudo()
                .search(
                    [
                        ("email", "=", qcontext.get("signup_email")),
                        ("state", "!=", "new"),
                    ],
                    limit=1,
                )
            )
            if user:
                return request.redirect(
                    "/web/login?%s"
                    % url_encode({"login": user.login, "redirect": "/web"})
                )

        response = request.render("auth_signup.signup", qcontext)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
        return response
