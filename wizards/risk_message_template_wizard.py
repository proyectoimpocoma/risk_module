import re

from odoo import fields, models
from odoo.exceptions import ValidationError


class RiskMessageTemplateWizard(models.TransientModel):
    _name = "risk.message.template.wizard"
    _description = "Crear plantilla de mensaje"

    category = fields.Selection(
        [
            ("document_rejection", "Rechazo de documentos"),
            ("submission_correction", "Solicitud de correccion"),
            ("submission_rejection", "Rechazo definitivo"),
        ],
        string="Donde se usa",
        required=True,
        default="document_rejection",
    )
    name = fields.Char(string="Motivo", required=True)
    body = fields.Text(string="Mensaje", required=True)

    def action_create_template(self):
        self.ensure_one()
        if not (self.name or "").strip():
            raise ValidationError("Indica el motivo de la plantilla.")
        if not (self.body or "").strip():
            raise ValidationError("Escribe el mensaje que recibira el usuario.")

        template_model = self.env["risk.message.template"]
        code = self._unique_code(self.category, self.name)
        defaults = template_model._category_default_values(self.category)
        sequence = self._next_sequence(self.category)
        template = template_model.create(
            {
                "sequence": sequence,
                "active": True,
                "category": self.category,
                "code": code,
                "name": self.name.strip(),
                "body": self.body.strip(),
                **defaults,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": "Plantilla de mensaje",
            "res_model": "risk.message.template",
            "res_id": template.id,
            "view_mode": "form",
            "target": "current",
        }

    def _unique_code(self, category, name):
        base = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
        base = base or "plantilla"
        code = base
        index = 2
        template_model = self.env["risk.message.template"]
        while template_model.search_count(
            [("category", "=", category), ("code", "=", code)]
        ):
            code = "%s_%s" % (base, index)
            index += 1
        return code

    def _next_sequence(self, category):
        template = self.env["risk.message.template"].search(
            [("category", "=", category)],
            order="sequence desc",
            limit=1,
        )
        return (template.sequence or 0) + 10 if template else 10
