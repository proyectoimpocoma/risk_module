from odoo import api, fields, models


DOCUMENT_TYPE_SELECTION = [
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
]

PARTY_SELECTION = [
    ("driver", "Conductor"),
    ("owner", "Propietario"),
    ("vehicle", "Vehiculo"),
    ("semi_trailer", "Semi/Remolque"),
    ("other", "Otro"),
]

APPLIES_WHEN_SELECTION = [
    ("always", "Siempre"),
    ("owner_natural", "Propietario persona natural"),
    ("owner_company", "Propietario juridico"),
    ("semi_trailer", "Tiene semi/remolque"),
    ("owner_driver_different", "Propietario y conductor diferentes"),
    ("owner_valid_study", "Propietario con estudio vigente"),
    ("driver_valid_study", "Conductor con estudio vigente"),
]


class RiskDocumentRequirement(models.Model):
    _name = "risk.document.requirement"
    _description = "Configuracion de documentos requeridos"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    name = fields.Char(string="Documento", required=True)
    document_type = fields.Selection(
        DOCUMENT_TYPE_SELECTION,
        string="Tipo",
        required=True,
        default="other",
    )
    party = fields.Selection(
        PARTY_SELECTION,
        string="Relacionado con",
        required=True,
        default="other",
    )
    required = fields.Boolean(string="Obligatorio", default=True)
    applies_when = fields.Selection(
        APPLIES_WHEN_SELECTION,
        string="Aplica cuando",
        required=True,
        default="always",
    )
    skip_when_owner_driver_same = fields.Boolean(
        string="Omitir si propietario y conductor son el mismo"
    )
    applies_driver = fields.Boolean(string="Conductor")
    applies_vehicle = fields.Boolean(string="Vehiculo")
    applies_owner_natural = fields.Boolean(string="Propietario natural")
    applies_owner_company = fields.Boolean(string="Propietario juridico")
    applies_semi_trailer = fields.Boolean(string="Semi/Remolque")
    applies_owner_valid_study = fields.Boolean(string="Estudio propietario")
    applies_driver_valid_study = fields.Boolean(string="Estudio conductor")
    validity_required = fields.Boolean(string="Requiere vencimiento")
    issue_date_required = fields.Boolean(string="Requiere fecha de expedicion")
    reject_expired = fields.Boolean(string="No aceptar vencidos", default=True)
    max_age_days = fields.Integer(string="Antiguedad maxima en dias")
    max_file_size_mb = fields.Float(string="Tamano maximo MB", default=10.0)
    allow_multiple_files = fields.Boolean(string="Permitir multiples archivos")
    max_files = fields.Integer(string="Maximo de archivos", default=1)
    allowed_file_extensions = fields.Char(
        string="Extensiones permitidas",
        default="pdf,jpg,jpeg,png",
        help="Separar por coma, por ejemplo: pdf,jpg,jpeg,png",
    )
    requires_color = fields.Boolean(string="Debe estar a color")
    requires_both_sides = fields.Boolean(string="Requiere ambas caras")
    instructions = fields.Text(string="Instrucciones")

    @api.depends("name", "party")
    def _compute_display_name(self):
        party_labels = dict(PARTY_SELECTION)
        for record in self:
            record.display_name = "%s - %s" % (
                record.name or "",
                party_labels.get(record.party, record.party),
            )

    def _applies_to_submission(self, submission):
        self.ensure_one()
        if self.skip_when_owner_driver_same and submission._same_owner_and_driver_person():
            return False
        if self.applies_when == "always":
            return True
        if self.applies_when == "owner_natural":
            return submission.owner_document_type != "nit"
        if self.applies_when == "owner_company":
            return submission.owner_document_type == "nit"
        if self.applies_when == "semi_trailer":
            return bool(submission.semi_trailer_plate)
        if self.applies_when == "owner_driver_different":
            return not submission._same_owner_and_driver_person()
        if self.applies_when == "owner_valid_study":
            return submission.owner_has_valid_study == "yes"
        if self.applies_when == "driver_valid_study":
            return submission.driver_has_valid_study == "yes"
        return False

    def _to_document_template(self):
        self.ensure_one()
        return {
            "document_type": self.document_type,
            "name": self.name,
            "party": self.party,
            "sequence": self.sequence,
            "required": self.required,
            "validity_required": self.validity_required,
            "issue_date_required": self.issue_date_required,
            "reject_expired": self.reject_expired,
            "max_age_days": self.max_age_days,
            "max_file_size_mb": self.max_file_size_mb,
            "allow_multiple_files": self.allow_multiple_files,
            "max_files": self.max_files or 1,
            "allowed_file_extensions": self.allowed_file_extensions,
            "requires_color": self.requires_color,
            "requires_both_sides": self.requires_both_sides,
            "instructions": self.instructions,
        }
