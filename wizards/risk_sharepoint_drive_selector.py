from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RiskSharepointDriveSelector(models.TransientModel):
    _name = "risk.sharepoint.drive.selector"
    _description = "Seleccionar biblioteca y carpeta de SharePoint"

    stage = fields.Selection(
        [("drive", "Biblioteca"), ("folder", "Carpeta")],
        default="drive",
        required=True,
    )

    # ── Etapa 1: selección de drive ───────────────────────────────────────
    drive_id = fields.Selection(
        selection="_selection_drives",
        string="Biblioteca",
    )

    # ── Etapa 2: navegación de carpetas ───────────────────────────────────
    current_path = fields.Char(default="")
    folder_choice = fields.Selection(
        selection="_selection_folders",
        string="Carpeta",
    )
    path_display = fields.Char(
        string="Ubicación actual",
        compute="_compute_path_display",
    )

    # ── Selections ────────────────────────────────────────────────────────

    def _selection_drives(self):
        try:
            drives = self.env["risk.sharepoint.service"]._list_drives()
            return [(d["name"], d["name"]) for d in drives]
        except Exception as exc:
            return [("__error__", _("Error al cargar bibliotecas: %s") % exc)]

    def _selection_folders(self):
        if not self.drive_id or self.drive_id == "__error__":
            return []
        try:
            folders = self.env["risk.sharepoint.service"]._list_folders(
                self.drive_id, self.current_path or ""
            )
            return [(f, f) for f in folders]
        except Exception as exc:
            return [("__error__", _("Error: %s") % exc)]

    # ── Compute ───────────────────────────────────────────────────────────

    @api.depends("drive_id", "current_path")
    def _compute_path_display(self):
        for rec in self:
            parts = [rec.drive_id or ""] + [
                p for p in (rec.current_path or "").split("/") if p
            ]
            rec.path_display = " / ".join(parts) if any(parts) else "raíz"

    # ── Default get ───────────────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        get = self.env["ir.config_parameter"].sudo().get_param
        current_drive = get("risk_module.sp_drive") or ""
        current_folder = get("risk_module.sp_root_folder") or ""
        if "drive_id" in fields_list and current_drive:
            res["drive_id"] = current_drive
        if "current_path" in fields_list and current_folder:
            res["current_path"] = current_folder
        return res

    # ── Acciones de navegación ────────────────────────────────────────────

    def _reopen(self):
        """Reabre el mismo wizard para refrescar los campos Selection."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_next_stage(self):
        """Avanza de selección de drive a navegación de carpetas."""
        self.ensure_one()
        if not self.drive_id:
            raise UserError(_("Selecciona una biblioteca primero."))
        if self.drive_id == "__error__":
            raise UserError(_("No se pudo cargar la lista de bibliotecas. Verifica la configuración de SharePoint."))
        self.write({"stage": "folder", "current_path": "", "folder_choice": False})
        return self._reopen()

    def action_enter_folder(self):
        """Entra en la subcarpeta seleccionada."""
        self.ensure_one()
        if not self.folder_choice:
            raise UserError(_("Selecciona una carpeta para entrar."))
        if self.folder_choice == "__error__":
            raise UserError(_("No se pueden cargar las subcarpetas. Verifica la configuración."))
        base = self.current_path or ""
        new_path = "%s/%s" % (base, self.folder_choice) if base else self.folder_choice
        self.write({"current_path": new_path, "folder_choice": False})
        return self._reopen()

    def action_go_up(self):
        """Sube un nivel en la jerarquía de carpetas."""
        self.ensure_one()
        parts = [p for p in (self.current_path or "").split("/") if p]
        self.write({"current_path": "/".join(parts[:-1]), "folder_choice": False})
        return self._reopen()

    def action_confirm(self):
        """Guarda drive y carpeta raíz en los parámetros de configuración."""
        self.ensure_one()
        if self.stage == "drive":
            return self.action_next_stage()
        if not self.drive_id or self.drive_id == "__error__":
            raise UserError(_("No se ha seleccionado una biblioteca válida."))
        cfg = self.env["ir.config_parameter"].sudo()
        cfg.set_param("risk_module.sp_drive", self.drive_id)
        cfg.set_param("risk_module.sp_root_folder", self.current_path or "Solicitudes")
        from odoo.addons.risk_module.models.risk_sharepoint_service import _LOCATION_CACHE
        _LOCATION_CACHE.clear()
        return {"type": "ir.actions.act_window_close"}
