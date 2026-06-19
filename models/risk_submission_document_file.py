import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RiskSubmissionDocumentFile(models.Model):
    _name = "risk.module.document.file"
    _description = "Archivo multiple de documento de riesgo"
    _order = "document_id, sequence, id"

    document_id = fields.Many2one(
        "risk.module.document",
        string="Documento",
        required=True,
        ondelete="cascade",
        index=True,
    )
    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        related="document_id.submission_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    file = fields.Binary(string="Archivo", attachment=True, required=True)
    filename = fields.Char(string="Nombre de archivo", required=True)
    mimetype = fields.Char(string="Tipo MIME")
    file_size = fields.Integer(string="Tamano bytes")
    uploaded_by_id = fields.Many2one(
        "res.users",
        string="Cargado por",
        readonly=True,
        copy=False,
    )
    uploaded_at = fields.Datetime(
        string="Fecha de carga",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault("uploaded_by_id", self.env.user.id)
            vals.setdefault("uploaded_at", now)
        records = super().create(vals_list)
        records._check_document_file_limits()
        documents = records.mapped("document_id")
        documents.filtered(lambda doc: doc.state in ("pending", "rejected")).write(
            {"state": "received"}
        )
        documents.write(
            {
                "uploaded_by_id": self.env.user.id,
                "uploaded_at": now,
            }
        )
        for document in documents:
            document.message_post(
                body="Archivos cargados para documento: %s" % document.name
            )
            _logger.info(
                "Risk document multiple files uploaded document_id=%s file_count=%s user_id=%s",
                document.id,
                len(document.file_ids),
                self.env.user.id,
            )
        documents.mapped("submission_id").action_mark_documents_sent_if_complete()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._check_document_file_limits()
        return result

    def _check_document_file_limits(self):
        for document in self.mapped("document_id"):
            if not document.allow_multiple_files:
                raise ValidationError(
                    "El documento %s no permite multiples archivos." % document.name
                )
            max_files = document.max_files or 1
            if len(document.file_ids) > max_files:
                raise ValidationError(
                    "El documento %s permite maximo %s archivos."
                    % (document.name, max_files)
                )
