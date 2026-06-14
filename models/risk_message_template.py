from odoo import api, fields, models


class RiskMessageTemplate(models.Model):
    _name = "risk.message.template"
    _description = "Plantilla de mensaje de riesgo"
    _order = "message_type, category, sequence, name"

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    message_type = fields.Selection(
        [
            ("request", "Solicitud"),
            ("correction", "Correccion"),
            ("document", "Documentos"),
            ("approval", "Aprobacion"),
            ("final_rejection", "Rechazo definitivo"),
            ("portal", "Portal"),
            ("internal", "Interno"),
        ],
        string="Tipo de mensaje",
        required=True,
        default="document",
    )
    category = fields.Selection(
        [
            ("document_rejection", "Rechazo de documentos"),
            ("submission_rejection", "Rechazo definitivo"),
            ("submission_correction", "Solicitud de correccion"),
            ("document_request", "Solicitud de documentos"),
            ("document_rejected_email", "Correo de documento rechazado"),
        ],
        string="Donde se usa",
        required=True,
        default="document_rejection",
    )
    channel = fields.Selection(
        [
            ("modal", "Modal interno"),
            ("email", "Correo"),
            ("portal", "Portal"),
            ("chatter", "Chatter"),
            ("mixed", "Varios canales"),
        ],
        string="Canal",
        required=True,
        default="modal",
    )
    recipient_type = fields.Selection(
        [
            ("third_party", "Tercero"),
            ("risk_user", "Usuario de riesgo"),
            ("internal", "Interno"),
            ("mixed", "Mixto"),
        ],
        string="Destinatario",
        required=True,
        default="third_party",
    )
    code = fields.Char(string="Codigo", required=True)
    name = fields.Char(string="Nombre", required=True)
    subject = fields.Char(string="Asunto")
    usage_location = fields.Char(string="Donde se usa")
    available_variables = fields.Text(string="Variables disponibles")
    body = fields.Text(string="Mensaje", required=True)
    preview_subject = fields.Char(
        string="Vista previa del asunto",
        compute="_compute_preview",
    )
    preview_body = fields.Text(
        string="Vista previa del mensaje",
        compute="_compute_preview",
    )

    _sql_constraints = [
        (
            "category_code_unique",
            "unique(category, code)",
            "Ya existe una plantilla con esta categoria y codigo.",
        ),
    ]

    @api.onchange("category")
    def _onchange_category(self):
        for record in self:
            record._apply_category_defaults(record.category)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("category"):
                vals.update(
                    self._category_default_values(
                        vals["category"],
                        only_missing=True,
                        current_values=vals,
                    )
                )
            if not vals.get("code") and vals.get("name"):
                vals["code"] = self._unique_code(
                    vals.get("category") or "document_rejection",
                    vals["name"],
                )
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("category"):
            vals.update(
                self._category_default_values(
                    vals["category"],
                    only_missing=True,
                    current_values=vals,
                )
            )
        return super().write(vals)

    def init(self):
        mapping = {
            "document_rejection": "document",
            "submission_rejection": "final_rejection",
            "submission_correction": "correction",
            "document_request": "document",
            "document_rejected_email": "document",
        }
        for category, message_type in mapping.items():
            defaults = self._category_default_values(category)
            self.env.cr.execute(
                """
                UPDATE risk_message_template
                   SET message_type = %s
                 WHERE category = %s
                   AND (message_type IS NULL OR message_type = 'document')
                """,
                [message_type, category],
            )
            self.env.cr.execute(
                """
                UPDATE risk_message_template
                   SET channel = COALESCE(NULLIF(channel, ''), %s),
                       recipient_type = COALESCE(NULLIF(recipient_type, ''), %s),
                       usage_location = COALESCE(NULLIF(usage_location, ''), %s),
                       available_variables = COALESCE(NULLIF(available_variables, ''), %s)
                 WHERE category = %s
                """,
                [
                    defaults.get("channel"),
                    defaults.get("recipient_type"),
                    defaults.get("usage_location"),
                    defaults.get("available_variables"),
                    category,
                ],
            )

    def _message_type_from_category(self, category):
        mapping = {
            "document_rejection": "document",
            "submission_rejection": "final_rejection",
            "submission_correction": "correction",
            "document_request": "document",
            "document_rejected_email": "document",
        }
        return mapping.get(category or "", "request")

    def _category_default_values(
        self, category, only_missing=False, current_values=None
    ):
        current_values = current_values or {}
        defaults = {
            "document_rejection": {
                "message_type": "document",
                "channel": "modal",
                "recipient_type": "third_party",
                "usage_location": "Modal de rechazo de documento y correo de documento rechazado.",
                "available_variables": "documento, solicitud, placa, tercero",
            },
            "submission_rejection": {
                "message_type": "final_rejection",
                "channel": "modal",
                "recipient_type": "third_party",
                "usage_location": "Modal Rechazar definitivamente en la solicitud.",
                "available_variables": "solicitud, placa, propietario, conductor, motivo",
            },
            "submission_correction": {
                "message_type": "correction",
                "channel": "modal",
                "recipient_type": "third_party",
                "usage_location": "Modal Solicitar correccion y portal del tercero.",
                "available_variables": "solicitud, placa, secciones_a_corregir, motivo",
            },
            "document_request": {
                "message_type": "document",
                "channel": "email",
                "recipient_type": "third_party",
                "usage_location": "Correo enviado al solicitar documentos.",
                "available_variables": "solicitud, placa, documentos_solicitados",
            },
            "document_rejected_email": {
                "message_type": "document",
                "channel": "email",
                "recipient_type": "third_party",
                "usage_location": "Correo enviado al rechazar un documento individual.",
                "available_variables": "documento, solicitud, placa, motivo",
            },
        }.get(category or "", {})
        if not only_missing:
            return defaults
        return {
            key: value
            for key, value in defaults.items()
            if not current_values.get(key)
        }

    def _apply_category_defaults(self, category):
        for field_name, value in self._category_default_values(category).items():
            setattr(self, field_name, value)

    @api.depends("subject", "body")
    def _compute_preview(self):
        values = {
            "solicitud": "ABC123",
            "placa": "ABC123",
            "documento": "Licencia de conduccion",
            "propietario": "Juan Perez",
            "conductor": "Juan Perez",
            "tercero": "Juan Perez",
            "motivo": "Informacion pendiente por corregir",
            "secciones_a_corregir": "Vehiculo, Propietario",
            "documentos_solicitados": "SOAT, Licencia de conduccion",
        }
        for record in self:
            record.preview_subject = record._render_preview_text(
                record.subject or "", values
            )
            record.preview_body = record._render_preview_text(record.body or "", values)

    def _render_preview_text(self, text, values):
        rendered = text or ""
        for key, value in values.items():
            rendered = rendered.replace("{{ %s }}" % key, value)
            rendered = rendered.replace("{{%s}}" % key, value)
        return rendered

    def _unique_code(self, category, name):
        base = "".join(
            character if character.isalnum() else "_"
            for character in (name or "").lower()
        ).strip("_")
        while "__" in base:
            base = base.replace("__", "_")
        base = base or "plantilla"
        code = base
        index = 2
        while self.search_count([("category", "=", category), ("code", "=", code)]):
            code = "%s_%s" % (base, index)
            index += 1
        return code

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
