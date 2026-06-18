from odoo import fields, models


class RiskSubmissionDocumentVersion(models.Model):
    """Historial de cargas de un documento.

    Se crea un registro por cada subida, reenvio o intento fallido, de forma
    que riesgo pueda ver dentro de Odoo toda la traza (quien, cuando, resultado
    y, en caso de reenvio, que rechazo lo origino) sin entrar a SharePoint.
    """

    _name = "risk.module.document.version"
    _description = "Historial de carga de documento de riesgo"
    _order = "create_date desc, id desc"

    document_id = fields.Many2one(
        "risk.module.document",
        string="Documento",
        required=True,
        ondelete="cascade",
        index=True,
    )
    submission_id = fields.Many2one(
        related="document_id.submission_id",
        string="Solicitud",
        store=True,
        index=True,
    )
    document_name = fields.Char(string="Documento", readonly=True)
    filename = fields.Char(string="Nombre de archivo", readonly=True)
    version_number = fields.Integer(string="Version", readonly=True)
    result = fields.Selection(
        [
            ("pending", "En proceso"),
            ("uploaded", "Subido"),
            ("failed", "Fallido"),
        ],
        string="Resultado",
        required=True,
        default="pending",
        readonly=True,
    )
    is_replacement = fields.Boolean(string="Reemplazo", readonly=True)
    triggered_by_rejection = fields.Selection(
        selection=lambda self: self.env["risk.module.document"]
        ._fields["rejection_reason"].selection,
        string="Rechazo que lo origino",
        readonly=True,
    )
    sharepoint_item_id = fields.Char(string="SharePoint item", readonly=True)
    sharepoint_web_url = fields.Char(string="Enlace SharePoint", readonly=True)
    error_message = fields.Text(string="Error", readonly=True)
    uploaded_by_id = fields.Many2one(
        "res.users",
        string="Cargado por",
        readonly=True,
        default=lambda self: self.env.user,
    )
    uploaded_at = fields.Datetime(
        string="Fecha",
        readonly=True,
        default=fields.Datetime.now,
    )
