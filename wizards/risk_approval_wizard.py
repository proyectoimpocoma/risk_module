import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RiskApprovalWizard(models.TransientModel):
    _name = "risk.approval.wizard"
    _description = "Decision manual de solicitud de riesgo"

    _REJECTION_MESSAGES = {
        "incomplete_documents": "No fue posible aprobar la solicitud porque aun falta informacion o documentos requeridos para completar la revision.",
        "documents_not_fixed": "La solicitud fue rechazada porque los documentos solicitados no fueron corregidos o cargados dentro del proceso de revision.",
        "inconsistent_information": "La informacion registrada presenta diferencias entre el formulario y los documentos adjuntos. Por favor revisa los datos antes de iniciar una nueva solicitud.",
        "identity_validation_failed": "No fue posible validar correctamente la identidad de la persona registrada en la solicitud.",
        "driver_not_approved": "El conductor registrado no cumple con los criterios requeridos para continuar con el proceso de habilitacion.",
        "owner_not_approved": "El propietario o tenedor registrado no cumple con los criterios requeridos para continuar con el proceso de habilitacion.",
        "vehicle_not_approved": "El vehiculo registrado no cumple con los criterios requeridos para continuar con el proceso de habilitacion.",
        "external_validation_failed": "El resultado de la validacion externa no permite continuar con la aprobacion de la solicitud.",
        "risk_alerts": "Durante la revision se identificaron alertas que impiden aprobar la solicitud en este momento.",
        "security_study_failed": "El estudio de seguridad asociado a la solicitud no fue aprobado.",
        "internal_policy": "La solicitud no cumple con las politicas internas definidas para la habilitacion de terceros.",
        "duplicate_or_expired": "La solicitud fue rechazada porque existe otra solicitud activa o porque la informacion registrada ya no se encuentra vigente.",
        "third_party_withdrawal": "La solicitud fue rechazada porque el tercero indico que no desea continuar con el proceso.",
        "contact_failed": "No fue posible confirmar informacion necesaria para continuar con la revision de la solicitud.",
        "other": "La solicitud fue rechazada por un motivo especifico indicado por el equipo de riesgo.",
    }
    _CORRECTION_MESSAGES = {
        "incomplete_documents": "Para continuar con la revision necesitamos que completes la informacion o documentos pendientes.",
        "documents_not_fixed": "Para continuar, por favor corrige o carga nuevamente los documentos indicados por el equipo de riesgo.",
        "inconsistent_information": "Encontramos diferencias entre la informacion registrada y los documentos adjuntos. Por favor revisa y corrige los datos indicados.",
        "identity_validation_failed": "Necesitamos que revises la informacion de identidad registrada para poder continuar con la validacion.",
        "driver_not_approved": "Necesitamos que revises la informacion del conductor indicada por el equipo de riesgo antes de continuar.",
        "owner_not_approved": "Necesitamos que revises la informacion del propietario o tenedor indicada por el equipo de riesgo.",
        "vehicle_not_approved": "Necesitamos que revises la informacion del vehiculo indicada por el equipo de riesgo.",
        "external_validation_failed": "La validacion externa requiere ajustes antes de poder continuar. Por favor revisa las observaciones indicadas.",
        "risk_alerts": "Durante la revision se identificaron alertas que requieren aclaracion. Por favor revisa las observaciones y corrige la informacion indicada.",
        "security_study_failed": "El estudio de seguridad requiere informacion adicional o correccion antes de continuar.",
        "internal_policy": "La solicitud requiere ajustes para cumplir con las politicas internas de habilitacion.",
        "duplicate_or_expired": "Necesitamos que revises la vigencia de la informacion registrada o si existe una solicitud activa relacionada.",
        "third_party_withdrawal": "Antes de continuar necesitamos confirmar si deseas seguir con el proceso de habilitacion.",
        "contact_failed": "No fue posible confirmar informacion necesaria. Por favor revisa los datos de contacto registrados.",
        "other": "La solicitud requiere una correccion especifica indicada por el equipo de riesgo.",
    }

    submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud",
        required=True,
        readonly=True,
    )
    decision = fields.Selection([
        ("approve", "Aprobar"),
        ("reject", "Rechazar definitivamente"),
        ("correction", "Devolver para correccion"),
    ], string="Decision", required=True, readonly=True)
    approval_note = fields.Text(string="Comentario de aprobacion")
    message_template_category = fields.Selection(
        [
            ("submission_rejection", "Rechazo definitivo"),
            ("submission_correction", "Solicitud de correccion"),
        ],
        string="Tipo de mensaje",
        compute="_compute_message_template_category",
    )
    message_template_id = fields.Many2one(
        "risk.message.template",
        string="Motivo",
        domain="[('category', '=', message_template_category), ('active', '=', True)]",
    )
    rejection_reason_code = fields.Selection(
        [
            ("incomplete_documents", "Documentacion incompleta"),
            ("documents_not_fixed", "Documentacion no subsanada"),
            ("inconsistent_information", "Informacion inconsistente"),
            ("identity_validation_failed", "Validacion de identidad no satisfactoria"),
            ("driver_not_approved", "Validacion del conductor no aprobada"),
            ("owner_not_approved", "Validacion del propietario o tenedor no aprobada"),
            ("vehicle_not_approved", "Validacion del vehiculo no aprobada"),
            ("external_validation_failed", "Validacion externa desfavorable"),
            ("risk_alerts", "Antecedentes o alertas de riesgo"),
            ("security_study_failed", "Estudio de seguridad no aprobado"),
            ("internal_policy", "No cumple politicas internas"),
            ("duplicate_or_expired", "Solicitud duplicada o no vigente"),
            ("third_party_withdrawal", "Desistimiento del tercero"),
            ("contact_failed", "No fue posible contactar o confirmar informacion"),
            ("other", "Otro motivo"),
        ],
        string="Motivo",
    )
    rejection_reason = fields.Text(string="Mensaje para el usuario")
    correction_section_vehicle = fields.Boolean(string="Vehiculo")
    correction_section_owner = fields.Boolean(string="Propietario")
    correction_section_driver = fields.Boolean(string="Conductor")
    correction_section_satellite = fields.Boolean(string="Satelital")
    correction_section_signatures = fields.Boolean(string="Firmas")
    correction_section_terms = fields.Boolean(string="Terminos")
    correction_section_other = fields.Boolean(string="Otro")

    @api.depends("decision")
    def _compute_message_template_category(self):
        for wizard in self:
            if wizard.decision == "correction":
                wizard.message_template_category = "submission_correction"
            elif wizard.decision == "reject":
                wizard.message_template_category = "submission_rejection"
            else:
                wizard.message_template_category = False

    def _rejection_message(self, reason_code):
        """
        Get the rejection message associated with a given reason code.
        
        Args:
            reason_code (str): The code of the rejection reason.
            
        Returns:
            str: The full rejection message from the template or default dictionary.
        """
        if self.decision == "correction":
            category = "submission_correction"
            default = self._CORRECTION_MESSAGES.get(reason_code or "")
        else:
            category = "submission_rejection"
            default = self._REJECTION_MESSAGES.get(reason_code or "")
        return self.env["risk.message.template"]._get_body(
            category,
            reason_code,
            default=default,
        )

    @api.onchange("rejection_reason_code")
    def _onchange_rejection_reason_code(self):
        for wizard in self:
            message = wizard._rejection_message(wizard.rejection_reason_code)
            if message:
                wizard.rejection_reason = message

    @api.onchange("message_template_id")
    def _onchange_message_template_id(self):
        for wizard in self:
            if not wizard.message_template_id:
                continue
            wizard.rejection_reason = wizard.message_template_id.body
            if wizard.message_template_id.code in wizard._submission_reason_codes():
                wizard.rejection_reason_code = wizard.message_template_id.code
            else:
                wizard.rejection_reason_code = False

    def _selected_template_message(self):
        self.ensure_one()
        if self.message_template_id:
            return (self.message_template_id.body or "").strip()
        return (self._rejection_message(self.rejection_reason_code) or "").strip()

    def _submission_reason_codes(self):
        return {
            code
            for code, _label in self._fields["rejection_reason_code"].selection
        }

    def action_confirm(self):
        """
        Confirm the decision made in the wizard and apply it to the submission.
        Validates required fields before executing approval or rejection.
        
        Returns:
            dict: An action to close the wizard window.
        """
        self.ensure_one()
        _logger.info(
            "Approval wizard confirmed submission_id=%s decision=%s user_id=%s",
            self.submission_id.id,
            self.decision,
            self.env.user.id,
        )
        if self.decision == "approve":
            self.submission_id.action_confirm_approval(self.approval_note)
        elif self.decision == "reject":
            if not self.message_template_id and not self.rejection_reason_code:
                raise ValidationError("Debes seleccionar un motivo de rechazo.")
            self.rejection_reason = self._selected_template_message()
            if not self.rejection_reason or not self.rejection_reason.strip():
                _logger.warning("Approval wizard rejection blocked missing reason submission_id=%s user_id=%s", self.submission_id.id, self.env.user.id)
                raise ValidationError("Debes indicar el mensaje de rechazo.")
            self.submission_id.action_confirm_rejection(self.rejection_reason.strip())
        else:
            if not self.message_template_id and not self.rejection_reason_code:
                raise ValidationError("Debes seleccionar un motivo de correccion.")
            if not (self.rejection_reason or "").strip():
                self.rejection_reason = self._rejection_message(
                    self.rejection_reason_code
                )
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValidationError("Debes indicar el mensaje de correccion.")
            self.submission_id.action_confirm_correction_request(
                self.rejection_reason.strip(),
                sections={
                    "vehicle": self.correction_section_vehicle,
                    "owner": self.correction_section_owner,
                    "driver": self.correction_section_driver,
                    "satellite": self.correction_section_satellite,
                    "signatures": self.correction_section_signatures,
                    "terms": self.correction_section_terms,
                    "other": self.correction_section_other,
                },
            )
        return {"type": "ir.actions.act_window_close"}
