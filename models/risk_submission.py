import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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
    driver_has_valid_study = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Conductor con estudio vigente")
    driver_signature = fields.Binary(string="Firma conductor")
    driver_signature_document = fields.Char(string="Cedula firma conductor")
    driver_signed_at = fields.Datetime(string="Fecha firma conductor")
    driver_signature_ip = fields.Char(string="IP firma conductor")
    driver_signature_user_agent = fields.Text(string="Navegador firma conductor")
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
        return result
