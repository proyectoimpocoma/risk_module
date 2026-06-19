import base64
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
    # No es obligatorio: en modo solo-SharePoint el binario local se purga tras
    # subir y el archivo queda referenciado por ``sharepoint_item_id``.
    file = fields.Binary(string="Archivo", attachment=True)
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
    sharepoint_item_id = fields.Char(
        string="SharePoint item",
        readonly=True,
        copy=False,
        index=True,
    )
    sharepoint_web_url = fields.Char(
        string="Enlace SharePoint",
        readonly=True,
        copy=False,
    )
    sharepoint_drive_id = fields.Char(
        string="SharePoint drive",
        readonly=True,
        copy=False,
    )
    sharepoint_state = fields.Selection(
        [
            ("disabled", "Sin sincronizar"),
            ("pending", "Pendiente"),
            ("synced", "En SharePoint"),
            ("error", "Error"),
        ],
        string="Estado SharePoint",
        default="disabled",
        copy=False,
    )
    sharepoint_synced_at = fields.Datetime(
        string="Sincronizado en",
        readonly=True,
        copy=False,
    )
    sharepoint_error = fields.Text(
        string="Error de sincronizacion",
        readonly=True,
        copy=False,
    )
    sharepoint_attempts = fields.Integer(
        string="Intentos de sincronizacion",
        readonly=True,
        copy=False,
        default=0,
    )

    @api.constrains("file", "sharepoint_item_id")
    def _check_file_or_sharepoint(self):
        for record in self:
            if not record.file and not record.sharepoint_item_id:
                raise ValidationError(
                    "El archivo %s debe tener contenido o estar sincronizado en SharePoint."
                    % (record.filename or record.id)
                )

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            vals.setdefault("uploaded_by_id", self.env.user.id)
            vals.setdefault("uploaded_at", now)
        records = super().create(vals_list)
        records._check_document_file_limits()
        if self.env["risk.sharepoint.service"]._is_enabled():
            records.filtered(lambda rec: rec.file).write(
                {"sharepoint_state": "pending"}
            )
        documents = records.mapped("document_id")
        documents.filtered(lambda doc: doc.state == "pending").write(
            {"state": "received"}
        )
        documents.filtered(lambda doc: doc.state == "rejected").write(
            {
                "state": "received",
                "rejection_reason": False,
                "rejection_message_sent_at": False,
            }
        )
        for document in documents:
            latest_file = document.file_ids.sorted(lambda item: (item.uploaded_at, item.id))[-1]
            document.write(
                {
                    "uploaded_by_id": latest_file.uploaded_by_id.id,
                    "uploaded_at": latest_file.uploaded_at,
                }
            )
            document.message_post(
                body="Archivos cargados para documento: %s" % document.name
            )
            _logger.info(
                "Risk document multiple files uploaded document_id=%s file_count=%s user_id=%s",
                document.id,
                len(document.file_ids),
                self.env.user.id,
            )
        documents._recompute_sharepoint_state_from_files()
        documents.mapped("submission_id").action_mark_documents_sent_if_complete()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._check_document_file_limits()
        return result

    # ------------------------------------------------------------------
    # Sincronizacion con SharePoint (un item por archivo)
    # ------------------------------------------------------------------
    def _sp_unique_filename(self):
        """Nombre unico por archivo para evitar colisiones (todos los archivos
        de un documento viven en la misma carpeta de SharePoint)."""
        self.ensure_one()
        name = self.filename or self.document_id.name or "documento"
        if "." in name:
            stem, extension = name.rsplit(".", 1)
            return "%s (%s).%s" % (stem, self.id, extension)
        return "%s (%s)" % (name, self.id)

    def _sync_to_sharepoint(self):
        """Sube este archivo a SharePoint (lo invoca el cron o el reintento).

        Si ya existe ``sharepoint_item_id`` sube una nueva version del mismo
        item; si no, crea el archivo. Tras subir purga la copia local si la
        configuracion lo indica.
        """
        self.ensure_one()
        service = self.env["risk.sharepoint.service"]
        cfg = service._config()
        if not self.file:
            if self.sharepoint_item_id:
                self.sharepoint_state = "synced"
                self.document_id._recompute_sharepoint_state_from_files()
            return
        content = base64.b64decode(self.file)
        try:
            result = service._store_file(
                self.document_id._sp_folder_segments(),
                self._sp_unique_filename(),
                content,
                item_id=self.sharepoint_item_id or None,
            )
        except Exception as exc:  # noqa: BLE001 - se registra y se reintenta luego
            self._sp_mark_error(str(exc), cfg)
            return
        vals = {
            "sharepoint_item_id": result["item_id"],
            "sharepoint_web_url": result["web_url"],
            "sharepoint_drive_id": result["drive_id"],
            "sharepoint_state": "synced",
            "sharepoint_synced_at": fields.Datetime.now(),
            "sharepoint_error": False,
        }
        if cfg["purge_local"]:
            vals["file"] = False
        self.write(vals)
        self.document_id._recompute_sharepoint_state_from_files()
        _logger.info(
            "SharePoint file sync ok file_id=%s document_id=%s item_id=%s purged=%s",
            self.id,
            self.document_id.id,
            result["item_id"],
            cfg["purge_local"],
        )

    def _sp_mark_error(self, message, cfg=None):
        """Registra un fallo de sincronizacion y decide si reintentar."""
        self.ensure_one()
        cfg = cfg or self.env["risk.sharepoint.service"]._config()
        attempts = self.sharepoint_attempts + 1
        give_up = attempts >= cfg["max_attempts"]
        self.write(
            {
                "sharepoint_attempts": attempts,
                "sharepoint_error": (message or "")[:2000],
                "sharepoint_state": "error" if give_up else "pending",
            }
        )
        self.document_id._recompute_sharepoint_state_from_files()
        _logger.warning(
            "SharePoint file sync failed file_id=%s document_id=%s attempts=%s give_up=%s error=%s",
            self.id,
            self.document_id.id,
            attempts,
            give_up,
            (message or "")[:200],
        )

    def action_retry_sharepoint(self):
        """Reintento manual desde el formulario (sincrono)."""
        for record in self:
            record.sharepoint_attempts = 0
            record.sharepoint_state = "pending"
            record._sync_to_sharepoint()
        return True

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
