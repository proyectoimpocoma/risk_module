from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RiskAdditionalDocumentWizard(models.TransientModel):
    _name = "risk.additional.document.wizard"
    _description = "Solicitar documento adicional"

    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        required=True,
        readonly=True,
    )
    available_requirement_ids = fields.Many2many(
        "risk.document.requirement",
        compute="_compute_available_requirement_ids",
    )
    requirement_ids = fields.Many2many(
        "risk.document.requirement",
        "risk_additional_document_wizard_requirement_rel",
        "wizard_id",
        "requirement_id",
        string="Documentos a solicitar",
        domain="[('id', 'in', available_requirement_ids)]",
        required=True,
    )
    no_available_documents = fields.Boolean(
        string="Sin documentos disponibles",
        compute="_compute_available_requirement_ids",
    )
    notify_third_party = fields.Boolean(
        string="Notificar al tercero ahora",
        default=True,
    )

    @api.depends("submission_id", "submission_id.document_ids")
    def _compute_available_requirement_ids(self):
        requirement_model = self.env["risk.document.requirement"]
        for wizard in self:
            if not wizard.submission_id:
                wizard.available_requirement_ids = requirement_model
                wizard.no_available_documents = True
                continue
            existing_keys = {
                (document.document_type, document.party)
                for document in wizard.submission_id.document_ids
            }
            requirements = requirement_model.search(
                [("active", "=", True)],
                order="party, sequence, name",
            )
            available = requirements.filtered(
                lambda requirement: (
                    requirement.document_type,
                    requirement.party,
                )
                not in existing_keys
            )
            wizard.available_requirement_ids = available
            wizard.no_available_documents = not bool(available)

    @api.onchange("available_requirement_ids")
    def _onchange_available_requirement_ids(self):
        for wizard in self:
            wizard.requirement_ids = wizard.requirement_ids & wizard.available_requirement_ids

    def action_request_document(self):
        self.ensure_one()
        if not self.requirement_ids:
            raise ValidationError(
                "Selecciona al menos un documento adicional para solicitar."
            )

        existing_keys = {
            (document.document_type, document.party)
            for document in self.submission_id.document_ids
        }
        duplicated_requirements = self.requirement_ids.filtered(
            lambda requirement: (
                requirement.document_type,
                requirement.party,
            )
            in existing_keys
        )
        if duplicated_requirements:
            raise ValidationError(
                "Uno o mas documentos seleccionados ya fueron solicitados en la solicitud actual."
            )

        document_values = []
        for requirement in self.requirement_ids:
            values = requirement._to_document_template()
            document_values.append(
                {
                    "submission_id": self.submission_id.id,
                    "source": "manual",
                    **values,
                }
            )
        documents = self.env["risk.module.document"].create(document_values)
        if self.submission_id.state in ("manual_approval_pending", "documents_review"):
            self.submission_id.state = "documents_requested"
        document_names = ", ".join(documents.mapped("name"))
        self.submission_id.message_post(
            body="Documentos adicionales solicitados: <strong>%s</strong>."
            % document_names
        )
        if self.notify_third_party:
            self.submission_id.action_send_documents_requested_email()
        return {"type": "ir.actions.act_window_close"}
