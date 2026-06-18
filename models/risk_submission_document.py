import base64
import logging
from datetime import timedelta
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RiskSubmissionDocument(models.Model):
    _name = "risk.module.document"
    _description = "Documento de solicitud de riesgo"
    _inherit = ["mail.thread"]
    _order = "required desc, party, sequence, id"

    _REJECTION_MESSAGES = {
        "illegible": "El documento cargado no se puede leer con claridad. Por favor vuelve a cargar una imagen o PDF mas nitido, procurando que toda la informacion sea visible.",
        "incomplete": "El documento esta incompleto. Por favor carga todas las paginas o caras requeridas para que podamos continuar con la revision.",
        "missing_back": "Hace falta la parte posterior del documento. Por favor carga nuevamente el archivo incluyendo ambas caras.",
        "expired": "El documento cargado se encuentra vencido. Por favor adjunta una version vigente para continuar con el proceso.",
        "wrong_driver": "El documento cargado no corresponde al conductor registrado en la solicitud. Por favor verifica la informacion y carga el documento correcto.",
        "wrong_owner": "El documento cargado no corresponde al propietario o tenedor registrado. Por favor carga el documento correspondiente a la persona indicada en la solicitud.",
        "wrong_vehicle": "El documento cargado no corresponde al vehiculo registrado en la solicitud. Por favor verifica la placa y adjunta el documento correcto.",
        "wrong_file": "El archivo cargado no corresponde al documento solicitado. Por favor revisa el nombre del documento requerido y vuelve a cargar el archivo correcto.",
        "not_color": "El documento debe estar cargado a color para poder validarlo correctamente. Por favor adjunta una nueva version a color.",
        "photo_requirements": "La foto cargada no cumple con los requisitos solicitados. Por favor adjunta una foto actualizada, clara y donde se vea la informacion requerida.",
        "date_not_visible": "No es posible validar la fecha del documento porque no se ve con claridad. Por favor carga una version donde la fecha sea legible.",
        "cropped": "Parte de la informacion del documento aparece cortada. Por favor vuelve a cargarlo asegurandote de que el documento completo sea visible.",
        "damaged": "No pudimos abrir correctamente el archivo cargado. Por favor intenta subirlo nuevamente en formato PDF, JPG o PNG.",
        "invalid_rut": "El RUT cargado no cumple con las condiciones requeridas. Por favor carga una version donde se observe la marca de agua como copia de certificado o certificado.",
        "old_chamber": "La Camara de Comercio debe tener una fecha de expedicion no mayor a 30 dias. Por favor carga un certificado actualizado.",
    }

    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Documento", required=True)
    document_type = fields.Selection(
        [
            ("driver_id", "Cedula del conductor"),
            ("driver_license", "Licencia de conduccion"),
            ("driver_social_security", "Planilla de seguridad social"),
            ("driver_photo", "Foto del conductor"),
            ("driver_risk_induction", "Induccion y notificacion general de riesgos"),
            ("owner_document", "Cedula / NIT del propietario"),
            ("owner_bank_certificate", "Certificacion bancaria"),
            ("owner_rut", "RUT"),
            ("owner_chamber_commerce", "Camara de comercio"),
            ("owner_legal_representative_id", "Cedula representante legal"),
            ("vehicle_registration", "Tarjeta de propiedad"),
            ("vehicle_photo", "Foto del vehiculo"),
            ("soat", "SOAT"),
            ("technical_inspection", "Revision tecnico-mecanica"),
            ("policy", "Poliza"),
            ("third_party_life_sheet", "Formato FO-RI-01"),
            ("owner_security_study", "Estudio de seguridad del propietario"),
            ("driver_security_study", "Estudio de seguridad del conductor"),
            ("semi_registration", "Documento del semi/remolque"),
            ("semi_photo", "Foto del remolque o semirremolque"),
            ("other", "Otro"),
        ],
        string="Tipo",
        required=True,
        default="other",
    )
    party = fields.Selection(
        [
            ("driver", "Conductor"),
            ("owner", "Propietario"),
            ("vehicle", "Vehiculo"),
            ("semi_trailer", "Semi/Remolque"),
            ("other", "Otro"),
        ],
        string="Relacionado con",
        required=True,
        default="other",
    )
    required = fields.Boolean(string="Obligatorio", default=True)
    source = fields.Selection(
        [
            ("generated", "Generado por catalogo"),
            ("manual", "Adicional manual"),
        ],
        string="Origen",
        default="manual",
        required=True,
        tracking=True,
    )
    validity_required = fields.Boolean(string="Requiere vigencia")
    issue_date_required = fields.Boolean(string="Requiere fecha de expedicion")
    reject_expired = fields.Boolean(string="No aceptar vencidos", default=True)
    max_age_days = fields.Integer(string="Antiguedad maxima en dias")
    max_file_size_mb = fields.Float(string="Tamano maximo MB", default=10.0)
    allowed_file_extensions = fields.Char(
        string="Extensiones permitidas",
        default="pdf,jpg,jpeg,png",
    )
    requires_color = fields.Boolean(string="Debe estar a color")
    requires_both_sides = fields.Boolean(string="Requiere ambas caras")
    instructions = fields.Text(string="Instrucciones")
    file = fields.Binary(string="Archivo", attachment=True)
    filename = fields.Char(string="Nombre de archivo")
    issue_date = fields.Date(string="Fecha de expedicion")
    expiration_date = fields.Date(string="Fecha de vencimiento")
    expiration_state = fields.Selection(
        [
            ("no_date", "Sin fecha"),
            ("valid", "Vigente"),
            ("expiring", "Vence pronto"),
            ("expired", "Vencido"),
        ],
        string="Vigencia",
        compute="_compute_expiration_state",
    )
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("received", "Recibido"),
            ("approved", "Aprobado"),
            ("rejected", "Rechazado"),
        ],
        string="Estado",
        default="pending",
        required=True,
        tracking=True,
    )
    rejection_reason = fields.Selection(
        [
            ("illegible", "Documento ilegible"),
            ("incomplete", "Documento incompleto"),
            ("missing_back", "Falta reverso"),
            ("expired", "Documento vencido"),
            ("wrong_driver", "No corresponde al conductor"),
            ("wrong_owner", "No corresponde al propietario"),
            ("wrong_vehicle", "No corresponde al vehiculo"),
            ("wrong_file", "Archivo equivocado"),
            ("not_color", "Debe estar a color"),
            ("photo_requirements", "Foto no cumple requisitos"),
            ("date_not_visible", "Fecha no visible"),
            ("cropped", "Informacion cortada"),
            ("damaged", "Archivo danado"),
            ("invalid_rut", "RUT no valido"),
            ("old_chamber", "Camara de Comercio vencida"),
        ],
        string="Motivo de rechazo",
    )
    observations = fields.Text(string="Observaciones")
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
    approved_by_id = fields.Many2one(
        "res.users",
        string="Aprobado por",
        readonly=True,
        copy=False,
    )
    approved_at = fields.Datetime(
        string="Fecha de aprobacion",
        readonly=True,
        copy=False,
    )
    rejected_by_id = fields.Many2one(
        "res.users",
        string="Rechazado por",
        readonly=True,
        copy=False,
    )
    rejected_at = fields.Datetime(
        string="Fecha de rechazo",
        readonly=True,
        copy=False,
    )
    rejection_message_sent_at = fields.Datetime(
        string="Mensaje de rechazo enviado",
        readonly=True,
        copy=False,
    )
    replacement_count = fields.Integer(
        string="Veces reemplazado",
        readonly=True,
        copy=False,
    )
    has_file = fields.Boolean(
        string="Tiene archivo",
        compute="_compute_has_file",
        store=True,
        help="Verdadero si el documento tiene archivo en Odoo o ya esta en SharePoint.",
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
        tracking=True,
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
    version_ids = fields.One2many(
        "risk.module.document.version",
        "document_id",
        string="Historial de cargas",
        readonly=True,
    )

    @api.depends("file", "sharepoint_item_id")
    def _compute_has_file(self):
        for record in self:
            record.has_file = bool(record.file) or bool(record.sharepoint_item_id)

    @api.depends("expiration_date")
    def _compute_expiration_state(self):
        """
        Compute the expiration state of the document based on its expiration date.
        Sets state to 'no_date', 'expired', 'expiring', or 'valid'.
        """
        today = fields.Date.context_today(self)
        soon_limit = today + timedelta(days=30)
        for record in self:
            if not record.expiration_date:
                record.expiration_state = "no_date"
            elif record.expiration_date < today:
                record.expiration_state = "expired"
            elif record.expiration_date <= soon_limit:
                record.expiration_state = "expiring"
            else:
                record.expiration_state = "valid"

    @api.onchange("file")
    def _onchange_file(self):
        # Al cargar (o reemplazar tras un rechazo) el documento vuelve a revision.
        if self.file and self.state in ("pending", "rejected"):
            _logger.debug(
                "Document onchange marked received document_id=%s", self.id or "new"
            )
            self.state = "received"

    @api.onchange("rejection_reason")
    def _onchange_rejection_reason(self):
        for record in self:
            message = record._rejection_reason_message(record.rejection_reason)
            if message:
                record.observations = message

    def _rejection_reason_message(self, reason):
        """
        Get the rejection message for a given reason using risk.message.template.
        
        Args:
            reason (str): The rejection reason code.
            
        Returns:
            str: The fully formatted rejection message.
        """
        default = self._REJECTION_MESSAGES.get(reason or "")
        return self.env["risk.message.template"]._get_body(
            "document_rejection",
            reason,
            default=default,
        )

    def _allowed_file_extension_set(self):
        self.ensure_one()
        values = []
        for extension in (self.allowed_file_extensions or "").split(","):
            extension = extension.strip().lower()
            if not extension:
                continue
            if not extension.startswith("."):
                extension = ".%s" % extension
            values.append(extension)
        return set(values)

    # Material Symbols icon shown for each document in the portal detail view.
    # Mapped by document_type with a fallback by party so no schema change is
    # needed; keep in sync with the document_type / party selections above.
    _PORTAL_ICONS_BY_TYPE = {
        "driver_id": "badge",
        "driver_license": "description",
        "driver_social_security": "assignment_ind",
        "driver_photo": "photo_camera",
        "driver_risk_induction": "health_and_safety",
        "owner_document": "badge",
        "owner_bank_certificate": "account_balance",
        "owner_rut": "article",
        "owner_chamber_commerce": "description",
        "owner_legal_representative_id": "badge",
        "vehicle_registration": "directions_car",
        "vehicle_photo": "photo_camera",
        "soat": "verified_user",
        "technical_inspection": "build",
        "policy": "policy",
        "third_party_life_sheet": "assignment",
        "owner_security_study": "security",
        "driver_security_study": "security",
        "semi_registration": "rv_hookup",
        "semi_photo": "photo_camera",
        "other": "description",
    }
    _PORTAL_ICONS_BY_PARTY = {
        "driver": "person",
        "owner": "business_center",
        "vehicle": "local_shipping",
        "semi_trailer": "rv_hookup",
        "other": "description",
    }

    def _portal_material_icon(self):
        """Material Symbols icon name for this document in the portal view."""
        self.ensure_one()
        icon = self._PORTAL_ICONS_BY_TYPE.get(self.document_type)
        if not icon:
            icon = self._PORTAL_ICONS_BY_PARTY.get(self.party, "description")
        return icon

    @api.constrains("state", "observations")
    def _check_rejection_observations(self):
        for record in self:
            if record.state == "rejected" and not (record.observations or "").strip():
                _logger.warning(
                    "Document rejection blocked missing observations document_id=%s",
                    record.id,
                )
                raise ValidationError(
                    "Debes indicar observaciones para rechazar un documento."
                )

    @api.constrains("state", "file", "sharepoint_item_id")
    def _check_approved_file(self):
        for record in self:
            if record.state == "approved" and not record.has_file:
                _logger.warning(
                    "Document approval blocked missing file document_id=%s", record.id
                )
                raise ValidationError(
                    "No puedes aprobar un documento sin archivo adjunto."
                )
            if (
                record.state == "approved"
                and record.validity_required
                and not record.expiration_date
            ):
                raise ValidationError(
                    "Debes indicar la fecha de vencimiento para aprobar %s."
                    % record.name
                )
            if (
                record.state == "approved"
                and record.reject_expired
                and record.expiration_state == "expired"
            ):
                raise ValidationError(
                    "No puedes aprobar %s porque esta vencido." % record.name
                )
            if record.state == "approved" and (
                record.issue_date_required or record.max_age_days
            ):
                if not record.issue_date:
                    raise ValidationError(
                        "Debes indicar la fecha de expedicion para aprobar %s."
                        % record.name
                    )
            if record.state == "approved" and record.max_age_days:
                limit_date = fields.Date.context_today(record) - timedelta(
                    days=record.max_age_days
                )
                if record.issue_date < limit_date:
                    raise ValidationError(
                        "No puedes aprobar %s porque supera la antiguedad maxima de %s dias."
                        % (record.name, record.max_age_days)
                    )

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info(
            "Creating risk documents count=%s user_id=%s",
            len(vals_list),
            self.env.user.id,
        )
        for vals in vals_list:
            if vals.get("file") and vals.get("state", "pending") == "pending":
                vals["state"] = "received"
            if vals.get("file"):
                vals.setdefault("uploaded_by_id", self.env.user.id)
                vals.setdefault("uploaded_at", fields.Datetime.now())
        records = super().create(vals_list)
        for record in records:
            _logger.info(
                "Risk document created document_id=%s submission_id=%s type=%s state=%s required=%s",
                record.id,
                record.submission_id.id,
                record.document_type,
                record.state,
                record.required,
            )
        if self._sp_sync_enabled():
            for record in records.filtered("file"):
                record.sharepoint_state = "pending"
                record._sp_create_version(is_replacement=False)
        completed_submissions = records.mapped("submission_id").filtered(
            lambda submission: (
                submission.state == "documents_requested"
                and submission._all_required_documents_uploaded()
            )
        )
        if completed_submissions:
            completed_submissions.action_mark_documents_sent_if_complete()
        return records

    def write(self, vals):
        pending_records = self.env["risk.module.document"]
        if vals.get("file") and not vals.get("state"):
            # Cargar o reemplazar (incluso tras un rechazo) devuelve a revision.
            pending_records = self.filtered(
                lambda record: record.state in ("pending", "rejected")
            )
        old_states = {record.id: record.state for record in self}
        old_file_presence = {record.id: bool(record.file) for record in self}
        old_rejection = {record.id: record.rejection_reason for record in self}
        sp_sync_enabled = self._sp_sync_enabled()
        _logger.debug(
            "Writing risk documents ids=%s fields=%s user_id=%s",
            self.ids,
            sorted(vals.keys()),
            self.env.user.id,
        )
        result = super().write(vals)
        if pending_records:
            super(RiskSubmissionDocument, pending_records).write({"state": "received"})
            _logger.info(
                "Risk documents auto-marked received document_ids=%s",
                pending_records.ids,
            )
        audit_updates = {}
        if vals.get("file"):
            audit_updates.update(
                {
                    "uploaded_by_id": self.env.user.id,
                    "uploaded_at": fields.Datetime.now(),
                }
            )
        if vals.get("state") == "approved":
            audit_updates.update(
                {
                    "approved_by_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                    "rejected_by_id": False,
                    "rejected_at": False,
                    "rejection_message_sent_at": False,
                }
            )
        elif vals.get("state") == "rejected":
            audit_updates.update(
                {
                    "rejected_by_id": self.env.user.id,
                    "rejected_at": fields.Datetime.now(),
                    "approved_by_id": False,
                    "approved_at": False,
                }
            )
        if audit_updates:
            for record in self:
                record_updates = dict(audit_updates)
                # En modo solo-SharePoint el archivo local se purga tras subir,
                # asi que un item ya sincronizado tambien cuenta como reemplazo.
                is_replacement = bool(old_file_presence.get(record.id)) or bool(
                    record.sharepoint_item_id
                )
                if vals.get("file") and is_replacement:
                    record_updates["replacement_count"] = record.replacement_count + 1
                if vals.get("file") and old_states.get(record.id) == "rejected":
                    record_updates.update(
                        {
                            "rejection_reason": False,
                            "rejection_message_sent_at": False,
                        }
                    )
                if vals.get("file") and sp_sync_enabled:
                    record_updates.update(
                        {
                            "sharepoint_state": "pending",
                            "sharepoint_error": False,
                            "sharepoint_attempts": 0,
                        }
                    )
                super(RiskSubmissionDocument, record).write(record_updates)
                if vals.get("file"):
                    action = "reemplazado" if is_replacement else "cargado"
                    record.message_post(
                        body="Documento %s: %s" % (action, record.name),
                    )
                    if sp_sync_enabled:
                        triggered = (
                            old_rejection.get(record.id)
                            if old_states.get(record.id) == "rejected"
                            else False
                        )
                        record._sp_create_version(
                            is_replacement=is_replacement,
                            triggered_by_rejection=triggered,
                        )
        if "state" in vals:
            for record in self:
                _logger.info(
                    "Risk document state changed document_id=%s submission_id=%s old_state=%s new_state=%s user_id=%s",
                    record.id,
                    record.submission_id.id,
                    old_states.get(record.id),
                    record.state,
                    self.env.user.id,
                )
        completed_submissions = self.mapped("submission_id").filtered(
            lambda submission: (
                submission.state == "documents_requested"
                and submission._all_required_documents_uploaded()
            )
        )
        if completed_submissions:
            completed_submissions.action_mark_documents_sent_if_complete()
        return result

    # ------------------------------------------------------------------
    # Sincronizacion con SharePoint (modo solo-referencia, outbox/cron)
    # ------------------------------------------------------------------
    def _sp_sync_enabled(self):
        """Atajo: indica si la integracion con SharePoint esta activa."""
        return self.env["risk.sharepoint.service"]._is_enabled()

    def _sp_folder_segments(self):
        """Ruta de carpetas en SharePoint para este documento."""
        self.ensure_one()
        cfg = self.env["risk.sharepoint.service"]._config()
        submission = self.submission_id
        ref = submission.name or ("Solicitud-%s" % submission.id)
        plate = submission.vehicle_plate or ""
        sub_folder = ("%s %s" % (ref, plate)).strip()
        party_label = dict(self._fields["party"].selection).get(
            self.party, self.party or "otro"
        )
        return [cfg["root_folder"], sub_folder, party_label]

    def _sp_create_version(self, is_replacement=False, triggered_by_rejection=False):
        """Registra un intento de carga en el historial (estado 'pending')."""
        self.ensure_one()
        return self.env["risk.module.document.version"].sudo().create(
            {
                "document_id": self.id,
                "document_name": self.name,
                "filename": self.filename,
                "version_number": self.replacement_count + 1,
                "result": "pending",
                "is_replacement": is_replacement,
                "triggered_by_rejection": triggered_by_rejection or False,
                "uploaded_by_id": self.env.user.id,
                "uploaded_at": fields.Datetime.now(),
            }
        )

    def _sp_finalize_version(self, result, store_result=None, error_message=None):
        """Cierra la ultima version 'pending' del documento con el resultado."""
        self.ensure_one()
        Version = self.env["risk.module.document.version"].sudo()
        version = Version.search(
            [("document_id", "=", self.id), ("result", "=", "pending")],
            order="create_date desc, id desc",
            limit=1,
        )
        if not version:
            version = self._sp_create_version()
        vals = {"result": result}
        if store_result:
            vals.update(
                {
                    "sharepoint_item_id": store_result.get("item_id"),
                    "sharepoint_web_url": store_result.get("web_url"),
                }
            )
        if error_message:
            vals["error_message"] = (error_message or "")[:2000]
        version.write(vals)

    def _sync_to_sharepoint(self):
        """Sube el archivo del documento a SharePoint (lo invoca el cron).

        Si ya existe ``sharepoint_item_id`` sube una nueva version del mismo
        item (reenvio tras rechazo); si no, crea el archivo. Tras subir, purga
        la copia local si la configuracion lo indica.
        """
        self.ensure_one()
        service = self.env["risk.sharepoint.service"]
        cfg = service._config()
        if not self.file:
            # Nada que subir: o ya esta en SharePoint o no hay archivo.
            if self.sharepoint_item_id:
                self.sharepoint_state = "synced"
            return
        content = base64.b64decode(self.file)
        try:
            result = service._store_file(
                self._sp_folder_segments(),
                self.filename or self.name or "documento",
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
        self._sp_finalize_version("uploaded", store_result=result)
        _logger.info(
            "SharePoint sync ok document_id=%s item_id=%s purged=%s",
            self.id,
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
        _logger.warning(
            "SharePoint sync failed document_id=%s attempts=%s give_up=%s error=%s",
            self.id,
            attempts,
            give_up,
            (message or "")[:200],
        )
        if give_up:
            self._sp_finalize_version("failed", error_message=message)
            self.message_post(
                body="Error al sincronizar con SharePoint tras %s intentos: %s"
                % (attempts, message)
            )

    @api.model
    def _cron_sync_sharepoint(self, limit=50):
        """Outbox: sube los documentos pendientes/erroneos a SharePoint."""
        service = self.env["risk.sharepoint.service"]
        if not service._is_enabled():
            return
        cfg = service._config()
        docs = self.search(
            [
                ("sharepoint_state", "in", ("pending", "error")),
                ("sharepoint_attempts", "<", cfg["max_attempts"]),
                ("file", "!=", False),
            ],
            limit=limit,
        )
        _logger.info("SharePoint cron processing count=%s", len(docs))
        for doc in docs:
            try:
                with self.env.cr.savepoint():
                    doc._sync_to_sharepoint()
            except Exception:  # noqa: BLE001 - aislar fallos por documento
                _logger.exception(
                    "SharePoint cron unexpected error document_id=%s", doc.id
                )

    def action_retry_sharepoint(self):
        """Reintento manual desde el formulario (sincrono)."""
        for record in self:
            record.sharepoint_attempts = 0
            record.sharepoint_state = "pending"
            record._sync_to_sharepoint()
        return True

    def action_mark_received(self):
        """
        Mark selected documents as received.
        """
        _logger.info(
            "Marking risk documents received document_ids=%s user_id=%s",
            self.ids,
            self.env.user.id,
        )
        self.write({"state": "received"})

    def action_open_document_preview(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Ver documento",
            "res_model": "risk.module.document",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "risk_module.view_risk_module_document_form"
            ).id,
            "target": "new",
        }

    def action_open_file(self):
        self.ensure_one()
        # Si ya esta sincronizado, abrimos el archivo en SharePoint. Mientras
        # sigue pendiente/erroneo servimos la copia local (que es la version
        # vigente; la de SharePoint aun seria la anterior).
        if self.sharepoint_state == "synced" and self.sharepoint_web_url:
            return {
                "type": "ir.actions.act_url",
                "url": self.sharepoint_web_url,
                "target": "new",
            }
        if not self.file:
            raise ValidationError("Este documento no tiene archivo cargado.")
        filename = quote(self.filename or self.name or "documento")
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/risk.module.document/%s/file/%s?download=false"
            % (self.id, filename),
            "target": "new",
        }

    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Rechazar documento",
            "res_model": "risk.module.document.reject.wizard",
            "view_mode": "form",
            "view_id": self.env.ref(
                "risk_module.view_risk_document_reject_wizard_form"
            ).id,
            "target": "new",
            "context": {
                "default_document_id": self.id,
                "active_model": self._name,
                "active_id": self.id,
            },
        }

    def action_approve(self):
        """
        Approve the document if it has an attached file.
        Raises ValidationError if conditions for approval are not met.
        """
        for record in self:
            if not record.has_file:
                _logger.warning(
                    "Document approval action blocked missing file document_id=%s",
                    record.id,
                )
                raise ValidationError(
                    "No puedes aprobar un documento sin archivo adjunto."
                )
        _logger.info(
            "Approving risk documents document_ids=%s user_id=%s",
            self.ids,
            self.env.user.id,
        )
        self.write({"state": "approved"})
        for record in self:
            record.message_post(
                body="Documento aprobado: %s" % record.name,
            )
            if record.submission_id:
                record.submission_id.message_post(
                    body="Documento aprobado: %s" % record.name,
                )

    def action_reject(self):
        return self.action_open_reject_wizard()

    def action_confirm_rejection(self):
        for record in self:
            if not (record.observations or "").strip() and record.rejection_reason:
                record.observations = record._rejection_reason_message(
                    record.rejection_reason
                )
            if not (record.observations or "").strip():
                _logger.warning(
                    "Document rejection action blocked missing observations document_id=%s",
                    record.id,
                )
                raise ValidationError(
                    "Debes indicar observaciones para rechazar un documento."
                )
        _logger.info(
            "Rejecting risk documents document_ids=%s user_id=%s",
            self.ids,
            self.env.user.id,
        )
        self.write({"state": "rejected"})
        for record in self:
            body = "Documento rechazado: %s. Observaciones: %s" % (
                record.name,
                (record.observations or "").strip(),
            )
            record.message_post(body=body)
            if record.submission_id:
                record.submission_id.message_post(body=body)
                record.submission_id.action_send_document_rejected_email(record)
            record.write({"rejection_message_sent_at": fields.Datetime.now()})
