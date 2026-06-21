from odoo import fields, models


class RiskWarning(models.Model):
    _name = "risk.warning"
    _description = "Advertencia interna de riesgo"
    _inherit = ["mail.thread"]
    _order = "severity desc, create_date desc"

    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        required=True,
        ondelete="cascade",
        index=True,
    )
    rule_code = fields.Char(string="Regla", required=True, index=True)
    category = fields.Selection(
        [
            ("email", "Correo"),
            ("phone", "Telefono"),
            ("document", "Documento"),
            ("plate", "Placa"),
            ("history", "Historial"),
        ],
        string="Categoria",
        required=True,
        index=True,
    )
    severity = fields.Selection(
        [
            ("info", "Informativa"),
            ("warning", "Advertencia"),
            ("critical", "Critica"),
        ],
        string="Severidad",
        required=True,
        default="warning",
        tracking=True,
        index=True,
    )
    state = fields.Selection(
        [
            ("new", "Nueva"),
            ("reviewed", "Revisada"),
            ("dismissed", "Descartada"),
            ("confirmed", "Confirmada"),
        ],
        string="Estado",
        required=True,
        default="new",
        tracking=True,
        index=True,
    )
    message = fields.Text(string="Mensaje interno", required=True)
    matched_value = fields.Char(string="Valor detectado", required=True, index=True)
    related_submission_ids = fields.Many2many(
        "risk.module",
        "risk_warning_related_submission_rel",
        "warning_id",
        "submission_id",
        string="Solicitudes relacionadas",
    )
    reviewed_by_id = fields.Many2one(
        "res.users",
        string="Revisada por",
        readonly=True,
        copy=False,
    )
    reviewed_at = fields.Datetime(
        string="Fecha revision",
        readonly=True,
        copy=False,
    )
    review_note = fields.Text(string="Nota interna")

    _sql_constraints = [
        (
            "submission_rule_value_unique",
            "unique(submission_id, rule_code, matched_value)",
            "Ya existe esta advertencia para la solicitud.",
        ),
    ]

    def _set_review_state(self, state):
        self.write(
            {
                "state": state,
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": fields.Datetime.now(),
            }
        )

    def action_mark_reviewed(self):
        self._set_review_state("reviewed")
        return True

    def action_confirm(self):
        self._set_review_state("confirmed")
        return True

    def action_dismiss(self):
        self._set_review_state("dismissed")
        return True
