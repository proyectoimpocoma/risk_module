from odoo import _, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Parametros de integracion con SharePoint (Microsoft Graph, app-only).
    # Persistidos en ir.config_parameter via el atajo config_parameter.
    risk_sp_enabled = fields.Boolean(
        string="Guardar documentos en SharePoint",
        config_parameter="risk_module.sp_enabled",
        help="Si esta desactivado, los documentos se guardan solo en Odoo "
        "(comportamiento clasico) y no se sincronizan con SharePoint.",
    )
    risk_sp_tenant_id = fields.Char(
        string="Tenant ID (Azure AD)",
        config_parameter="risk_module.sp_tenant_id",
    )
    risk_sp_client_id = fields.Char(
        string="Client ID (App registrada)",
        config_parameter="risk_module.sp_client_id",
    )
    risk_sp_client_secret = fields.Char(
        string="Client Secret",
        config_parameter="risk_module.sp_client_secret",
    )
    risk_sp_site = fields.Char(
        string="Sitio de SharePoint",
        config_parameter="risk_module.sp_site",
        help="Host y ruta del sitio, por ejemplo: "
        "contoso.sharepoint.com:/sites/Riesgos",
    )
    risk_sp_drive = fields.Char(
        string="Biblioteca de documentos",
        config_parameter="risk_module.sp_drive",
        help="Nombre de la biblioteca (drive). Si se deja vacio se usa la "
        "biblioteca por defecto del sitio.",
    )
    risk_sp_root_folder = fields.Char(
        string="Carpeta raiz",
        config_parameter="risk_module.sp_root_folder",
        default="Solicitudes",
        help="Carpeta raiz dentro de la biblioteca donde se crea el arbol de "
        "solicitudes.",
    )
    risk_sp_purge_local = fields.Boolean(
        string="Eliminar copia local tras subir",
        config_parameter="risk_module.sp_purge_local",
        default=True,
        help="Si esta activo, el archivo se borra de Odoo una vez confirmada "
        "la subida a SharePoint (modo solo-referencia).",
    )
    risk_sp_max_attempts = fields.Integer(
        string="Maximo de intentos de sincronizacion",
        config_parameter="risk_module.sp_max_attempts",
        default=5,
        help="Numero maximo de reintentos antes de dejar un documento en "
        "estado de error para revision manual.",
    )

    def _notify(self, message, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SharePoint"),
                "message": message,
                "type": kind,
                "sticky": kind == "danger",
            },
        }

    def action_risk_sp_test_connection(self):
        """Resuelve sitio y biblioteca para validar credenciales/permisos."""
        self.ensure_one()
        try:
            info = self.env["risk.sharepoint.service"]._test_connection()
        except Exception as exc:  # noqa: BLE001 - mostramos el error al usuario
            raise UserError(_("No se pudo conectar con SharePoint: %s") % exc)
        return self._notify(
            _("Conexion correcta. Sitio resuelto (drive %s).") % info["drive_id"]
        )

    def action_risk_sp_select_drive(self):
        """Abre el asistente para seleccionar la biblioteca de SharePoint."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Seleccionar biblioteca"),
            "res_model": "risk.sharepoint.drive.selector",
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_risk_sp_backfill(self):
        """Marca los documentos existentes con archivo para subirlos al cron."""
        self.ensure_one()
        docs = self.env["risk.module.document"].search(
            [
                ("file", "!=", False),
                ("sharepoint_state", "in", ("disabled", False)),
            ]
        )
        docs.write({"sharepoint_state": "pending", "sharepoint_attempts": 0})
        return self._notify(
            _("%s documentos marcados para sincronizar con SharePoint.") % len(docs)
        )
