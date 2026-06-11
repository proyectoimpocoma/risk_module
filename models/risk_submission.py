import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import timedelta

from odoo import api, fields, models

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

    name = fields.Char(string="Referencia")
    state = fields.Selection([
        ("draft", "Borrador"),
        ("submitted", "Enviado"),
        ("risk_review", "En revision de riesgo"),
        ("external_validation_pending", "Validacion externa pendiente"),
        ("manual_approval_pending", "Pendiente aprobacion manual"),
        ("documents_requested", "Documentos solicitados"),
        ("documents_review", "Documentos en revision"),
        ("approved", "Aprobado"),
        ("rejected", "Rechazado"),
    ], string="Estado", default="draft", required=True, tracking=True)
    access_token = fields.Char(string="Token publico", default=lambda self: uuid.uuid4().hex, copy=False)
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
    owner_document_type = fields.Selection([
        ("cc", "CC"),
        ("nit", "Nit"),
    ], string="Tipo de documento")
    owner_document_number = fields.Char(string="Numero de documento")
    owner_address = fields.Char(string="Direccion")
    owner_neighborhood = fields.Char(string="Barrio")
    owner_city = fields.Char(string="Ciudad")
    owner_phone = fields.Char(string="Celular notificaciones")
    owner_email = fields.Char(string="Correo facturacion y notificaciones")
    advance_payment_to = fields.Selection([
        ("driver", "Conductor"),
        ("owner", "Propietario"),
    ], string="Entrega y pago de anticipos a")
    same_owner_on_license = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Corresponde al propietario en licencia")
    registered_owner_document_type = fields.Selection([
        ("cc", "CC"),
        ("nit", "Nit"),
    ], string="Tipo documento propietario")
    registered_owner_document_number = fields.Char(string="Numero documento propietario")
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
    driver_is_fit = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Apto fisica, mental y psicotecnicamente")
    driver_is_trained = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Capacitado y entrenado")
    family_reference_name = fields.Char(string="Referencia familiar")
    family_reference_relationship = fields.Char(string="Parentesco referencia familiar")
    family_reference_phone = fields.Char(string="Celular referencia familiar")
    cargo_reference_name = fields.Char(string="Referencia transporte de carga")
    cargo_reference_phone = fields.Char(string="Celular referencia transporte de carga")
    banking_info_accepted = fields.Boolean(string="Acepto informacion bancaria")
    compensation_accepted = fields.Boolean(string="Acepto compensacion general")
    personal_data_accepted = fields.Boolean(string="Acepto tratamiento de datos personales")
    terms_accepted_at = fields.Datetime(string="Fecha aceptacion terminos")
    owner_has_valid_study = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Propietario con estudio vigente")
    owner_signature = fields.Binary(string="Firma propietario")
    owner_signature_document = fields.Char(string="Cedula firma propietario")
    owner_signed_at = fields.Datetime(string="Fecha firma propietario")
    owner_signature_ip = fields.Char(string="IP firma propietario")
    owner_signature_user_agent = fields.Text(string="Navegador firma propietario")
    owner_signature_email = fields.Char(string="Correo verificado propietario", readonly=True, copy=False)
    owner_signature_code_hash = fields.Char(string="Hash codigo propietario", readonly=True, copy=False)
    owner_signature_code_sent_at = fields.Datetime(string="Codigo propietario enviado", readonly=True, copy=False)
    owner_signature_code_expires_at = fields.Datetime(string="Codigo propietario vence", readonly=True, copy=False)
    owner_signature_verified_at = fields.Datetime(string="Correo propietario verificado", readonly=True, copy=False)
    owner_signature_verified_ip = fields.Char(string="IP verificacion propietario", readonly=True, copy=False)
    owner_signature_code_attempts = fields.Integer(string="Intentos codigo propietario", readonly=True, copy=False)
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
    driver_has_valid_study = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Conductor con estudio vigente")
    driver_signature = fields.Binary(string="Firma conductor")
    driver_signature_document = fields.Char(string="Cedula firma conductor")
    driver_signed_at = fields.Datetime(string="Fecha firma conductor")
    driver_signature_ip = fields.Char(string="IP firma conductor")
    driver_signature_user_agent = fields.Text(string="Navegador firma conductor")
    driver_signature_email = fields.Char(string="Correo verificado conductor", readonly=True, copy=False)
    driver_signature_code_hash = fields.Char(string="Hash codigo conductor", readonly=True, copy=False)
    driver_signature_code_sent_at = fields.Datetime(string="Codigo conductor enviado", readonly=True, copy=False)
    driver_signature_code_expires_at = fields.Datetime(string="Codigo conductor vence", readonly=True, copy=False)
    driver_signature_verified_at = fields.Datetime(string="Correo conductor verificado", readonly=True, copy=False)
    driver_signature_verified_ip = fields.Char(string="IP verificacion conductor", readonly=True, copy=False)
    driver_signature_code_attempts = fields.Integer(string="Intentos codigo conductor", readonly=True, copy=False)
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
    approval_note = fields.Text(string="Comentario de aprobacion", readonly=True, copy=False)
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
    rejection_reason = fields.Text(string="Motivo de rechazo", readonly=True, copy=False)
    document_ids = fields.One2many(
        "risk.module.document",
        "submission_id",
        string="Documentos",
        copy=False,
    )
    external_validation_ids = fields.One2many(
        "risk.external.validation",
        "submission_id",
        string="Validaciones externas",
        copy=False,
    )

    @api.depends("state")
    def _compute_portal_state_label(self):
        labels = {
            "draft": "En revision",
            "submitted": "En revision",
            "risk_review": "En revision",
            "external_validation_pending": "En revision",
            "manual_approval_pending": "En revision",
            "documents_requested": "Documentos solicitados",
            "documents_review": "Documentos en revision",
            "approved": "Aprobada",
            "rejected": "Rechazada",
        }
        for record in self:
            record.portal_state_label = labels.get(record.state, "En revision")

    def _portal_document_upload_allowed(self, document, user=None):
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

    def _portal_is_owned_by(self, user):
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
        _logger.debug("Preparing portal ownership values user_id=%s partner_id=%s", user.id, user.partner_id.id)
        return {
            "partner_id": user.partner_id.id,
            "portal_user_id": user.id,
            "submitted_by_id": user.id,
        }

    def _submission_confirmation_email_to(self):
        self.ensure_one()
        return (
            self.partner_id.email
            or self.owner_email
            or self.portal_user_id.email
            or self.submitted_by_id.email
            or self.driver_email
        )

    def _portal_submission_absolute_url(self):
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        return "%s/mis-solicitudes-riesgo/%s" % (base_url.rstrip("/"), self.id)

    def action_send_submission_received_email(self):
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
                record.write({
                    "submission_email_status": "skipped",
                    "submission_email_sent_to": False,
                })
                continue

            email_values = {
                "email_from": "reporte@impocoma.com",
                "reply_to": "reporte@impocoma.com",
                "email_to": recipient,
                "recipient_ids": [(5, 0, 0)],
            }
            try:
                template.sudo().send_mail(
                    record.id,
                    force_send=False,
                    email_values=email_values,
                )
            except Exception:
                _logger.exception(
                    "Risk submission confirmation email failed submission_id=%s recipient=%s",
                    record.id,
                    recipient,
                )
                record.write({
                    "submission_email_status": "failed",
                    "submission_email_sent_to": recipient,
                })
                continue

            record.write({
                "submission_email_status": "sent",
                "submission_email_sent_to": recipient,
                "submission_email_sent_at": fields.Datetime.now(),
            })
            record.message_post(
                body="Correo de confirmacion de solicitud enviado a %s." % recipient
            )
            _logger.info(
                "Risk submission confirmation email queued submission_id=%s recipient=%s",
                record.id,
                recipient,
            )
            sent = True
        return sent

    def _signature_party_config(self, party):
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
        self.ensure_one()
        salt = "%s:%s:%s" % (self._name, self.id, self.access_token or "")
        payload = "%s:%s" % (party, code)
        return hmac.new(
            salt.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signature_email_verified_for(self, party, email):
        self.ensure_one()
        config = self._signature_party_config(party)
        return bool(
            email
            and self[config["state"]] == "verified"
            and self[config["verified_at"]]
            and self[config["email"]] == email
        )

    def _send_signature_code(self, party):
        self.ensure_one()
        config = self._signature_party_config(party)
        email = (self[config["email_field"]] or "").strip()
        if not email:
            _logger.warning(
                "Signature code send blocked without email submission_id=%s party=%s",
                self.id,
                party,
            )
            return {
                "ok": False,
                "message": "Debes ingresar un correo para el %s antes de enviar el codigo." % config["label"],
            }

        now = fields.Datetime.now()
        sent_at = self[config["sent_at"]]
        if sent_at and (now - sent_at).total_seconds() < SIGNATURE_CODE_RESEND_SECONDS:
            _logger.warning(
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
        self.write({
            config["email"]: email,
            config["hash"]: self._signature_code_hash(party, code),
            config["sent_at"]: now,
            config["expires_at"]: expires_at,
            config["verified_at"]: False,
            config["verified_ip"]: False,
            config["attempts"]: 0,
            config["state"]: "sent",
        })

        template = self.env.ref(config["template"], raise_if_not_found=False)
        if not template:
            _logger.warning("Signature code template not found party=%s", party)
            return {
                "ok": False,
                "message": "No se encontro la plantilla de correo para enviar el codigo.",
            }

        try:
            template.with_context(
                signature_code=code,
                signature_party_label=config["label"],
                signature_person_name=self[config["name_field"]] or config["label"],
                signature_code_ttl_minutes=SIGNATURE_CODE_TTL_MINUTES,
            ).sudo().send_mail(
                self.id,
                force_send=False,
                email_values={
                    "email_from": "reporte@impocoma.com",
                    "reply_to": "reporte@impocoma.com",
                    "email_to": email,
                    "recipient_ids": [(5, 0, 0)],
                },
            )
        except Exception:
            _logger.exception(
                "Signature code email failed submission_id=%s party=%s email=%s",
                self.id,
                party,
                email,
            )
            return {
                "ok": False,
                "message": "No pudimos enviar el codigo. Intenta nuevamente.",
            }

        self.message_post(body="Codigo de verificacion de firma enviado al %s: %s." % (config["label"], email))
        _logger.info(
            "Signature code email queued submission_id=%s party=%s email=%s expires_at=%s",
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
            self.write({
                config["attempts"]: attempts,
                config["state"]: state,
            })
            _logger.warning(
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

        self.write({
            config["verified_at"]: now,
            config["verified_ip"]: ip_address,
            config["attempts"]: attempts,
            config["state"]: "verified",
        })
        self.message_post(body="Correo de firma verificado para el %s: %s." % (config["label"], self[config["email"]]))
        _logger.info(
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
        return self._send_signature_code("owner")

    def verify_owner_signature_code(self, code, ip_address=None):
        return self._verify_signature_code("owner", code, ip_address=ip_address)

    def send_driver_signature_code(self):
        return self._send_signature_code("driver")

    def verify_driver_signature_code(self, code, ip_address=None):
        return self._verify_signature_code("driver", code, ip_address=ip_address)

    def action_open_printable(self):
        """Abre la hoja de vida imprimible desde la vista interna."""
        self.ensure_one()
        if not self.access_token:
            _logger.info("Generating printable access token submission_id=%s", self.id)
            self.access_token = uuid.uuid4().hex
        _logger.info("Opening printable action submission_id=%s user_id=%s", self.id, self.env.user.id)
        return {
            "type": "ir.actions.act_url",
            "name": "Hoja de Vida Imprimible",
            "url": f"/registro-conductor/imprimir/{self.id}?token={self.access_token}",
            "target": "new",
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Normaliza placas y ciudad del propietario antes de crear."""
        _logger.info("Creating risk submissions count=%s user_id=%s", len(vals_list), self.env.user.id)
        for vals in vals_list:
            if vals.get("vehicle_plate"):
                vals["vehicle_plate"] = self._normalize_plate(vals["vehicle_plate"])
            if vals.get("semi_trailer_plate"):
                vals["semi_trailer_plate"] = self._normalize_plate(vals["semi_trailer_plate"])
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
        """Normaliza placas y ciudad del propietario antes de escribir."""
        old_states = {record.id: record.state for record in self}
        _logger.debug(
            "Writing risk submissions ids=%s user_id=%s fields=%s",
            self.ids,
            self.env.user.id,
            sorted(vals.keys()),
        )
        if vals.get("vehicle_plate"):
            vals["vehicle_plate"] = self._normalize_plate(vals["vehicle_plate"])
        if vals.get("semi_trailer_plate"):
            vals["semi_trailer_plate"] = self._normalize_plate(vals["semi_trailer_plate"])
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
            lambda record: vals.get("state") == "submitted"
            and old_states.get(record.id) != "submitted"
            and record.submission_email_status != "sent"
        )
        if submitted_records:
            submitted_records.action_send_submission_received_email()
        return result
