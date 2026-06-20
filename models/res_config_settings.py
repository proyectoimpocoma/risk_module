import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
    risk_sp_drive_id = fields.Char(
        string="Drive ID",
        config_parameter="risk_module.sp_drive_id",
        help="ID tecnico de la biblioteca obtenido desde Microsoft Graph.",
    )
    risk_sp_root_folder = fields.Char(
        string="Carpeta raiz",
        config_parameter="risk_module.sp_root_folder",
        default="Solicitudes",
        help="Carpeta raiz dentro de la biblioteca donde se crea el arbol de "
        "solicitudes.",
    )
    risk_sp_root_item_id = fields.Char(
        string="Item ID carpeta raiz",
        config_parameter="risk_module.sp_root_item_id",
        help="ID tecnico de la carpeta raiz donde se crearan las solicitudes.",
    )
    risk_sp_graph_children_url = fields.Char(
        string="URL Graph /children",
        config_parameter="risk_module.sp_graph_children_url",
        help="URL copiada desde Graph Explorer para una carpeta: "
        "https://graph.microsoft.com/v1.0/drives/<drive_id>/items/<item_id>/children",
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
            _("Conexion correcta. Drive %s, carpeta %s.")
            % (info["drive_id"], info["root_item_id"])
        )

    def action_risk_sp_apply_graph_url(self):
        """Guarda drive_id/item_id desde una URL /children de Graph Explorer."""
        self.ensure_one()
        service = self.env["risk.sharepoint.service"]
        parsed = service._parse_children_url(self.risk_sp_graph_children_url)
        _logger.info(
            "SharePoint settings apply Graph URL drive_id=%s item_id=%s user_id=%s",
            parsed["drive_id"],
            parsed["item_id"],
            self.env.user.id,
        )
        cfg = self.env["ir.config_parameter"].sudo()
        cfg.set_param("risk_module.sp_drive_id", parsed["drive_id"])
        cfg.set_param("risk_module.sp_root_item_id", parsed["item_id"])
        try:
            drive_name = service._get_drive_name(parsed["drive_id"])
        except Exception:
            drive_name = self.risk_sp_drive or parsed["drive_id"]
        cfg.set_param("risk_module.sp_drive", drive_name)
        cfg.set_param(
            "risk_module.sp_root_folder",
            self.risk_sp_root_folder or "Solicitudes",
        )
        from odoo.addons.risk_module.models.risk_sharepoint_service import _LOCATION_CACHE

        _LOCATION_CACHE.clear()
        return self._notify(
            _("URL aplicada. Drive %s, carpeta %s.")
            % (parsed["drive_id"], parsed["item_id"])
        )

    def action_risk_sp_explore_graph_url(self):
        """Abre el explorador de carpetas desde la URL /children ingresada."""
        self.ensure_one()
        graph_url = self.risk_sp_graph_children_url
        if not graph_url:
            raise UserError(_("Pega primero la URL Graph /children."))
        parsed = self.env["risk.sharepoint.service"]._parse_children_url(graph_url)
        _logger.info(
            "SharePoint settings open explorer from Graph URL drive_id=%s item_id=%s user_id=%s",
            parsed["drive_id"],
            parsed["item_id"],
            self.env.user.id,
        )
        wizard = self.env["risk.sharepoint.drive.selector"].with_context(
            graph_children_url=graph_url
        ).create({})
        return {
            "type": "ir.actions.act_window",
            "name": _("Explorar carpeta SharePoint"),
            "res_model": "risk.sharepoint.drive.selector",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_risk_sp_test_root_folder(self):
        """Valida acceso de lectura a la carpeta raiz configurada."""
        self.ensure_one()
        try:
            info = self.env["risk.sharepoint.service"]._test_root_folder()
        except Exception as exc:  # noqa: BLE001 - mostramos el error al usuario
            raise UserError(_("No se pudo acceder a la carpeta: %s") % exc)
        return self._notify(
            _("Carpeta accesible. Drive %s, carpeta %s.")
            % (info["drive_id"], info["item_id"])
        )

    def action_risk_sp_select_drive(self):
        """Abre el asistente para seleccionar la biblioteca de SharePoint."""
        self.ensure_one()
        wizard = self.env["risk.sharepoint.drive.selector"].create({})
        return {
            "type": "ir.actions.act_window",
            "name": _("Seleccionar biblioteca"),
            "res_model": "risk.sharepoint.drive.selector",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
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
