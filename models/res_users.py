from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_signup_invitation_scope(self):
        return "b2c"
