import logging
import werkzeug
from werkzeug.urls import url_encode

from odoo import http, _
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.models.res_users import SKIP_CAPTCHA_LOGIN
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


class RiskSignupController(AuthSignupHome):
    def _ensure_open_signup(self):
        _logger.debug("Ensuring open portal signup configuration")
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
        _logger.debug("Signup config forced signup_enabled=%s reset_password_enabled=%s", config.get("signup_enabled"), config.get("reset_password_enabled"))
        return config

    @http.route()
    def web_login(self, *args, **kw):
        self._ensure_open_signup()
        _logger.debug("Login page requested redirect=%s", kw.get("redirect") or request.params.get("redirect"))
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
        _logger.info(
            "Signup route requested method=%s login=%s redirect=%s signup_enabled=%s",
            request.httprequest.method,
            qcontext.get("login"),
            qcontext.get("redirect"),
            qcontext.get("signup_enabled"),
        )

        if not qcontext.get("token") and not qcontext.get("signup_enabled"):
            _logger.warning("Signup route blocked because signup is disabled")
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
                _logger.info("Signup completed login=%s user_id=%s", qcontext.get("login"), user_sudo.id if user_sudo else None)
                return self.web_login(*args, **kw)
            except UserError as e:
                _logger.warning("Signup user error login=%s error=%s", qcontext.get("login"), e.args[0])
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
                    _logger.warning("Signup blocked by duplicate login=%s", qcontext.get("login"))
                    qcontext["error"] = _(
                        "Another user is already registered using this email address."
                    )
                else:
                    _logger.exception("Signup failed login=%s", qcontext.get("login"))
                    qcontext["error"] = _(
                        "Could not create a new account. Please contact support."
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
                _logger.info("Signup email already exists, redirecting to login=%s", user.login)
                return request.redirect(
                    "/web/login?%s"
                    % url_encode({"login": user.login, "redirect": "/web"})
                )

        response = request.render("auth_signup.signup", qcontext)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
        return response
