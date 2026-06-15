import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class RiskProcessController(http.Controller):
    @http.route("/riesgo/proceso", type="http", auth="user", website=False, sitemap=False)
    def risk_process_flow(self, **kwargs):
        """Render the internal process-flow reference page (read-only diagram)."""
        if not request.env.user.has_group("risk_module.group_risk_user"):
            return request.not_found()
        return request.render("risk_module.process_flow_page", {})
