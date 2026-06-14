import hashlib
import hmac
import logging
import secrets
import uuid
import odoo
from datetime import timedelta
from odoo.orm.registry import Registry
from odoo import api, fields, models, SUPERUSER_ID
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
_signature_logger = logging.getLogger("risk_module.signatures")

SIGNATURE_CODE_TTL_MINUTES = 15
SIGNATURE_CODE_RESEND_SECONDS = 60
SIGNATURE_CODE_MAX_ATTEMPTS = 5


class RiskSubmission(models.Model):
    _name = "risk.module"
    _description = "Solicitud de habilitacion de terceros"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "vehicle_plate"
    _order = "create_date desc"

    _FORM_LOCKED_FIELDS = frozenset(
        {
            "form_date",
            "vehicle_plate",
            "semi_trailer_plate",
            "satellite_company",
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
    vehicle_plate = fields.Char(string="Placa", required=True)
    semi_trailer_plate = fields.Char(string="Semi/Remolque")
    satellite_company = fields.Char(string="Empresa satelital")
    satellite_user = fields.Char(string="Usuario satelital")
    satellite_password = fields.Char(string="Clave satelital")
    owner_name = fields.Char(string="Nombres y apellidos / Empresa")
    owner_document_type = fields.Selection(
        [
            ("cc", "CC"),
            ("nit", "Nit"),
        ],
        string="Tipo de documento",
    )
    owner_document_number = fields.Char(string="Numero de documento")
    owner_address = fields.Char(string="Direccion")
    owner_neighborhood = fields.Char(string="Barrio")
    owner_city = fields.Char(string="Ciudad")
    owner_phone = fields.Char(string="Celular notificaciones")
    owner_email = fields.Char(string="Correo facturacion y notificaciones")
    advance_payment_to = fields.Selection(
        [
            ("driver", "Conductor"),
            ("owner", "Propietario"),
        ],
        string="Entrega y pago de anticipos a",
    )
    same_owner_on_license = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Corresponde al propietario en licencia",
    )
    registered_owner_document_type = fields.Selection(
        [
            ("cc", "CC"),
            ("nit", "Nit"),
        ],
        string="Tipo documento propietario",
    )
    registered_owner_document_number = fields.Char(
        string="Numero documento propietario"
    )
    registered_owner_name = fields.Char(string="Nombres y apellidos propietario")
    registered_owner_phone = fields.Char(string="Celular propietario")
    driver_name = fields.Char(string="Nombres y apellidos conductor")
    driver_document_number = fields.Char(string="Numero de cedula conductor")
    driver_address = fields.Char(string="Direccion conductor")
    driver_neighborhood = fields.Char(string="Barrio conductor")
    driver_city = fields.Char(string="Ciudad conductor")
    driver_phone = fields.Char(string="Celular conductor")
    driver_optional_phone = fields.Char(string="Telefono opcional conductor")
    driver_email = fields.Char(string="Correo autorizacion conductor")
    driver_is_fit = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Apto fisica, mental y psicotecnicamente",
    )
    driver_is_trained = fields.Selection(
        [
            ("yes", "Si"),
            ("no", "No"),
        ],
        string="Capacitado y entrenado",
    )
    family_reference_name = fields.Char(string="Referencia familiar")
    family_reference_relationship = fields.Char(string="Parentesco referencia familiar")
    family_reference_phone = fields.Char(string="Celular referencia familiar")
    cargo_reference_name = fields.Char(string="Referencia transporte de carga")
    cargo_reference_phone = fields.Char(string="Celular referencia transporte de carga")
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
            "draft": "En revision",
            "submitted": "En revision",
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

        A document upload is only allowed when the submission is in the
        documents_requested state, the document belongs to this submission and
        the document state is pending or rejected.
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
        allowed = (
            self.state == "documents_requested"
            and document
            and document.submission_id == self
            and document.state in ("pending", "rejected")
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

        def _after_commit_send_mail(
            rec_id=record_id,
            template_id=template_id,
            email_values=email_values,
            template_context=template_context,
            write_values=write_values,
            failure_values=failure_values,
            success_message=success_message,
            failure_message=failure_message,
        ):
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})

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
                    cr.commit()
                    return

                if write_values:
                    record.write(write_values)
                if success_message:
                    record.message_post(body=success_message)

                cr.commit()

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

    def _signature_party_config(self, party):
        """Return the signature configuration mapping for the requested party.

        Valid parties are 'owner' and 'driver'. A ValueError is raised for invalid parties.
        """
        configs = {
            "owner": {
                "label": "propietario",
                "email_field": "owner_email",
                "name_field": "owner_name",
                "template": "risk_module.email_template_owner_signature_code",
                "email": "owner_signature_email",
                "hash": "owner_signature_code_hash",
                "sent_at": "owner_signature_code_sent_at",
                "expires_at": "owner_signature_code_expires_at",
                "verified_at": "owner_signature_verified_at",
                "verified_ip": "owner_signature_verified_ip",
                "attempts": "owner_signature_code_attempts",
                "state": "owner_signature_verification_state",
            },
            "driver": {
                "label": "conductor",
                "email_field": "driver_email",
                "name_field": "driver_name",
                "template": "risk_module.email_template_driver_signature_code",
                "email": "driver_signature_email",
                "hash": "driver_signature_code_hash",
                "sent_at": "driver_signature_code_sent_at",
                "expires_at": "driver_signature_code_expires_at",
                "verified_at": "driver_signature_verified_at",
                "verified_ip": "driver_signature_verified_ip",
                "attempts": "driver_signature_code_attempts",
                "state": "driver_signature_verification_state",
            },
        }
        if party not in configs:
            raise ValueError("Invalid signature verification party: %s" % party)
        return configs[party]

    def _signature_code_hash(self, party, code):
        """Return a secure HMAC hash for a signature verification code.

        The hash is derived from the record identity, access token, party and code.
        """
        self.ensure_one()
        salt = "%s:%s:%s" % (self._name, self.id, self.access_token or "")
        payload = "%s:%s" % (party, code)
        return hmac.new(
            salt.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signature_email_verified_for(self, party, email):
        """Return True when the given email is verified for the signature party.

        The method checks the stored state, verification timestamp, and matching email.
        """
        self.ensure_one()
        config = self._signature_party_config(party)
        return bool(
            email
            and self[config["state"]] == "verified"
            and self[config["verified_at"]]
            and self[config["email"]] == email
        )

    def _send_signature_code(self, party):
        """Generate and send a verification code to the party's email address.

        The method enforces resend throttling and stores the hashed code and
        expiration details on the record.
        """
        self.ensure_one()
        config = self._signature_party_config(party)
        email = (self[config["email_field"]] or "").strip()

        if not email:
            _signature_logger.warning(
                "Signature code send blocked without email submission_id=%s party=%s",
                self.id,
                party,
            )
            return {
                "ok": False,
                "message": "Debes ingresar un correo para el %s antes de enviar el codigo."
                % config["label"],
            }

        now = fields.Datetime.now()
        sent_at = self[config["sent_at"]]
        if sent_at and (now - sent_at).total_seconds() < SIGNATURE_CODE_RESEND_SECONDS:
            _signature_logger.warning(
                "Signature code resend throttled submission_id=%s party=%s email=%s",
                self.id,
                party,
                email,
            )
            return {
                "ok": False,
                "message": "Espera un minuto antes de solicitar otro codigo.",
            }

        code = "%06d" % secrets.randbelow(1000000)
        expires_at = now + timedelta(minutes=SIGNATURE_CODE_TTL_MINUTES)

        self.write(
            {
                config["email"]: email,
                config["hash"]: self._signature_code_hash(party, code),
                config["sent_at"]: now,
                config["expires_at"]: expires_at,
                config["verified_at"]: False,
                config["verified_ip"]: False,
                config["attempts"]: 0,
                config["state"]: "sent",
            }
        )

        template = self.env.ref(config["template"], raise_if_not_found=False)
        if not template:
            _signature_logger.warning("Signature code template not found party=%s", party)
            return {
                "ok": False,
                "message": "No se encontro la plantilla de correo para enviar el codigo.",
            }

        self._queue_mail_after_commit(
            template=template,
            record_id=self.id,
            email_values={
                "email_from": "reporte@impocoma.com",
                "reply_to": "reporte@impocoma.com",
                "email_to": email,
                "recipient_ids": [(5, 0, 0)],
            },
            force_send=True,
            template_context={
                "signature_code": code,
                "signature_party_label": config["label"],
                "signature_person_name": self[config["name_field"]] or config["label"],
                "signature_code_ttl_minutes": SIGNATURE_CODE_TTL_MINUTES,
            },
            failure_values={
                config["hash"]: False,
                config["sent_at"]: False,
                config["expires_at"]: False,
                config["verified_at"]: False,
                config["verified_ip"]: False,
                config["attempts"]: 0,
                config["state"]: "not_sent",
            },
            success_message="Codigo de verificacion de firma enviado al %s: %s."
            % (config["label"], email),
            failure_message="No fue posible enviar el codigo de verificacion al %s: %s."
            % (config["label"], email),
        )

        _signature_logger.info(
            "Signature code email scheduled after commit submission_id=%s party=%s email=%s expires_at=%s",
            self.id,
            party,
            email,
            expires_at,
        )

        return {
            "ok": True,
            "message": "Enviamos un codigo al correo del %s." % config["label"],
        }

    def _verify_signature_code(self, party, code, ip_address=None):
        """Verify a submitted signature code and update verification state.

        The method handles invalid codes, expired codes, throttling, and blocked state.
        """
        self.ensure_one()
        config = self._signature_party_config(party)
        clean_code = (code or "").strip()
        now = fields.Datetime.now()

        if self[config["state"]] == "blocked":
            return {
                "ok": False,
                "message": "El codigo esta bloqueado por demasiados intentos. Solicita uno nuevo.",
            }
        if not self[config["hash"]]:
            return {
                "ok": False,
                "message": "Primero debes solicitar un codigo de verificacion.",
            }
        if not clean_code or len(clean_code) != 6 or not clean_code.isdigit():
            return {
                "ok": False,
                "message": "Ingresa un codigo de 6 digitos.",
            }
        if self[config["expires_at"]] and now > self[config["expires_at"]]:
            self.write({config["state"]: "expired"})
            return {
                "ok": False,
                "message": "El codigo vencio. Solicita uno nuevo.",
            }

        attempts = self[config["attempts"]] + 1
        if not hmac.compare_digest(
            self[config["hash"]],
            self._signature_code_hash(party, clean_code),
        ):
            state = "blocked" if attempts >= SIGNATURE_CODE_MAX_ATTEMPTS else "sent"
            self.write(
                {
                    config["attempts"]: attempts,
                    config["state"]: state,
                }
            )
            _signature_logger.warning(
                "Signature code verification failed submission_id=%s party=%s attempts=%s state=%s",
                self.id,
                party,
                attempts,
                state,
            )
            if state == "blocked":
                return {
                    "ok": False,
                    "message": "Codigo bloqueado por demasiados intentos. Solicita uno nuevo.",
                }
            return {
                "ok": False,
                "message": "Codigo incorrecto. Revisa el correo e intenta nuevamente.",
            }

        self.write(
            {
                config["verified_at"]: now,
                config["verified_ip"]: ip_address,
                config["attempts"]: attempts,
                config["state"]: "verified",
            }
        )
        self.message_post(
            body="Correo de firma verificado para el %s: %s."
            % (config["label"], self[config["email"]])
        )
        _signature_logger.info(
            "Signature code verified submission_id=%s party=%s email=%s ip=%s",
            self.id,
            party,
            self[config["email"]],
            ip_address,
        )
        return {
            "ok": True,
            "message": "Correo del %s verificado correctamente." % config["label"],
        }

    def send_owner_signature_code(self):
        """Send a verification code to the owner's email address."""
        return self._send_signature_code("owner")

    def verify_owner_signature_code(self, code, ip_address=None):
        """Verify the owner's submitted signature code."""
        return self._verify_signature_code("owner", code, ip_address=ip_address)

    def send_driver_signature_code(self):
        """Send a verification code to the driver's email address."""
        return self._send_signature_code("driver")

    def verify_driver_signature_code(self, code, ip_address=None):
        """Verify the driver's submitted signature code."""
        return self._verify_signature_code("driver", code, ip_address=ip_address)

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
        return result
