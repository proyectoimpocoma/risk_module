import logging
import uuid
import odoo
from odoo.orm.registry import Registry
from odoo import api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SIGNATURE_CODE_TTL_MINUTES = 15
SIGNATURE_CODE_RESEND_SECONDS = 60
SIGNATURE_CODE_MAX_ATTEMPTS = 5


class RiskSubmission(models.Model):
    _name = "risk.module"
    _description = "Solicitud de habilitacion de terceros"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "vehicle_plate"
    _order = "create_date desc"

    _ACTIVE_SUBMISSION_STATES = (
        "draft",
        "submitted",
        "risk_review",
        "external_validation_pending",
        "manual_approval_pending",
        "documents_requested",
        "documents_review",
        "correction_required",
        "correction_submitted",
    )

    _FORM_LOCKED_FIELDS = frozenset(
        {
            "form_date",
            "vehicle_plate",
            "semi_trailer_plate",
            "satellite_company",
            "satellite_url",
            "satellite_user",
            "satellite_password",
            "owner_name",
            "owner_document_type",
            "owner_document_number",
            "owner_address",
            "owner_neighborhood",
            "owner_city",
            "owner_phone",
            "owner_email",
            "advance_payment_to",
            "same_owner_on_license",
            "registered_owner_document_type",
            "registered_owner_document_number",
            "registered_owner_name",
            "registered_owner_phone",
            "driver_name",
            "driver_document_number",
            "driver_address",
            "driver_neighborhood",
            "driver_city",
            "driver_phone",
            "driver_optional_phone",
            "driver_email",
            "driver_is_fit",
            "driver_is_trained",
            "family_reference_name",
            "family_reference_relationship",
            "family_reference_phone",
            "cargo_reference_name",
            "cargo_reference_phone",
            "banking_info_accepted",
            "compensation_accepted",
            "personal_data_accepted",
            "terms_accepted_at",
            "owner_has_valid_study",
            "single_owner_driver_signature",
            "owner_signature",
            "owner_signature_document",
            "owner_signed_at",
            "owner_signature_ip",
            "owner_signature_user_agent",
            "driver_has_valid_study",
            "driver_signature",
            "driver_signature_document",
            "driver_signed_at",
            "driver_signature_ip",
            "driver_signature_user_agent",
            "message",
        }
    )

    name = fields.Char(string="Referencia")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("submitted", "Enviado"),
            ("risk_review", "En revision de riesgo"),
            ("external_validation_pending", "Validacion externa pendiente"),
            ("manual_approval_pending", "Pendiente aprobacion manual"),
            ("documents_requested", "Documentos solicitados"),
            ("documents_review", "Documentos en revision"),
            ("correction_required", "Requiere correccion"),
            ("correction_submitted", "Correccion enviada"),
            ("approved", "Aprobado"),
            ("rejected", "Rechazado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )
    access_token = fields.Char(
        string="Token publico", default=lambda self: uuid.uuid4().hex, copy=False
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Tercero portal",
        index=True,
        copy=False,
        tracking=True,
    )
    portal_user_id = fields.Many2one(
        "res.users",
        string="Usuario portal",
        index=True,
        copy=False,
        tracking=True,
    )
    submitted_by_id = fields.Many2one(
        "res.users",
        string="Enviado por",
        index=True,
        copy=False,
        tracking=True,
    )
    submission_email_sent_at = fields.Datetime(
        string="Correo de confirmacion enviado",
        readonly=True,
        copy=False,
    )
    submission_email_sent_to = fields.Char(
        string="Correo de confirmacion destinatario",
        readonly=True,
        copy=False,
    )
    submission_email_status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("sent", "Enviado"),
            ("failed", "Fallido"),
            ("skipped", "Omitido"),
        ],
        string="Estado correo de confirmacion",
        readonly=True,
        copy=False,
    )
    portal_state_label = fields.Char(
        string="Estado portal",
        compute="_compute_portal_state_label",
    )
    form_date = fields.Date(string="Fecha", default=fields.Date.context_today)
    vehicle_plate = fields.Char(string="Placa", required=True, tracking=True)
    semi_trailer_plate = fields.Char(string="Semi/Remolque", tracking=True)
    satellite_company = fields.Char(string="Empresa satelital", tracking=True)
    satellite_url = fields.Char(string="URL empresa satelital", tracking=True)
    satellite_user = fields.Char(string="Usuario satelital", tracking=True)
    satellite_password = fields.Char(string="Clave satelital")
    owner_name = fields.Char(string="Nombres y apellidos / Empresa", tracking=True)
    owner_document_type = fields.Selection(
        [
            ("cc", "CC"),
            ("nit", "Nit"),
        ],
        string="Tipo de documento",
        tracking=True,
    )
    owner_document_number = fields.Char(string="Numero de documento", tracking=True)
    owner_address = fields.Char(string="Direccion", tracking=True)
    owner_neighborhood = fields.Char(string="Barrio", tracking=True)
    owner_city = fields.Char(string="Ciudad", tracking=True)
    owner_phone = fields.Char(string="Celular notificaciones", tracking=True)
    owner_email = fields.Char(string="Correo facturacion y notificaciones", tracking=True)
    advance_payment_to = fields.Selection(
        [
            ("driver", "Conductor"),
            ("owner", "Propietario"),
        ],
        string="Entrega y pago de anticipos a",
        tracking=True,
    )
    same_owner_on_license = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Corresponde al propietario en licencia",
        tracking=True,
    )
    registered_owner_document_type = fields.Selection(
        [
            ("cc", "CC"),
            ("nit", "Nit"),
        ],
        string="Tipo documento propietario",
        tracking=True,
    )
    registered_owner_document_number = fields.Char(
        string="Numero documento propietario",
        tracking=True,
    )
    registered_owner_name = fields.Char(string="Nombres y apellidos propietario", tracking=True)
    registered_owner_phone = fields.Char(string="Celular propietario", tracking=True)
    driver_name = fields.Char(string="Nombres y apellidos conductor", tracking=True)
    driver_document_number = fields.Char(string="Numero de cedula conductor", tracking=True)
    driver_address = fields.Char(string="Direccion conductor", tracking=True)
    driver_neighborhood = fields.Char(string="Barrio conductor", tracking=True)
    driver_city = fields.Char(string="Ciudad conductor", tracking=True)
    driver_phone = fields.Char(string="Celular conductor", tracking=True)
    driver_optional_phone = fields.Char(string="Telefono opcional conductor", tracking=True)
    driver_email = fields.Char(string="Correo autorizacion conductor", tracking=True)
    driver_is_fit = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Apto fisica, mental y psicotecnicamente",
        tracking=True,
    )
    driver_is_trained = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Capacitado y entrenado",
        tracking=True,
    )
    family_reference_name = fields.Char(string="Referencia familiar", tracking=True)
    family_reference_relationship = fields.Char(string="Parentesco referencia familiar", tracking=True)
    family_reference_phone = fields.Char(string="Celular referencia familiar", tracking=True)
    cargo_reference_name = fields.Char(string="Referencia transporte de carga", tracking=True)
    cargo_reference_phone = fields.Char(string="Celular referencia transporte de carga", tracking=True)
    banking_info_accepted = fields.Boolean(string="Acepto informacion bancaria")
    compensation_accepted = fields.Boolean(string="Acepto compensacion general")
    personal_data_accepted = fields.Boolean(
        string="Acepto tratamiento de datos personales"
    )
    terms_accepted_at = fields.Datetime(string="Fecha aceptacion terminos")
    owner_has_valid_study = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Propietario con estudio vigente",
    )
    single_owner_driver_signature = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Propietario y conductor son la misma persona",
        default="no",
    )
    owner_signature = fields.Binary(string="Firma propietario")
    owner_signature_document = fields.Char(string="Cedula firma propietario")
    owner_signed_at = fields.Datetime(string="Fecha firma propietario")
    owner_signature_ip = fields.Char(string="IP firma propietario")
    owner_signature_user_agent = fields.Text(string="Navegador firma propietario")
    owner_signature_email = fields.Char(
        string="Correo verificado propietario", readonly=True, copy=False
    )
    owner_signature_code_hash = fields.Char(
        string="Hash codigo propietario", readonly=True, copy=False
    )
    owner_signature_code_sent_at = fields.Datetime(
        string="Codigo propietario enviado", readonly=True, copy=False
    )
    owner_signature_code_expires_at = fields.Datetime(
        string="Codigo propietario vence", readonly=True, copy=False
    )
    owner_signature_verified_at = fields.Datetime(
        string="Correo propietario verificado", readonly=True, copy=False
    )
    owner_signature_verified_ip = fields.Char(
        string="IP verificacion propietario", readonly=True, copy=False
    )
    owner_signature_code_attempts = fields.Integer(
        string="Intentos codigo propietario", readonly=True, copy=False
    )
    owner_signature_verification_state = fields.Selection(
        [
            ("not_sent", "No enviado"),
            ("sent", "Enviado"),
            ("verified", "Verificado"),
            ("expired", "Vencido"),
            ("blocked", "Bloqueado"),
        ],
        string="Estado verificacion propietario",
        default="not_sent",
        readonly=True,
        copy=False,
    )
    driver_has_valid_study = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Conductor con estudio vigente",
    )
    driver_signature = fields.Binary(string="Firma conductor")
    driver_signature_document = fields.Char(string="Cedula firma conductor")
    driver_signed_at = fields.Datetime(string="Fecha firma conductor")
    driver_signature_ip = fields.Char(string="IP firma conductor")
    driver_signature_user_agent = fields.Text(string="Navegador firma conductor")
    driver_signature_email = fields.Char(
        string="Correo verificado conductor", readonly=True, copy=False
    )
    driver_signature_code_hash = fields.Char(
        string="Hash codigo conductor", readonly=True, copy=False
    )
    driver_signature_code_sent_at = fields.Datetime(
        string="Codigo conductor enviado", readonly=True, copy=False
    )
    driver_signature_code_expires_at = fields.Datetime(
        string="Codigo conductor vence", readonly=True, copy=False
    )
    driver_signature_verified_at = fields.Datetime(
        string="Correo conductor verificado", readonly=True, copy=False
    )
    driver_signature_verified_ip = fields.Char(
        string="IP verificacion conductor", readonly=True, copy=False
    )
    driver_signature_code_attempts = fields.Integer(
        string="Intentos codigo conductor", readonly=True, copy=False
    )
    driver_signature_verification_state = fields.Selection(
        [
            ("not_sent", "No enviado"),
            ("sent", "Enviado"),
            ("verified", "Verificado"),
            ("expired", "Vencido"),
            ("blocked", "Bloqueado"),
        ],
        string="Estado verificacion conductor",
        default="not_sent",
        readonly=True,
        copy=False,
    )
    message = fields.Text(string="Observaciones")
    risk_reviewer_id = fields.Many2one(
        "res.users",
        string="Revisor de riesgo",
        readonly=True,
        copy=False,
        tracking=True,
    )
    risk_reviewed_at = fields.Datetime(
        string="Fecha revision de riesgo",
        readonly=True,
        copy=False,
        tracking=True,
    )
    approval_user_id = fields.Many2one(
        "res.users",
        string="Aprobado por",
        readonly=True,
        copy=False,
        tracking=True,
    )
    approval_date = fields.Datetime(
        string="Fecha aprobacion",
        readonly=True,
        copy=False,
        tracking=True,
    )
    approval_note = fields.Text(
        string="Comentario de aprobacion", readonly=True, copy=False
    )
    rejection_user_id = fields.Many2one(
        "res.users",
        string="Rechazado por",
        readonly=True,
        copy=False,
        tracking=True,
    )
    rejection_date = fields.Datetime(
        string="Fecha rechazo",
        readonly=True,
        copy=False,
        tracking=True,
    )
    rejection_reason = fields.Text(
        string="Motivo de rechazo", readonly=True, copy=False
    )
    correction_reason = fields.Text(
        string="Motivo de correccion",
        readonly=True,
        copy=False,
        tracking=True,
    )
    correction_requested_by_id = fields.Many2one(
        "res.users",
        string="Correccion solicitada por",
        readonly=True,
        copy=False,
        tracking=True,
    )
    correction_requested_at = fields.Datetime(
        string="Fecha solicitud correccion",
        readonly=True,
        copy=False,
        tracking=True,
    )
    correction_submitted_at = fields.Datetime(
        string="Fecha envio correccion",
        readonly=True,
        copy=False,
        tracking=True,
    )
    correction_count = fields.Integer(
        string="Veces devuelta",
        readonly=True,
        copy=False,
    )
    correction_section_vehicle = fields.Boolean(
        string="Corregir vehiculo",
        readonly=True,
        copy=False,
    )
    correction_section_owner = fields.Boolean(
        string="Corregir propietario",
        readonly=True,
        copy=False,
    )
    correction_section_driver = fields.Boolean(
        string="Corregir conductor",
        readonly=True,
        copy=False,
    )
    correction_section_satellite = fields.Boolean(
        string="Corregir satelital",
        readonly=True,
        copy=False,
    )
    correction_section_signatures = fields.Boolean(
        string="Corregir firmas",
        readonly=True,
        copy=False,
    )
    correction_section_terms = fields.Boolean(
        string="Corregir terminos",
        readonly=True,
        copy=False,
    )
    correction_section_other = fields.Boolean(
        string="Otra correccion",
        readonly=True,
        copy=False,
    )
    document_ids = fields.One2many(
        "risk.module.document",
        "submission_id",
        string="Documentos",
        copy=False,
    )
    document_required_count = fields.Integer(
        string="Requeridos",
        compute="_compute_document_summary",
    )
    document_pending_count = fields.Integer(
        string="Pendientes",
        compute="_compute_document_summary",
    )
    document_received_count = fields.Integer(
        string="Recibidos",
        compute="_compute_document_summary",
    )
    document_approved_count = fields.Integer(
        string="Aprobados",
        compute="_compute_document_summary",
    )
    document_rejected_count = fields.Integer(
        string="Rechazados",
        compute="_compute_document_summary",
    )
    document_progress_label = fields.Char(
        string="Progreso documental",
        compute="_compute_document_summary",
    )
    next_action_label = fields.Char(
        string="Siguiente accion",
        compute="_compute_next_action_label",
    )
    external_validation_ids = fields.One2many(
        "risk.external.validation",
        "submission_id",
        string="Validaciones externas",
        copy=False,
    )
    warning_ids = fields.One2many(
        "risk.warning",
        "submission_id",
        string="Advertencias de riesgo",
        copy=False,
    )
    warning_count = fields.Integer(
        string="Advertencias",
        compute="_compute_warning_summary",
        store=True,
    )
    critical_warning_count = fields.Integer(
        string="Criticas",
        compute="_compute_warning_summary",
        store=True,
    )
    new_critical_warning_count = fields.Integer(
        string="Criticas sin revisar",
        compute="_compute_warning_summary",
        store=True,
    )

    def _is_risk_analyst_without_leader_rights(self):
        """
        Check if the current user is a risk analyst without manager rights.

        Returns:
            bool: True if user is analyst but not manager, False otherwise.
        """
        if self.env.su or self.env.context.get("skip_risk_form_lock"):
            return False
        user = self.env.user
        return (
            user.id != SUPERUSER_ID
            and user.has_group("risk_module.group_risk_user")
            and not user.has_group("risk_module.group_risk_manager")
        )

    def _check_form_locked_fields_for_risk_analyst(self, vals):
        """
        Prevent risk analysts from modifying locked form fields.

        Args:
            vals (dict): Dictionary of values being written.
            
        Raises:
            UserError: If the user attempts to modify locked fields.
        """
        if self._is_risk_analyst_without_leader_rights():
            locked_fields = self._FORM_LOCKED_FIELDS.intersection(vals)
            if locked_fields:
                labels = [
                    self._fields[field].string
                    for field in sorted(locked_fields)
                    if field in self._fields
                ]
                raise UserError(
                    "El Analista de Riesgo puede gestionar el flujo, pero no puede modificar datos registrados en el formulario: %s."
                    % ", ".join(labels)
                )

    @api.depends("document_ids.state", "document_ids.required")
    def _compute_document_summary(self):
        """
        Compute summary counts for the requested documents.
        Calculates total required, pending, received, approved, and rejected.
        """
        for record in self:
            required_documents = record.document_ids.filtered("required")
            record.document_required_count = len(required_documents)
            record.document_pending_count = len(
                required_documents.filtered(lambda doc: doc.state == "pending")
            )
            record.document_received_count = len(
                required_documents.filtered(lambda doc: doc.state == "received")
            )
            record.document_approved_count = len(
                required_documents.filtered(lambda doc: doc.state == "approved")
            )
            record.document_rejected_count = len(
                required_documents.filtered(lambda doc: doc.state == "rejected")
            )
            record.document_progress_label = "%s / %s aprobados" % (
                record.document_approved_count,
                record.document_required_count,
            )

    @api.depends("warning_ids.state", "warning_ids.severity")
    def _compute_warning_summary(self):
        for record in self:
            warnings = record.warning_ids.filtered(
                lambda item: item.state in ("new", "reviewed", "confirmed")
            )
            critical = warnings.filtered(lambda item: item.severity == "critical")
            record.warning_count = len(warnings)
            record.critical_warning_count = len(critical)
            record.new_critical_warning_count = len(
                critical.filtered(lambda item: item.state == "new")
            )

    @api.depends(
        "state",
        "document_pending_count",
        "document_received_count",
        "document_rejected_count",
    )
    def _compute_next_action_label(self):
        """Show the next operational action for the risk work queue."""
        default_actions = {
            "draft": "Completar formulario",
            "submitted": "Iniciar revision",
            "risk_review": "Revisar datos y definir siguiente paso",
            "external_validation_pending": "Gestionar validacion externa",
            "manual_approval_pending": "Solicitar documentos, corregir o aprobar",
            "documents_requested": "Esperar carga de documentos",
            "documents_review": "Revisar documentos recibidos",
            "correction_required": "Esperar correccion del tercero",
            "correction_submitted": "Revisar correcciones",
            "approved": "Proceso finalizado",
            "rejected": "Proceso rechazado",
        }
        for record in self:
            if record.state == "documents_requested" and record.document_pending_count:
                record.next_action_label = "%s documentos pendientes por cargar" % (
                    record.document_pending_count
                )
            elif record.state == "documents_review" and record.document_received_count:
                record.next_action_label = "%s documentos recibidos por revisar" % (
                    record.document_received_count
                )
            elif record.state == "documents_review" and record.document_rejected_count:
                record.next_action_label = "Esperar reemplazo de documentos rechazados"
            else:
                record.next_action_label = default_actions.get(
                    record.state,
                    "Revisar solicitud",
                )

    @api.depends("state")
    def _compute_portal_state_label(self):
        """Compute the portal_state_label field from the current state.

        This label is used in the portal to present a simplified submission status.
        """
        labels = {
            "draft": "Pendiente por completar",
            "submitted": "Enviado",
            "risk_review": "En revision",
            "external_validation_pending": "En revision",
            "manual_approval_pending": "En revision",
            "documents_requested": "Documentos solicitados",
            "documents_review": "Documentos enviados",
            "correction_required": "Requiere correccion",
            "correction_submitted": "Correccion enviada",
            "approved": "Aprobada",
            "rejected": "Rechazada",
        }
        for record in self:
            record.portal_state_label = labels.get(record.state, "En revision")

    def _portal_document_upload_allowed(self, document, user=None):
        """Return whether a portal user may upload the given document.

        A document upload is allowed when the submission is collecting the
        initial requested documents, when a rejected document needs to be
        replaced during document review, or while the submission is in a
        correction phase (a document was rejected and a correction was
        requested), so the third party can replace the flagged document.
        """
        self.ensure_one()
        if user and not self._portal_is_owned_by(user):
            _logger.warning(
                "Portal document upload ownership denied submission_id=%s document_id=%s user_id=%s",
                self.id,
                document.id if document else None,
                user.id,
            )
            return False
        document_belongs_to_submission = bool(document and document.submission_id == self)
        allowed = document_belongs_to_submission and (
            (self.state == "documents_requested" and document.state in ("pending", "rejected"))
            or (self.state == "documents_review" and document.state == "rejected")
            or (
                self.state in ("correction_required", "correction_submitted")
                and document.state in ("pending", "rejected")
            )
        )
        _logger.debug(
            "Portal document upload rule evaluated submission_id=%s document_id=%s submission_state=%s document_state=%s allowed=%s",
            self.id,
            document.id if document else None,
            self.state,
            document.state if document else None,
            allowed,
        )
        return allowed

    def _all_required_documents_uploaded(self):
        """
        Check if all required documents for the submission have been uploaded.

        Returns:
            bool: True if no required documents are pending or rejected, False otherwise.
        """
        self.ensure_one()
        remaining = self.document_ids.filtered(
            lambda doc: doc.required and doc.state in ("pending", "rejected")
        )
        return not bool(remaining)

    def action_mark_documents_sent_if_complete(self):
        """
        Move the submission to the 'documents_review' state if all required documents are uploaded.
        """
        for record in self:
            if record.state != "documents_requested":
                continue
            if record._all_required_documents_uploaded():
                record.write({"state": "documents_review"})
                record.message_post(
                    body="Todos los documentos solicitados han sido cargados y la solicitud pasa a Documentos enviados."
                )
                _logger.info(
                    "Submission documents uploaded and moved to documents_review submission_id=%s",
                    record.id,
                )

    def _portal_is_owned_by(self, user):
        """Return True when this submission belongs to the given portal user.

        Ownership is determined by matching the submission partner with the user's partner.
        """
        self.ensure_one()
        owned = bool(self.partner_id and self.partner_id == user.partner_id)
        _logger.debug(
            "Portal ownership evaluated submission_id=%s user_id=%s partner_id=%s owner_partner_id=%s owned=%s",
            self.id,
            user.id,
            user.partner_id.id,
            self.partner_id.id,
            owned,
        )
        return owned

    @api.model
    def _portal_ownership_values(self, user):
        """Return default ownership values for a new portal submission.

        These values link the submission to the portal user and their partner.
        """
        _logger.debug(
            "Preparing portal ownership values user_id=%s partner_id=%s",
            user.id,
            user.partner_id.id,
        )
        return {
            "partner_id": user.partner_id.id,
            "portal_user_id": user.id,
            "submitted_by_id": user.id,
        }

    def _submission_confirmation_email_to(self):
        """Return the best available email address for submission confirmation.

        The method falls back through several fields to ensure a recipient is found.
        """
        self.ensure_one()
        return (
            self.partner_id.email
            or self.owner_email
            or self.portal_user_id.email
            or self.submitted_by_id.email
            or self.driver_email
        )

    def _portal_submission_absolute_url(self):
        """Return the absolute portal URL for this submission.

        The returned URL is used by portal views and external links.
        """
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        return "%s/mis-solicitudes-riesgo/%s" % (base_url.rstrip("/"), self.id)

    def _queue_mail_after_commit(
        self,
        template,
        record_id,
        email_values=None,
        force_send=True,
        template_context=None,
        write_values=None,
        failure_values=None,
        success_message=None,
        failure_message=None,
    ):
        """Schedule an email send to run after the current transaction commits.

        The callback sends the mail, writes any follow-up values, and posts a
        success or failure message to the record.
        """
        self.ensure_one()

        dbname = self.env.cr.dbname
        model_name = self._name
        template_id = template.id

        email_values = dict(email_values or {})
        template_context = dict(template_context or {})
        write_values = dict(write_values or {})
        failure_values = dict(failure_values or {})
        success_message = success_message or False
        failure_message = failure_message or False

        def _send_mail(env, rec_id=record_id, commit=False):
            record = env[model_name].browse(rec_id)

            if not record.exists():
                return

            try:
                env["mail.template"].browse(template_id).with_context(
                    **template_context
                ).send_mail(
                    rec_id,
                    force_send=force_send,
                    email_values=email_values,
                )
            except Exception:
                _logger.exception(
                    "Deferred mail send failed model=%s record_id=%s template_id=%s",
                    model_name,
                    rec_id,
                    template_id,
                )
                if failure_values:
                    record.write(failure_values)
                if failure_message:
                    record.message_post(body=failure_message)
                if commit:
                    env.cr.commit()
                return

            if write_values:
                record.write(write_values)
            if success_message:
                record.message_post(body=success_message)
            if commit:
                env.cr.commit()

        def _after_commit_send_mail():
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                _send_mail(env, commit=True)

        if self.env.context.get("risk_send_mail_immediately"):
            _send_mail(self.env)
            return
        self.env.cr.postcommit.add(_after_commit_send_mail)

    def action_send_submission_received_email(self):
        """Send or schedule the submission confirmation email for records.

        If the required mail template or recipient is missing, the method logs
        the problem and updates the submission state accordingly.
        """
        template = self.env.ref(
            "risk_module.email_template_risk_submission_confirmation",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Risk submission confirmation template not found")
            return False

        sent = False
        for record in self:
            recipient = record._submission_confirmation_email_to()
            if not recipient:
                _logger.warning(
                    "Risk submission confirmation email skipped without recipient submission_id=%s",
                    record.id,
                )
                record.write(
                    {
                        "submission_email_status": "skipped",
                        "submission_email_sent_to": False,
                    }
                )
                continue

            record._queue_mail_after_commit(
                template=template,
                record_id=record.id,
                email_values={
                    "email_from": "reporte@impocoma.com",
                    "reply_to": "reporte@impocoma.com",
                    "email_to": recipient,
                    "recipient_ids": [(5, 0, 0)],
                },
                force_send=True,
                write_values={
                    "submission_email_status": "sent",
                    "submission_email_sent_to": recipient,
                    "submission_email_sent_at": fields.Datetime.now(),
                },
                failure_values={
                    "submission_email_status": "failed",
                    "submission_email_sent_to": recipient,
                },
                success_message="Correo de confirmacion de solicitud enviado a %s."
                % recipient,
                failure_message="No fue posible enviar el correo de confirmacion a %s."
                % recipient,
            )

            _logger.info(
                "Risk submission confirmation email scheduled after commit submission_id=%s recipient=%s",
                record.id,
                recipient,
            )
            sent = True

        return sent

    def _submission_rejected_email_to(self):
        """Return the best available email address for submission rejection notifications."""
        self.ensure_one()
        return (
            self.partner_id.email
            or self.owner_email
            or self.portal_user_id.email
            or self.submitted_by_id.email
            or self.driver_email
        )

    def _submission_rejection_notification_partner_ids(self):
        self.ensure_one()
        partners = self.env["res.partner"]
        for partner in (
            self.partner_id,
            self.portal_user_id.partner_id,
            self.submitted_by_id.partner_id,
        ):
            if partner:
                partners |= partner
        return partners.ids

    def action_send_submission_approved_email(self):
        template = self.env.ref(
            "risk_module.email_template_risk_submission_approved",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Risk submission approved template not found")
            return False

        sent = False
        for record in self:
            recipient = record._submission_rejected_email_to()
            if not recipient:
                _logger.warning(
                    "Risk submission approved email skipped without recipient submission_id=%s",
                    record.id,
                )
                continue

            record._queue_mail_after_commit(
                template=template,
                record_id=record.id,
                email_values={
                    "email_from": "reporte@impocoma.com",
                    "reply_to": "reporte@impocoma.com",
                    "email_to": recipient,
                    "recipient_ids": [(5, 0, 0)],
                },
                force_send=True,
                template_context={},
                success_message="Correo de aprobacion de solicitud enviado a %s."
                % recipient,
                failure_message="No fue posible enviar el correo de aprobacion de solicitud a %s."
                % recipient,
            )

            _logger.info(
                "Risk submission approved email scheduled after commit submission_id=%s recipient=%s",
                record.id,
                recipient,
            )
            sent = True

        return sent

    def action_send_submission_rejected_email(self):
        template = self.env.ref(
            "risk_module.email_template_risk_submission_rejected",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Risk submission rejected template not found")
            return False

        sent = False
        for record in self:
            recipient = record._submission_rejected_email_to()
            if not recipient:
                _logger.warning(
                    "Risk submission rejected email skipped without recipient submission_id=%s",
                    record.id,
                )
                continue

            record._queue_mail_after_commit(
                template=template,
                record_id=record.id,
                email_values={
                    "email_from": "reporte@impocoma.com",
                    "reply_to": "reporte@impocoma.com",
                    "email_to": recipient,
                    "recipient_ids": [(5, 0, 0)],
                },
                force_send=True,
                template_context={
                    "submission_rejection_reason": record.rejection_reason or "",
                },
                success_message="Correo de rechazo de solicitud enviado a %s."
                % recipient,
                failure_message="No fue posible enviar el correo de rechazo de solicitud a %s."
                % recipient,
            )

            _logger.info(
                "Risk submission rejected email scheduled after commit submission_id=%s recipient=%s",
                record.id,
                recipient,
            )
            sent = True

        return sent

    def action_send_correction_requested_email(self):
        template = self.env.ref(
            "risk_module.email_template_risk_submission_correction_requested",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Risk correction requested template not found")
            return False

        sent = False
        for record in self:
            recipient = record._submission_rejected_email_to()
            if not recipient:
                _logger.warning(
                    "Risk correction requested email skipped without recipient submission_id=%s",
                    record.id,
                )
                continue

            record._queue_mail_after_commit(
                template=template,
                record_id=record.id,
                email_values={
                    "email_from": "reporte@impocoma.com",
                    "reply_to": "reporte@impocoma.com",
                    "email_to": recipient,
                    "recipient_ids": [(5, 0, 0)],
                },
                force_send=True,
                template_context={
                    "correction_reason": record.correction_reason or "",
                    "correction_sections": record._correction_section_labels(),
                },
                success_message="Correo de correccion de solicitud enviado a %s."
                % recipient,
                failure_message="No fue posible enviar el correo de correccion de solicitud a %s."
                % recipient,
            )
            sent = True
        return sent

    def _correction_section_labels(self):
        self.ensure_one()
        sections = [
            ("correction_section_vehicle", "Vehiculo"),
            ("correction_section_owner", "Propietario"),
            ("correction_section_driver", "Conductor"),
            ("correction_section_satellite", "Satelital"),
            ("correction_section_signatures", "Firmas"),
            ("correction_section_terms", "Terminos"),
            ("correction_section_other", "Otro"),
        ]
        labels = [label for field, label in sections if self[field]]
        return ", ".join(labels) if labels else "No especificadas"

    def _documents_requested_email_to(self):
        """Return the best available email address for documents-requested notifications."""
        self.ensure_one()
        return (
            self.partner_id.email
            or self.owner_email
            or self.portal_user_id.email
            or self.submitted_by_id.email
            or self.driver_email
        )

    def _risk_message_template_body(self, category, code, default=False):
        return self.env["risk.message.template"]._get_body(
            category,
            code,
            default=default,
        )

    def action_send_documents_requested_email(self):
        template = self.env.ref(
            "risk_module.email_template_risk_submission_documents_requested",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Risk documents requested template not found")
            return False

        sent = False
        for record in self:
            recipient = record._documents_requested_email_to()
            if not recipient:
                _logger.warning(
                    "Risk documents requested email skipped without recipient submission_id=%s",
                    record.id,
                )
                continue

            record._queue_mail_after_commit(
                template=template,
                record_id=record.id,
                email_values={
                    "email_from": "reporte@impocoma.com",
                    "reply_to": "reporte@impocoma.com",
                    "email_to": recipient,
                    "recipient_ids": [(5, 0, 0)],
                },
                force_send=True,
                template_context={
                    "documents_requested_message": record._risk_message_template_body(
                        "document_request",
                        "documents_requested",
                        default=(
                            "Hemos solicitado documentos adicionales para tu solicitud."
                        ),
                    ),
                },
                success_message="Correo de solicitud de documentos enviado a %s."
                % recipient,
                failure_message="No fue posible enviar el correo de solicitud de documentos a %s."
                % recipient,
            )

            _logger.info(
                "Documents requested email scheduled after commit submission_id=%s recipient=%s",
                record.id,
                recipient,
            )
            sent = True

        return sent

    def _document_rejected_email_to(self):
        """Return the best available email address for rejected-document notifications."""
        self.ensure_one()
        return (
            self.partner_id.email
            or self.owner_email
            or self.portal_user_id.email
            or self.submitted_by_id.email
            or self.driver_email
        )

    def action_send_document_rejected_email(self, document):
        template = self.env.ref(
            "risk_module.email_template_risk_submission_document_rejected",
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning("Risk document rejected template not found")
            return False

        recipient = self._document_rejected_email_to()
        if not recipient:
            _logger.warning(
                "Risk document rejected email skipped without recipient submission_id=%s document_id=%s",
                self.id,
                getattr(document, "id", None),
            )
            return False

        self._queue_mail_after_commit(
            template=template,
            record_id=self.id,
            email_values={
                "email_from": "reporte@impocoma.com",
                "reply_to": "reporte@impocoma.com",
                "email_to": recipient,
                "recipient_ids": [(5, 0, 0)],
            },
            force_send=True,
            template_context={
                "rejected_document_name": document.name,
                "rejection_observations": document.observations or "",
                "document_rejected_message": self._risk_message_template_body(
                    "document_rejected_email",
                    "document_rejected",
                    default="Uno de tus documentos requiere correccion.",
                ),
            },
            success_message="Correo de documento rechazado enviado a %s." % recipient,
            failure_message="No fue posible enviar el correo de documento rechazado a %s."
            % recipient,
        )

        _logger.info(
            "Document rejected email scheduled after commit submission_id=%s document_id=%s recipient=%s",
            self.id,
            getattr(document, "id", None),
            recipient,
        )
        return True

    def action_open_printable(self):
        """Return an action to open the printable submission report.

        The URL includes a temporary access token for secure printable access.
        """
        self.ensure_one()
        if not self.access_token:
            _logger.info("Generating printable access token submission_id=%s", self.id)
            self.access_token = uuid.uuid4().hex
        _logger.info(
            "Opening printable action submission_id=%s user_id=%s",
            self.id,
            self.env.user.id,
        )
        return {
            "type": "ir.actions.act_url",
            "name": "Hoja de Vida Imprimible",
            "url": f"/registro-conductor/imprimir/{self.id}?token={self.access_token}",
            "target": "new",
        }

    @api.model
    def _active_submission_states(self):
        """Return states considered active for duplicate-request checks."""
        return self._ACTIVE_SUBMISSION_STATES

    @api.model
    def _find_active_submission_for_plate(self, plate, exclude_id=False):
        """Return another active submission for the same plate, if any."""
        normalized_plate = self._normalize_plate(plate)
        if not normalized_plate:
            return self.browse()
        domain = [
            ("vehicle_plate", "=", normalized_plate),
            ("state", "in", self._active_submission_states()),
        ]
        if exclude_id:
            domain.append(("id", "!=", int(exclude_id)))
        return self.search(domain, limit=1)

    @api.model
    def _risk_warning_normalize_email(self, value):
        return (value or "").strip().lower()

    @api.model
    def _risk_warning_normalize_digits(self, value):
        return "".join(character for character in (value or "") if character.isdigit())

    @api.model
    def _risk_warning_normalize_name(self, value):
        return " ".join((value or "").strip().lower().split())

    @api.model
    def _risk_warning_watched_fields(self):
        return {
            "vehicle_plate",
            "owner_name",
            "owner_document_number",
            "owner_phone",
            "owner_email",
            "registered_owner_document_number",
            "registered_owner_phone",
            "driver_name",
            "driver_document_number",
            "driver_phone",
            "driver_optional_phone",
            "driver_email",
        }

    def _risk_warning_related_submissions(self, field_name, value, states=False):
        self.ensure_one()
        if not value:
            return self.browse()
        domain = [(field_name, "=", value), ("id", "!=", self.id)]
        if states:
            domain.append(("state", "in", states))
        return self.search(domain, limit=20)

    def _risk_warning_related_email_submissions(self, field_names, value, states=False):
        self.ensure_one()
        if not value:
            return self.browse()
        related = self.browse()
        for field_name in field_names:
            domain = [(field_name, "!=", False), ("id", "!=", self.id)]
            if states:
                domain.append(("state", "in", states))
            candidates = self.search(domain, limit=50)
            related |= candidates.filtered(
                lambda item: self._risk_warning_normalize_email(
                    getattr(item, field_name)
                )
                == value
            )
        return related

    def _risk_warning_related_digit_submissions(self, field_names, value, states=False):
        self.ensure_one()
        if not value:
            return self.browse()
        related = self.browse()
        for field_name in field_names:
            domain = [(field_name, "!=", False), ("id", "!=", self.id)]
            if states:
                domain.append(("state", "in", states))
            candidates = self.search(domain, limit=50)
            related |= candidates.filtered(
                lambda item: self._risk_warning_normalize_digits(
                    getattr(item, field_name)
                )
                == value
            )
        return related

    def _risk_warning_create_once(
        self,
        rule_code,
        category,
        severity,
        matched_value,
        message,
        related_submissions=False,
    ):
        self.ensure_one()
        matched_value = (matched_value or "").strip()
        if not matched_value:
            return self.env["risk.warning"]
        Warning = self.env["risk.warning"].sudo()
        existing = Warning.search(
            [
                ("submission_id", "=", self.id),
                ("rule_code", "=", rule_code),
                ("matched_value", "=", matched_value),
            ],
            limit=1,
        )
        if existing:
            if related_submissions:
                existing.related_submission_ids = [(6, 0, related_submissions.ids)]
            return existing
        return Warning.create(
            {
                "submission_id": self.id,
                "rule_code": rule_code,
                "category": category,
                "severity": severity,
                "matched_value": matched_value,
                "message": message,
                "related_submission_ids": [
                    (6, 0, related_submissions.ids if related_submissions else [])
                ],
            }
        )

    def _generate_risk_warnings(self):
        """Create internal risk warnings from deterministic first-pass rules."""
        active_states = self._active_submission_states()
        for record in self:
            owner_email = record._risk_warning_normalize_email(record.owner_email)
            driver_email = record._risk_warning_normalize_email(record.driver_email)
            email_fields = ["owner_email", "driver_email"]
            for field_name, label, email in (
                ("owner_email", "correo del propietario", owner_email),
                ("driver_email", "correo del conductor", driver_email),
            ):
                if not email:
                    continue
                active_related = record._risk_warning_related_email_submissions(
                    email_fields,
                    email,
                    states=active_states,
                )
                if active_related:
                    record._risk_warning_create_once(
                        "duplicate_%s_active" % field_name,
                        "email",
                        "warning",
                        email,
                        "El %s ya aparece en otra solicitud activa." % label,
                        active_related,
                    )
                rejected_related = record._risk_warning_related_email_submissions(
                    email_fields,
                    email,
                    states=["rejected"],
                )
                if rejected_related:
                    record._risk_warning_create_once(
                        "rejected_%s_history" % field_name,
                        "history",
                        "warning",
                        email,
                        "El %s aparece en una solicitud rechazada anteriormente."
                        % label,
                        rejected_related,
                    )

            phone_values = [
                ("owner_phone", "telefono del propietario", record.owner_phone),
                (
                    "registered_owner_phone",
                    "telefono del propietario registrado",
                    record.registered_owner_phone,
                ),
                ("driver_phone", "telefono del conductor", record.driver_phone),
                (
                    "driver_optional_phone",
                    "telefono opcional del conductor",
                    record.driver_optional_phone,
                ),
            ]
            phone_fields = [item[0] for item in phone_values]
            for field_name, label, raw_value in phone_values:
                phone = record._risk_warning_normalize_digits(raw_value)
                if not phone:
                    continue
                active_related = record._risk_warning_related_digit_submissions(
                    phone_fields,
                    phone,
                    states=active_states,
                )
                if active_related:
                    record._risk_warning_create_once(
                        "duplicate_%s_active" % field_name,
                        "phone",
                        "warning",
                        phone,
                        "El %s ya aparece en otra solicitud activa." % label,
                        active_related,
                    )
                rejected_related = record._risk_warning_related_digit_submissions(
                    phone_fields,
                    phone,
                    states=["rejected"],
                )
                if rejected_related:
                    record._risk_warning_create_once(
                        "rejected_%s_history" % field_name,
                        "history",
                        "warning",
                        phone,
                        "El %s aparece en una solicitud rechazada anteriormente."
                        % label,
                        rejected_related,
                    )

            owner_doc = record._risk_warning_normalize_digits(
                record.owner_document_number
            )
            if owner_doc:
                related = record._risk_warning_related_digit_submissions(
                    ["owner_document_number", "registered_owner_document_number"],
                    owner_doc,
                )
                different_name = related.filtered(
                    lambda item: record._risk_warning_normalize_name(item.owner_name)
                    and record._risk_warning_normalize_name(item.owner_name)
                    != record._risk_warning_normalize_name(record.owner_name)
                )
                if different_name:
                    record._risk_warning_create_once(
                        "owner_document_different_name",
                        "document",
                        "critical",
                        owner_doc,
                        "El documento del propietario existe con un nombre diferente.",
                        different_name,
                    )

            driver_doc = record._risk_warning_normalize_digits(
                record.driver_document_number
            )
            if driver_doc:
                related = record._risk_warning_related_digit_submissions(
                    ["driver_document_number", "owner_document_number"],
                    driver_doc,
                )
                different_name = related.filtered(
                    lambda item: record._risk_warning_normalize_name(item.driver_name)
                    and record._risk_warning_normalize_name(item.driver_name)
                    != record._risk_warning_normalize_name(record.driver_name)
                )
                if different_name:
                    record._risk_warning_create_once(
                        "driver_document_different_name",
                        "document",
                        "critical",
                        driver_doc,
                        "El documento del conductor existe con un nombre diferente.",
                        different_name,
                    )

            plate = record._normalize_plate(record.vehicle_plate)
            if plate:
                related = record._risk_warning_related_submissions(
                    "vehicle_plate",
                    plate,
                )
                different_owner = related.filtered(
                    lambda item: record._risk_warning_normalize_digits(
                        item.owner_document_number
                    )
                    and record._risk_warning_normalize_digits(
                        item.owner_document_number
                    )
                    != owner_doc
                )
                if different_owner:
                    record._risk_warning_create_once(
                        "plate_different_owner",
                        "plate",
                        "critical",
                        plate,
                        "La placa aparece asociada a otro propietario.",
                        different_owner,
                    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create risk submission records and normalize key fields.

        Vehicle plate and owner city values are normalized before the record is created.
        If a submission is already in submitted state, the confirmation email is scheduled.
        """
        _logger.info(
            "Creating risk submissions count=%s user_id=%s",
            len(vals_list),
            self.env.user.id,
        )
        for vals in vals_list:
            if vals.get("vehicle_plate"):
                vals["vehicle_plate"] = self._normalize_plate(vals["vehicle_plate"])
            if vals.get("semi_trailer_plate"):
                vals["semi_trailer_plate"] = self._normalize_plate(
                    vals["semi_trailer_plate"]
                )
            if vals.get("owner_city"):
                vals["owner_city"] = self._normalize_city(vals["owner_city"])
        records = super().create(vals_list)
        for record in records:
            _logger.info(
                "Risk submission created submission_id=%s plate=%s state=%s partner_id=%s",
                record.id,
                record.vehicle_plate,
                record.state,
                record.partner_id.id,
            )
        submitted_records = records.filtered(lambda record: record.state == "submitted")
        if submitted_records:
            submitted_records.action_send_submission_received_email()
        records._generate_risk_warnings()
        return records

    def write(self, vals):
        """Write values to risk submissions with normalization and transition handling.

        Normalizes vehicle plates and owner city fields, logs state changes, and
        sends the confirmation email when records transition into submitted state.
        """
        old_states = {record.id: record.state for record in self}
        _logger.debug(
            "Writing risk submissions ids=%s user_id=%s fields=%s",
            self.ids,
            self.env.user.id,
            sorted(vals.keys()),
        )
        self._check_form_locked_fields_for_risk_analyst(vals)
        if vals.get("vehicle_plate"):
            vals["vehicle_plate"] = self._normalize_plate(vals["vehicle_plate"])
        if vals.get("semi_trailer_plate"):
            vals["semi_trailer_plate"] = self._normalize_plate(
                vals["semi_trailer_plate"]
            )
        if vals.get("owner_city"):
            vals["owner_city"] = self._normalize_city(vals["owner_city"])
        result = super().write(vals)
        if "state" in vals:
            for record in self:
                _logger.info(
                    "Risk submission state changed submission_id=%s old_state=%s new_state=%s user_id=%s",
                    record.id,
                    old_states.get(record.id),
                    record.state,
                    self.env.user.id,
                )
        submitted_records = self.filtered(
            lambda record: (
                vals.get("state") == "submitted"
                and old_states.get(record.id) != "submitted"
                and record.submission_email_status != "sent"
            )
        )
        if submitted_records:
            submitted_records.action_send_submission_received_email()
        if self._risk_warning_watched_fields().intersection(vals) or vals.get("state") in (
            "submitted",
            "risk_review",
            "manual_approval_pending",
            "documents_review",
        ):
            self._generate_risk_warnings()
        return result
