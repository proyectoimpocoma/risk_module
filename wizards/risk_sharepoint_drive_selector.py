from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RiskSharepointDriveSelector(models.TransientModel):
    _name = "risk.sharepoint.drive.selector"
    _description = "Seleccionar biblioteca de SharePoint"

    drive_id = fields.Selection(
        selection="_selection_drives",
        string="Biblioteca",
        required=True,
    )
    drive_name = fields.Char(string="Nombre de la biblioteca", readonly=True)

    def _selection_drives(self):
        try:
            drives = self.env["risk.sharepoint.service"]._list_drives()
            return [(d["name"], d["name"]) for d in drives]
        except Exception as exc:
            return [("__error__", _("Error al cargar bibliotecas: %s") % exc)]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        current = (
            self.env["ir.config_parameter"].sudo().get_param("risk_module.sp_drive") or ""
        )
        if "drive_id" in fields_list and current:
            res["drive_id"] = current
        return res

    @api.onchange("drive_id")
    def _onchange_drive_id(self):
        self.drive_name = self.drive_id or ""

    def action_confirm(self):
        self.ensure_one()
        if self.drive_id == "__error__":
            raise UserError(_("No se pudo cargar la lista de bibliotecas. Verifica la configuración de SharePoint."))
        self.env["ir.config_parameter"].sudo().set_param(
            "risk_module.sp_drive", self.drive_id or ""
        )
        # Invalidate location cache so next operation uses the new drive.
        from odoo.addons.risk_module.models.risk_sharepoint_service import _LOCATION_CACHE
        _LOCATION_CACHE.clear()
        return {"type": "ir.actions.act_window_close"}
