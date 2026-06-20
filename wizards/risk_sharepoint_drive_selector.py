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
    current_item_id = fields.Char(default="")   # item_id del directorio actual
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
            svc = self.env["risk.sharepoint.service"]
            if self.current_item_id:
                drive_id = svc._drive_id_by_name(self.drive_id)
                folders = svc._list_folders_by_item(drive_id, self.current_item_id)
                return [(f["name"], f["name"]) for f in folders]
            folders = svc._list_folders(self.drive_id, self.current_path or "")
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
            rec.path_display = " / ".join(p for p in parts if p) or "raíz"

    # ── Default get ───────────────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        get = self.env["ir.config_parameter"].sudo().get_param
        saved_drive = get("risk_module.sp_drive") or ""
        saved_folder = get("risk_module.sp_root_folder") or ""
        saved_item_id = get("risk_module.sp_root_item_id") or ""

        if saved_drive and saved_item_id:
            # Ya hay una ubicación guardada: abrir directamente en etapa carpeta
            res.update({
                "stage": "folder",
                "drive_id": saved_drive,
                "current_path": saved_folder,
                "current_item_id": saved_item_id,
            })
        elif saved_drive:
            res["drive_id"] = saved_drive
            if saved_folder:
                res["current_path"] = saved_folder
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
            raise UserError(_("No se pudo cargar la lista de bibliotecas. Verifica la configuración."))
        svc = self.env["risk.sharepoint.service"]
        root_item_id, _drive_id = svc._get_drive_root_item_id(self.drive_id)
        self.write({
            "stage": "folder",
            "current_path": "",
            "current_item_id": root_item_id,
            "folder_choice": False,
        })
        return self._reopen()

    def action_enter_folder(self):
        """Entra en la subcarpeta seleccionada y actualiza el item_id."""
        self.ensure_one()
        if not self.folder_choice:
            raise UserError(_("Selecciona una carpeta para entrar."))
        if self.folder_choice == "__error__":
            raise UserError(_("No se pueden cargar las subcarpetas. Verifica la configuración."))
        svc = self.env["risk.sharepoint.service"]
        drive_id = svc._drive_id_by_name(self.drive_id)
        child_item_id = svc._get_child_item_id(drive_id, self.current_item_id, self.folder_choice)
        base = self.current_path or ""
        new_path = "%s/%s" % (base, self.folder_choice) if base else self.folder_choice
        self.write({
            "current_path": new_path,
            "current_item_id": child_item_id,
            "folder_choice": False,
        })
        return self._reopen()

    def action_go_up(self):
        """Sube un nivel y recupera el item_id del directorio padre."""
        self.ensure_one()
        parts = [p for p in (self.current_path or "").split("/") if p]
        new_path = "/".join(parts[:-1])
        svc = self.env["risk.sharepoint.service"]
        drive_id = svc._drive_id_by_name(self.drive_id)
        parent_item_id = svc._get_item_parent_id(drive_id, self.current_item_id) or ""
        self.write({
            "current_path": new_path,
            "current_item_id": parent_item_id,
            "folder_choice": False,
        })
        return self._reopen()

    def action_confirm(self):
        """Guarda drive, carpeta raíz e item_id en los parámetros de configuración."""
        self.ensure_one()
        if self.stage == "drive":
            return self.action_next_stage()
        if not self.drive_id or self.drive_id == "__error__":
            raise UserError(_("No se ha seleccionado una biblioteca válida."))

        # Si por alguna razón no tenemos item_id (ej. config migrada), resolverlo ahora.
        item_id = self.current_item_id
        if not item_id:
            svc = self.env["risk.sharepoint.service"]
            try:
                item_id, _drive_id = svc._resolve_item_id_for_path(
                    self.drive_id, self.current_path or ""
                )
            except Exception:
                item_id = ""

        cfg = self.env["ir.config_parameter"].sudo()
        cfg.set_param("risk_module.sp_drive", self.drive_id)
        cfg.set_param("risk_module.sp_root_folder", self.current_path or "Solicitudes")
        if item_id:
            cfg.set_param("risk_module.sp_root_item_id", item_id)
        from odoo.addons.risk_module.models.risk_sharepoint_service import _LOCATION_CACHE
        _LOCATION_CACHE.clear()
        return {"type": "ir.actions.act_window_close"}
