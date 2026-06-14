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
    requirement_id = fields.Many2one(
        "risk.document.requirement",
        string="Documento a solicitar",
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
            if (
                wizard.requirement_id
                and wizard.requirement_id not in wizard.available_requirement_ids
            ):
                wizard.requirement_id = False

    def action_request_document(self):
        self.ensure_one()
        if not self.requirement_id:
            raise ValidationError("Selecciona el documento adicional que deseas solicitar.")
        existing = self.submission_id.document_ids.filtered(
            lambda document: (
                document.document_type == self.requirement_id.document_type
                and document.party == self.requirement_id.party
            )
        )
        if existing:
            raise ValidationError(
                "Este documento ya fue solicitado en la solicitud actual."
            )

        values = self.requirement_id._to_document_template()
        document = self.env["risk.module.document"].create(
            {
                "submission_id": self.submission_id.id,
                "source": "manual",
                **values,
            }
        )
        if self.submission_id.state in ("manual_approval_pending", "documents_review"):
            self.submission_id.state = "documents_requested"
        self.submission_id.message_post(
            body="Documento adicional solicitado: <strong>%s</strong>."
            % document.name
        )
        if self.notify_third_party:
            self.submission_id.action_send_documents_requested_email()
        return {"type": "ir.actions.act_window_close"}
