from odoo import fields, models


class RiskMessageTemplate(models.Model):
    _name = "risk.message.template"
    _description = "Plantilla de mensaje de riesgo"
    _order = "category, sequence, name"

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category = fields.Selection(
        [
            ("document_rejection", "Rechazo de documento"),
            ("submission_rejection", "Rechazo de solicitud"),
            ("document_request", "Solicitud de documentos"),
            ("document_rejected_email", "Correo de documento rechazado"),
        ],
        string="Categoria",
        required=True,
    )
    code = fields.Char(string="Codigo", required=True)
    name = fields.Char(string="Nombre", required=True)
    subject = fields.Char(string="Asunto")
    body = fields.Text(string="Mensaje", required=True)

    _sql_constraints = [
        (
            "category_code_unique",
            "unique(category, code)",
            "Ya existe una plantilla con esta categoria y codigo.",
        ),
    ]

    def _get_body(self, category, code, default=False):
        template = self.search(
            [
                ("category", "=", category),
                ("code", "=", code),
                ("active", "=", True),
            ],
            limit=1,
        )
        return template.body if template else default
