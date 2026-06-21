import base64
import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RiskSharepointDriveSelectorLine(models.TransientModel):
    _name = "risk.sharepoint.drive.selector.line"
    _description = "Elemento del explorador de SharePoint"
    _order = "sequence, name"

    wizard_id = fields.Many2one(
        "risk.sharepoint.drive.selector",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    item_id = fields.Char(required=True)
    item_type = fields.Selection(
        [("folder", "Carpeta"), ("file", "Archivo")],
        required=True,
    )
    is_folder = fields.Boolean()
    is_file = fields.Boolean()
    # Tamaño en bytes. Las carpetas de SharePoint pueden superar el límite de
    # int4 (~2.1 GB), así que usamos Float (columna numérica) para evitar el
    # error "integer out of range" al insertar.
    size = fields.Float(digits=(20, 0))
    web_url = fields.Char()

    def action_open_folder(self):
        self.ensure_one()
        if not self.is_folder:
            raise UserError(_("Solo puedes entrar en carpetas."))
        return self.wizard_id._enter_child_folder(self.item_id, self.name)

    def action_open_file(self):
        self.ensure_one()
        if not self.web_url:
            raise UserError(_("Este archivo no tiene enlace de SharePoint."))
        return {
            "type": "ir.actions.act_url",
            "url": self.web_url,
            "target": "new",
        }


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
    selected_drive_id = fields.Char()

    # ── Etapa 2: navegación de carpetas ───────────────────────────────────
    current_path = fields.Char(default="")
    current_item_id = fields.Char(default="")   # item_id del directorio actual
    line_ids = fields.One2many(
        "risk.sharepoint.drive.selector.line",
        "wizard_id",
        string="Elementos",
    )
    explorer_message = fields.Text(
        string="Estado del explorador",
        readonly=True,
    )
    folder_choice = fields.Selection(
        selection="_selection_folders",
        string="Carpeta",
    )
    path_display = fields.Char(
        string="Ubicación actual",
        compute="_compute_path_display",
    )
    directory_summary = fields.Text(
        string="Resumen técnico",
        compute="_compute_directory_summary",
    )
    folder_count = fields.Integer(
        string="Carpetas",
        compute="_compute_directory_summary",
    )
    file_count = fields.Integer(
        string="Archivos",
        compute="_compute_directory_summary",
    )
    new_folder_name = fields.Char(string="Nueva carpeta")
    test_file = fields.Binary(string="Archivo de prueba")
    test_filename = fields.Char(string="Nombre archivo prueba")
    test_upload_item_id = fields.Char(string="Item prueba", readonly=True)
    test_upload_web_url = fields.Char(string="Enlace prueba", readonly=True)
    test_upload_message = fields.Text(string="Resultado prueba", readonly=True)

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
                technical_drive_id = self._current_drive_id()
                folders = svc._list_folders_by_item(
                    technical_drive_id, self.current_item_id
                )
                return [(f["id"], f["name"]) for f in folders]
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

    @api.depends("drive_id", "selected_drive_id", "current_item_id")
    def _compute_directory_summary(self):
        for rec in self:
            rec.directory_summary = ""
            rec.folder_count = 0
            rec.file_count = 0
            if rec.stage != "folder" or not rec.current_item_id:
                continue
            try:
                children = rec.env["risk.sharepoint.service"]._list_children_by_item(
                    rec._current_drive_id(), rec.current_item_id
                )
            except Exception as exc:  # noqa: BLE001 - visible para autogestion
                rec.directory_summary = _("No se pudo listar la carpeta: %s") % exc
                _logger.exception(
                    "SharePoint explorer list folder failed drive_id=%s item_id=%s",
                    rec.selected_drive_id or rec.drive_id,
                    rec.current_item_id,
                )
                continue
            folders = [item for item in children if item["is_folder"]]
            files = [item for item in children if item["is_file"]]
            rec.folder_count = len(folders)
            rec.file_count = len(files)
            lines = []
            if folders:
                lines.append(_("Carpetas:"))
                lines.extend("  [DIR] %s" % item["name"] for item in folders)
            if files:
                if lines:
                    lines.append("")
                lines.append(_("Archivos:"))
                lines.extend(
                    "  [FILE] %s (%s bytes)" % (item["name"], item["size"])
                    for item in files
                )
            rec.directory_summary = "\n".join(lines) or _("La carpeta está vacía.")

    # ── Default get ───────────────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        get = self.env["ir.config_parameter"].sudo().get_param
        saved_drive = get("risk_module.sp_drive") or ""
        saved_drive_id = get("risk_module.sp_drive_id") or ""
        saved_folder = get("risk_module.sp_root_folder") or ""
        saved_item_id = get("risk_module.sp_root_item_id") or ""
        graph_url = self.env.context.get("graph_children_url")

        route_id = self.env.context.get("route_id")
        if route_id:
            route = self.env["risk.sharepoint.route"].browse(route_id)
            if route.exists() and route.dest_item_id and route.dest_drive_id:
                svc = self.env["risk.sharepoint.service"]
                try:
                    drive_name = svc._get_drive_name(route.dest_drive_id)
                except Exception:
                    drive_name = saved_drive or route.dest_drive_id
                res.update({
                    "stage": "folder",
                    "drive_id": drive_name,
                    "selected_drive_id": route.dest_drive_id,
                    "current_path": "",
                    "current_item_id": route.dest_item_id,
                })
                return res

        if graph_url:
            svc = self.env["risk.sharepoint.service"]
            parsed = svc._parse_children_url(graph_url)
            try:
                drive_name = svc._get_drive_name(parsed["drive_id"])
            except Exception:
                drive_name = saved_drive or parsed["drive_id"]
            res.update({
                "stage": "folder",
                "drive_id": drive_name,
                "selected_drive_id": parsed["drive_id"],
                "current_path": saved_folder,
                "current_item_id": parsed["item_id"],
            })
        elif saved_drive and saved_item_id:
            # Ya hay una ubicación guardada: abrir directamente en etapa carpeta
            res.update({
                "stage": "folder",
                "drive_id": saved_drive,
                "selected_drive_id": saved_drive_id,
                "current_path": saved_folder,
                "current_item_id": saved_item_id,
            })
        elif saved_drive:
            res["drive_id"] = saved_drive
            res["selected_drive_id"] = saved_drive_id
            if saved_folder:
                res["current_path"] = saved_folder
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._refresh_lines()
        return records

    def _current_drive_id(self):
        self.ensure_one()
        if self.selected_drive_id:
            return self.selected_drive_id
        return self.env["risk.sharepoint.service"]._drive_id_by_name(self.drive_id)

    def _folder_name_from_choice(self, drive_id, item_id):
        self.ensure_one()
        if not self.current_item_id:
            return item_id
        children = self.env["risk.sharepoint.service"]._list_children_by_item(
            drive_id, self.current_item_id
        )
        for child in children:
            if child["is_folder"] and child["id"] == item_id:
                return child["name"]
        raise UserError(_("La carpeta seleccionada ya no existe o no es accesible."))

    def _refresh_lines(self):
        self.ensure_one()
        self.line_ids.unlink()
        message = ""
        if self.stage != "folder" or not self.current_item_id:
            self.explorer_message = message
            return
        drive_id = self._current_drive_id()
        _logger.info(
            "SharePoint explorer refresh lines drive_id=%s item_id=%s path=%s",
            drive_id,
            self.current_item_id,
            self.current_path,
        )
        try:
            children = self.env["risk.sharepoint.service"]._list_children_by_item(
                drive_id, self.current_item_id
            )
        except Exception as exc:  # noqa: BLE001 - mensaje visible al usuario
            _logger.exception(
                "SharePoint explorer refresh lines failed drive_id=%s item_id=%s",
                drive_id,
                self.current_item_id,
            )
            self.explorer_message = _("No se pudo cargar esta carpeta: %s") % exc
            return
        vals_list = []
        for index, item in enumerate(children, start=1):
            is_folder = bool(item["is_folder"])
            vals_list.append({
                "wizard_id": self.id,
                "sequence": index,
                "name": item["name"],
                "item_id": item["id"],
                "item_type": "folder" if is_folder else "file",
                "is_folder": is_folder,
                "is_file": bool(item["is_file"]),
                "size": item["size"],
                "web_url": item["web_url"],
            })
        if vals_list:
            self.env["risk.sharepoint.drive.selector.line"].create(vals_list)
        folders = len([item for item in children if item["is_folder"]])
        files = len([item for item in children if item["is_file"]])
        if folders:
            message = _(
                "Selecciona Abrir en una carpeta para navegar. Cuando estés en la ubicación correcta, usa Seleccionar esta carpeta."
            )
        elif files:
            message = _(
                "Esta ubicación solo contiene archivos. Puedes seleccionarla como carpeta destino o subir un nivel."
            )
        else:
            message = _(
                "Esta carpeta está vacía. Puedes seleccionarla como destino o crear una subcarpeta."
            )
        self.explorer_message = message
        _logger.info(
            "SharePoint explorer refresh lines ok drive_id=%s item_id=%s folders=%s files=%s",
            drive_id,
            self.current_item_id,
            folders,
            files,
        )

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

    def _enter_child_folder(self, child_item_id, folder_name):
        self.ensure_one()
        technical_drive_id = self._current_drive_id()
        _logger.info(
            "SharePoint explorer enter folder drive_id=%s current_item_id=%s folder=%s selected_item_id=%s user_id=%s",
            technical_drive_id,
            self.current_item_id,
            folder_name,
            child_item_id,
            self.env.user.id,
        )
        base = self.current_path or ""
        new_path = "%s/%s" % (base, folder_name) if base else folder_name
        self.write({
            "current_path": new_path,
            "current_item_id": child_item_id,
            "folder_choice": False,
        })
        self._refresh_lines()
        return self._reopen()

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
            "selected_drive_id": _drive_id,
            "current_path": "",
            "current_item_id": root_item_id,
            "folder_choice": False,
        })
        self._refresh_lines()
        return self._reopen()

    def action_enter_folder(self):
        """Entra en la subcarpeta seleccionada y actualiza el item_id."""
        self.ensure_one()
        if not self.folder_choice:
            raise UserError(_("Selecciona una carpeta para entrar."))
        if self.folder_choice == "__error__":
            raise UserError(_("No se pueden cargar las subcarpetas. Verifica la configuración."))
        svc = self.env["risk.sharepoint.service"]
        technical_drive_id = self._current_drive_id()
        folder_name = self._folder_name_from_choice(
            technical_drive_id, self.folder_choice
        )
        if self.current_item_id:
            child_item_id = self.folder_choice
        else:
            child_item_id = svc._get_child_item_id(
                technical_drive_id, self.current_item_id, folder_name
            )
        return self._enter_child_folder(child_item_id, folder_name)

    def action_go_up(self):
        """Sube un nivel y recupera el item_id del directorio padre."""
        self.ensure_one()
        parts = [p for p in (self.current_path or "").split("/") if p]
        new_path = "/".join(parts[:-1])
        svc = self.env["risk.sharepoint.service"]
        technical_drive_id = self._current_drive_id()
        _logger.info(
            "SharePoint explorer go up drive_id=%s current_item_id=%s path=%s",
            technical_drive_id,
            self.current_item_id,
            self.current_path,
        )
        parent_item_id = svc._get_item_parent_id(
            technical_drive_id, self.current_item_id
        )
        if not parent_item_id:
            raise UserError(_("Ya estás en la raíz de la biblioteca."))
        self.write({
            "current_path": new_path,
            "current_item_id": parent_item_id,
            "folder_choice": False,
        })
        self._refresh_lines()
        return self._reopen()

    def action_refresh(self):
        self.ensure_one()
        _logger.info(
            "SharePoint explorer refresh drive_id=%s item_id=%s path=%s",
            self._current_drive_id() if self.drive_id else "",
            self.current_item_id,
            self.current_path,
        )
        self.folder_choice = False
        self._refresh_lines()
        return self._reopen()

    def action_create_folder(self):
        self.ensure_one()
        if not self.new_folder_name:
            raise UserError(_("Indica el nombre de la carpeta."))
        drive_id = self._current_drive_id()
        _logger.info(
            "SharePoint explorer create folder drive_id=%s parent_item_id=%s folder=%s user_id=%s",
            drive_id,
            self.current_item_id,
            self.new_folder_name,
            self.env.user.id,
        )
        self.env["risk.sharepoint.service"]._create_folder_under_item(
            drive_id, self.current_item_id, self.new_folder_name
        )
        self.new_folder_name = False
        self._refresh_lines()
        return self._reopen()

    def action_upload_test_file(self):
        self.ensure_one()
        if not self.test_file:
            raise UserError(_("Carga un archivo de prueba."))
        drive_id = self._current_drive_id()
        filename = self.test_filename or (
            "prueba_odoo_sharepoint_%s.txt" % datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        content = base64.b64decode(self.test_file)
        _logger.info(
            "SharePoint explorer test upload drive_id=%s parent_item_id=%s filename=%s size=%s user_id=%s",
            drive_id,
            self.current_item_id,
            filename,
            len(content),
            self.env.user.id,
        )
        item = self.env["risk.sharepoint.service"]._upload_test_file(
            drive_id, self.current_item_id, filename, content
        )
        self.write({
            "test_upload_item_id": item.get("id"),
            "test_upload_web_url": item.get("webUrl"),
            "test_upload_message": _(
                "Archivo de prueba subido correctamente: %s"
            ) % (item.get("name") or filename),
        })
        self._refresh_lines()
        return self._reopen()

    def action_delete_test_file(self):
        self.ensure_one()
        if not self.test_upload_item_id:
            raise UserError(_("No hay archivo de prueba para eliminar."))
        drive_id = self._current_drive_id()
        _logger.info(
            "SharePoint explorer delete test file drive_id=%s item_id=%s user_id=%s",
            drive_id,
            self.test_upload_item_id,
            self.env.user.id,
        )
        self.env["risk.sharepoint.service"]._delete(
            self.test_upload_item_id, drive_id=drive_id
        )
        self.write({
            "test_upload_item_id": False,
            "test_upload_web_url": False,
            "test_upload_message": _("Archivo de prueba eliminado correctamente."),
        })
        self._refresh_lines()
        return self._reopen()

    def action_open_test_file(self):
        self.ensure_one()
        if not self.test_upload_web_url:
            raise UserError(_("No hay enlace de prueba para abrir."))
        return {
            "type": "ir.actions.act_url",
            "url": self.test_upload_web_url,
            "target": "new",
        }

    def action_change_drive(self):
        """Regresa al paso 1 para cambiar la biblioteca."""
        self.ensure_one()
        self.write({
            "stage": "drive",
            "selected_drive_id": "",
            "current_path": "",
            "current_item_id": "",
            "folder_choice": False,
            "explorer_message": "",
        })
        self.line_ids.unlink()
        return self._reopen()

    def _confirm_into_route(self, route_id, item_id):
        """Guarda la carpeta elegida como destino de una ruta por tipo."""
        self.ensure_one()
        route = self.env["risk.sharepoint.route"].browse(route_id)
        if not route.exists():
            raise UserError(_("La ruta ya no existe."))
        label_parts = [self.drive_id] + [
            part for part in (self.current_path or "").split("/") if part
        ]
        dest_label = " / ".join(part for part in label_parts if part)
        _logger.info(
            "SharePoint explorer confirm route route_id=%s drive_id=%s item_id=%s path=%s user_id=%s",
            route_id,
            self.selected_drive_id,
            item_id,
            self.current_path,
            self.env.user.id,
        )
        route.write({
            "dest_drive_id": self.selected_drive_id or self._current_drive_id(),
            "dest_item_id": item_id,
            "dest_label": dest_label,
        })
        return {"type": "ir.actions.act_window_close"}

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
                self.selected_drive_id = _drive_id
            except Exception:
                item_id = ""

        # Si el explorador se abrió para una ruta concreta, guardamos la carpeta
        # en esa ruta en vez de en la configuración global.
        route_id = self.env.context.get("route_id")
        if route_id:
            return self._confirm_into_route(route_id, item_id)

        cfg = self.env["ir.config_parameter"].sudo()
        _logger.info(
            "SharePoint explorer confirm folder drive=%s drive_id=%s path=%s item_id=%s user_id=%s",
            self.drive_id,
            self.selected_drive_id,
            self.current_path,
            item_id,
            self.env.user.id,
        )
        cfg.set_param("risk_module.sp_drive", self.drive_id)
        if self.selected_drive_id:
            cfg.set_param("risk_module.sp_drive_id", self.selected_drive_id)
        cfg.set_param("risk_module.sp_root_folder", self.current_path or "Solicitudes")
        if item_id:
            cfg.set_param("risk_module.sp_root_item_id", item_id)
        from odoo.addons.risk_module.models.risk_sharepoint_service import _LOCATION_CACHE
        _LOCATION_CACHE.clear()
        return {"type": "ir.actions.act_window_close"}
