from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .risk_sharepoint_service import TEMPLATE_TOKENS, TOKEN_RE


class RiskSharepointRoute(models.Model):
    """Configuracion autogestionable de ruta y nombre por tipo de documento.

    Una fila por ``party``. Todas las rutas cuelgan de la carpeta raiz global
    (``sp_root_item_id``); aqui solo se define el arbol de subcarpetas y el
    nombre del archivo mediante plantillas con variables ``{token}``.
    """

    _name = "risk.sharepoint.route"
    _description = "Ruta de SharePoint por tipo de documento"
    _order = "party"

    party = fields.Selection(
        [
            ("driver", "Conductor"),
            ("owner", "Propietario"),
            ("vehicle", "Vehiculo"),
            ("semi_trailer", "Semi/Remolque"),
            ("other", "Otro"),
        ],
        string="Tipo",
        required=True,
    )
    folder_template = fields.Char(
        string="Plantilla de carpeta",
        required=True,
        default="{ref} {placa}/{tipo}",
        help="Subcarpetas dentro de la carpeta raiz. Usa / para anidar y "
        "variables como {placa} o {propietario}.",
    )
    filename_template = fields.Char(
        string="Plantilla de nombre",
        required=True,
        default="{documento}",
        help="Nombre del archivo sin extension; la original se conserva.",
    )
    append_id = fields.Boolean(
        string="Anadir (id) al nombre",
        default=True,
        help="Garantiza nombres unicos cuando un documento tiene varios "
        "archivos en la misma carpeta.",
    )
    active = fields.Boolean(default=True)

    # ── Vista previa (campos no almacenados, solo para el formulario) ──
    preview_submission_id = fields.Many2one(
        "risk.module",
        string="Solicitud de ejemplo",
        store=False,
        help="Elige una solicitud para ver la ruta y el nombre resultantes.",
    )
    preview_document_type = fields.Selection(
        selection="_selection_preview_document_type",
        string="Documento de ejemplo",
        store=False,
    )
    preview_folder = fields.Char(
        string="Carpeta resultante", compute="_compute_preview", store=False
    )
    preview_filename = fields.Char(
        string="Nombre resultante", compute="_compute_preview", store=False
    )
    tokens_help = fields.Html(
        string="Variables disponibles", compute="_compute_tokens_help", sanitize=False
    )

    _sql_constraints = [
        ("party_uniq", "unique(party)", "Ya existe una ruta para este tipo."),
    ]

    def _selection_preview_document_type(self):
        return self.env["risk.module.document"]._fields["document_type"].selection

    def _compute_tokens_help(self):
        rows = "".join(
            "<tr><td class='pe-3'><code>{%s}</code></td><td>%s</td></tr>"
            % (token, label)
            for token, label in TEMPLATE_TOKENS.items()
        )
        html = (
            "<table class='table table-sm o_main_table'><tbody>%s</tbody></table>"
            % rows
        )
        for rec in self:
            rec.tokens_help = html

    @api.depends(
        "folder_template",
        "filename_template",
        "append_id",
        "party",
        "preview_submission_id",
        "preview_document_type",
    )
    def _compute_preview(self):
        service = self.env["risk.sharepoint.service"]
        doc_selection = dict(
            self.env["risk.module.document"]._fields["document_type"].selection
        )
        party_selection = dict(self._fields["party"].selection)
        root_folder = service._config().get("root_folder") or ""
        for rec in self:
            submission = rec.preview_submission_id
            if not submission:
                rec.preview_folder = ""
                rec.preview_filename = ""
                continue
            doc_label = (
                doc_selection.get(rec.preview_document_type, rec.preview_document_type)
                if rec.preview_document_type
                else "Documento"
            )
            ctx = service._build_token_context(
                submission,
                party_label=party_selection.get(rec.party, rec.party or ""),
                doc_label=doc_label,
                rec_id=submission.id,
            )
            segments = service._render_path_segments(rec.folder_template, ctx)
            full = ([root_folder] if root_folder else []) + segments
            rec.preview_folder = "/".join(full)
            rec.preview_filename = service._apply_filename_template(
                rec.filename_template,
                ctx,
                "documento.pdf",
                append_id=rec.append_id,
                rec_id=submission.id,
            )

    @api.constrains("folder_template", "filename_template")
    def _check_templates(self):
        """Rechaza plantillas con variables fuera de la lista blanca."""
        valid = set(TEMPLATE_TOKENS)
        for rec in self:
            for template in (rec.folder_template, rec.filename_template):
                unknown = [
                    tok for tok in TOKEN_RE.findall(template or "")
                    if tok not in valid
                ]
                if unknown:
                    raise ValidationError(
                        _(
                            "Variables desconocidas: %(unknown)s.\n"
                            "Disponibles: %(valid)s"
                        )
                        % {
                            "unknown": ", ".join("{%s}" % u for u in unknown),
                            "valid": ", ".join(
                                "{%s}" % t for t in sorted(valid)
                            ),
                        }
                    )

    @api.model
    def _route_for_party(self, party):
        """Devuelve la ruta activa para un ``party``, o un recordset vacio.

        El ``active_test`` por defecto omite las rutas desactivadas, de modo
        que un tipo sin ruta activa cae al comportamiento clasico.
        """
        return self.search([("party", "=", party)], limit=1)
