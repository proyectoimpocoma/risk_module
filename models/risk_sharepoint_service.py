import logging
from urllib.parse import unquote, urlparse

import requests

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import msal
except ImportError:  # pragma: no cover - dependencia externa declarada en manifest
    msal = None

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
# Limite de subida simple de Graph; por encima se usa una sesion por chunks.
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024
# El tamano de chunk debe ser multiplo de 320 KiB (requisito de Graph).
UPLOAD_CHUNK_SIZE = 16 * 320 * 1024  # 5 MiB
HTTP_TIMEOUT = 30
# Caracteres no permitidos en nombres de SharePoint / OneDrive.
_INVALID_NAME_CHARS = '"*:<>?/\\|'

# Cache en memoria por proceso. El token lo gestiona MSAL dentro de la app;
# el site/drive se resuelve una vez por configuracion.
_MSAL_APPS = {}
_LOCATION_CACHE = {}


class RiskSharepointService(models.AbstractModel):
    """Cliente de Microsoft Graph (app-only) para almacenar documentos en SharePoint.

    Toda la interaccion con Graph vive aqui; el resto del modulo solo llama a
    ``_store_file`` / ``_get_download_url`` / ``_delete`` sin conocer detalles HTTP.
    """

    _name = "risk.sharepoint.service"
    _description = "Servicio de integracion con SharePoint"

    # ------------------------------------------------------------------
    # Configuracion
    # ------------------------------------------------------------------
    def _config(self):
        """Lee la configuracion de SharePoint desde ir.config_parameter."""
        get = self.env["ir.config_parameter"].sudo().get_param
        return {
            "enabled": get("risk_module.sp_enabled") in ("True", "1", "true"),
            "tenant_id": get("risk_module.sp_tenant_id") or "",
            "client_id": get("risk_module.sp_client_id") or "",
            "client_secret": get("risk_module.sp_client_secret") or "",
            "site": (get("risk_module.sp_site") or "").strip(),
            "drive": (get("risk_module.sp_drive") or "").strip(),
            "drive_id": (get("risk_module.sp_drive_id") or "").strip(),
            "root_folder": (get("risk_module.sp_root_folder") or "Solicitudes").strip(),
            "root_item_id": get("risk_module.sp_root_item_id") or "",
            "purge_local": get("risk_module.sp_purge_local")
            in ("True", "1", "true", None),
            "max_attempts": int(get("risk_module.sp_max_attempts") or 5),
        }

    def _is_enabled(self):
        cfg = self._config()
        return bool(
            cfg["enabled"]
            and cfg["tenant_id"]
            and cfg["client_id"]
            and cfg["client_secret"]
            and (cfg["site"] or cfg["drive_id"])
        )

    @staticmethod
    def _sanitize_name(name):
        """Limpia un segmento de ruta para que sea valido en SharePoint."""
        cleaned = "".join(
            " " if ch in _INVALID_NAME_CHARS else ch for ch in (name or "")
        )
        cleaned = cleaned.strip().strip(".")
        return cleaned or "sin_nombre"

    @staticmethod
    def _parse_children_url(url):
        """Extrae drive_id e item_id desde una URL de Graph /children."""
        parsed = urlparse((url or "").strip())
        path_parts = [unquote(part) for part in parsed.path.split("/") if part]
        try:
            drive_index = path_parts.index("drives")
            item_index = path_parts.index("items")
        except ValueError as exc:
            raise UserError(
                "La URL debe tener el formato /v1.0/drives/<drive_id>/items/<item_id>/children."
            ) from exc
        if len(path_parts) <= drive_index + 1 or len(path_parts) <= item_index + 1:
            raise UserError("La URL de Graph no contiene drive_id o item_id.")
        if "children" not in path_parts[item_index + 2 :]:
            raise UserError("La URL debe apuntar al endpoint /children de la carpeta.")
        return {
            "drive_id": path_parts[drive_index + 1],
            "item_id": path_parts[item_index + 1],
        }

    # ------------------------------------------------------------------
    # Autenticacion
    # ------------------------------------------------------------------
    def _get_token(self):
        cfg = self._config()
        if msal is None:
            raise UserError(
                "La libreria 'msal' no esta instalada. Ejecuta 'pip install msal'."
            )
        if not (cfg["tenant_id"] and cfg["client_id"] and cfg["client_secret"]):
            raise UserError("Faltan credenciales de SharePoint en la configuracion.")
        key = (cfg["tenant_id"], cfg["client_id"])
        app = _MSAL_APPS.get(key)
        if app is None:
            app = msal.ConfidentialClientApplication(
                cfg["client_id"],
                authority="https://login.microsoftonline.com/%s" % cfg["tenant_id"],
                client_credential=cfg["client_secret"],
            )
            _MSAL_APPS[key] = app
        result = app.acquire_token_silent(GRAPH_SCOPE, account=None)
        if not result:
            result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        if "access_token" not in result:
            _logger.error(
                "SharePoint token error error=%s description=%s",
                result.get("error"),
                result.get("error_description"),
            )
            raise UserError(
                "No se pudo autenticar con SharePoint: %s"
                % result.get("error_description", result.get("error", "desconocido"))
            )
        return result["access_token"]

    def _headers(self, extra=None):
        headers = {"Authorization": "Bearer %s" % self._get_token()}
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method, url, **kwargs):
        """Wrapper de requests con auth, timeout y un reintento ante 401."""
        kwargs.setdefault("timeout", HTTP_TIMEOUT)
        extra_headers = kwargs.pop("headers", None)
        response = requests.request(
            method, url, headers=self._headers(extra_headers), **kwargs
        )
        if response.status_code == 401:
            # Token expirado o revocado: limpiamos cache y reintentamos una vez,
            # preservando las cabeceras extra (p. ej. Content-Type de subida).
            cfg = self._config()
            _MSAL_APPS.pop((cfg["tenant_id"], cfg["client_id"]), None)
            response = requests.request(
                method, url, headers=self._headers(extra_headers), **kwargs
            )
        if response.status_code >= 400:
            _logger.warning(
                "SharePoint Graph error method=%s url=%s status=%s body=%s",
                method,
                url,
                response.status_code,
                response.text[:500],
            )
            response.raise_for_status()
        return response

    # ------------------------------------------------------------------
    # Resolucion de sitio / biblioteca
    # ------------------------------------------------------------------
    def _resolve_location(self):
        """Devuelve (site_id, drive_id), cacheado por configuracion."""
        cfg = self._config()
        key = (cfg["site"], cfg["drive"], cfg["drive_id"])
        cached = _LOCATION_CACHE.get(key)
        if cached:
            return cached
        if cfg["drive_id"]:
            _LOCATION_CACHE[key] = ("", cfg["drive_id"])
            return _LOCATION_CACHE[key]
        site = self._request("GET", "%s/sites/%s" % (GRAPH_BASE, cfg["site"])).json()
        site_id = site["id"]
        if cfg["drive"]:
            drives = (
                self._request("GET", "%s/sites/%s/drives" % (GRAPH_BASE, site_id))
                .json()
                .get("value", [])
            )
            drive = next((d for d in drives if d.get("name") == cfg["drive"]), None)
            if not drive:
                raise UserError(
                    "No se encontro la biblioteca '%s' en el sitio." % cfg["drive"]
                )
            drive_id = drive["id"]
        else:
            drive = self._request(
                "GET", "%s/sites/%s/drive" % (GRAPH_BASE, site_id)
            ).json()
            drive_id = drive["id"]
        _LOCATION_CACHE[key] = (site_id, drive_id)
        return site_id, drive_id

    def _ensure_folder(self, drive_id, segments):
        """Crea el arbol de carpetas de forma idempotente. Devuelve la ruta final."""
        path_parts = []
        for raw_segment in segments:
            segment = self._sanitize_name(raw_segment)
            parent = "/".join(path_parts)
            if parent:
                url = "%s/drives/%s/root:/%s:/children" % (GRAPH_BASE, drive_id, parent)
            else:
                url = "%s/drives/%s/root/children" % (GRAPH_BASE, drive_id)
            payload = {
                "name": segment,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail",
            }
            try:
                self._request("POST", url, json=payload)
            except requests.HTTPError as exc:
                # 409 = la carpeta ya existe; cualquier otro error se propaga.
                if not (exc.response is not None and exc.response.status_code == 409):
                    raise
            path_parts.append(segment)
        return "/".join(path_parts)

    def _ensure_folder_under_item(self, drive_id, parent_item_id, segments):
        """Crea segmentos debajo de un item_id y devuelve el item_id final."""
        current_item_id = parent_item_id
        for raw_segment in segments:
            segment = self._sanitize_name(raw_segment)
            url = "%s/drives/%s/items/%s/children" % (
                GRAPH_BASE,
                drive_id,
                current_item_id,
            )
            payload = {
                "name": segment,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail",
            }
            try:
                item = self._request("POST", url, json=payload).json()
                current_item_id = item["id"]
            except requests.HTTPError as exc:
                if not (exc.response is not None and exc.response.status_code == 409):
                    raise
                current_item_id = self._get_child_item_id(
                    drive_id, current_item_id, segment
                )
        return current_item_id

    def _list_children_by_item(self, drive_id, item_id):
        """Lista carpetas y archivos hijos de un item de SharePoint."""
        _logger.info(
            "SharePoint list children requested drive_id=%s item_id=%s",
            drive_id,
            item_id,
        )
        url = (
            "%s/drives/%s/items/%s/children"
            "?$select=id,name,folder,file,size,webUrl"
            % (GRAPH_BASE, drive_id, item_id)
        )
        items = self._request("GET", url).json().get("value", [])
        result = [
            {
                "id": item["id"],
                "name": item.get("name", item["id"]),
                "is_folder": "folder" in item,
                "is_file": "file" in item,
                "size": item.get("size") or 0,
                "web_url": item.get("webUrl") or "",
            }
            for item in items
        ]
        result.sort(key=lambda item: (not item["is_folder"], item["name"].lower()))
        _logger.info(
            "SharePoint list children ok drive_id=%s item_id=%s folders=%s files=%s",
            drive_id,
            item_id,
            len([item for item in result if item["is_folder"]]),
            len([item for item in result if item["is_file"]]),
        )
        return result

    def _create_folder_under_item(self, drive_id, parent_item_id, folder_name):
        """Crea una subcarpeta directa bajo parent_item_id."""
        safe_name = self._sanitize_name(folder_name)
        _logger.info(
            "SharePoint create folder requested drive_id=%s parent_item_id=%s folder=%s",
            drive_id,
            parent_item_id,
            safe_name,
        )
        url = "%s/drives/%s/items/%s/children" % (
            GRAPH_BASE,
            drive_id,
            parent_item_id,
        )
        payload = {
            "name": safe_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        }
        try:
            item = self._request("POST", url, json=payload).json()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 409:
                _logger.info(
                    "SharePoint create folder conflict drive_id=%s parent_item_id=%s folder=%s",
                    drive_id,
                    parent_item_id,
                    safe_name,
                )
                raise UserError("Ya existe una carpeta llamada '%s'." % safe_name) from exc
            raise
        _logger.info(
            "SharePoint create folder ok drive_id=%s parent_item_id=%s folder=%s item_id=%s",
            drive_id,
            parent_item_id,
            safe_name,
            item.get("id"),
        )
        return item

    def _upload_test_file(self, drive_id, parent_item_id, filename, content):
        """Sube un archivo de prueba en una carpeta concreta."""
        safe_name = self._sanitize_name(filename)
        _logger.info(
            "SharePoint test upload requested drive_id=%s parent_item_id=%s filename=%s size=%s",
            drive_id,
            parent_item_id,
            safe_name,
            len(content or b""),
        )
        item = self._upload_to_parent_item(drive_id, parent_item_id, safe_name, content)
        _logger.info(
            "SharePoint test upload ok drive_id=%s parent_item_id=%s filename=%s item_id=%s",
            drive_id,
            parent_item_id,
            safe_name,
            item.get("id"),
        )
        return item

    # ------------------------------------------------------------------
    # API publica usada por el modelo de documento
    # ------------------------------------------------------------------
    def _store_file(self, folder_segments, filename, content, item_id=None):
        """Sube ``content`` a SharePoint.

        Si ``item_id`` esta presente, sube una nueva version del item existente;
        si no, crea el archivo (creando antes el arbol de carpetas).

        Devuelve dict(item_id, web_url, drive_id).
        """
        _, drive_id = self._resolve_location()
        cfg = self._config()
        safe_name = self._sanitize_name(filename)
        if item_id:
            item = self._upload_to_item(drive_id, item_id, content)
        elif cfg["root_item_id"]:
            parent_item_id = self._ensure_folder_under_item(
                drive_id, cfg["root_item_id"], folder_segments[1:]
            )
            item = self._upload_to_parent_item(
                drive_id, parent_item_id, safe_name, content
            )
        else:
            folder_path = self._ensure_folder(drive_id, folder_segments)
            item = self._upload_to_path(drive_id, folder_path, safe_name, content)
        return {
            "item_id": item["id"],
            "web_url": item.get("webUrl"),
            "drive_id": drive_id,
        }

    def _upload_to_path(self, drive_id, folder_path, filename, content):
        if len(content) < SIMPLE_UPLOAD_LIMIT:
            url = "%s/drives/%s/root:/%s/%s:/content" % (
                GRAPH_BASE,
                drive_id,
                folder_path,
                filename,
            )
            return self._request(
                "PUT",
                url,
                data=content,
                headers={"Content-Type": "application/octet-stream"},
            ).json()
        session_url = "%s/drives/%s/root:/%s/%s:/createUploadSession" % (
            GRAPH_BASE,
            drive_id,
            folder_path,
            filename,
        )
        return self._upload_session(session_url, content)

    def _upload_to_parent_item(self, drive_id, parent_item_id, filename, content):
        if len(content) < SIMPLE_UPLOAD_LIMIT:
            url = "%s/drives/%s/items/%s:/%s:/content" % (
                GRAPH_BASE,
                drive_id,
                parent_item_id,
                filename,
            )
            return self._request(
                "PUT",
                url,
                data=content,
                headers={"Content-Type": "application/octet-stream"},
            ).json()
        session_url = "%s/drives/%s/items/%s:/%s:/createUploadSession" % (
            GRAPH_BASE,
            drive_id,
            parent_item_id,
            filename,
        )
        return self._upload_session(session_url, content)

    def _upload_to_item(self, drive_id, item_id, content):
        if len(content) < SIMPLE_UPLOAD_LIMIT:
            url = "%s/drives/%s/items/%s/content" % (GRAPH_BASE, drive_id, item_id)
            return self._request(
                "PUT",
                url,
                data=content,
                headers={"Content-Type": "application/octet-stream"},
            ).json()
        session_url = "%s/drives/%s/items/%s/createUploadSession" % (
            GRAPH_BASE,
            drive_id,
            item_id,
        )
        return self._upload_session(session_url, content)

    def _upload_session(self, session_url, content):
        """Subida por chunks para archivos grandes (>4 MB)."""
        upload_url = self._request(
            "POST",
            session_url,
            json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
        ).json()["uploadUrl"]
        total = len(content)
        start = 0
        response = None
        while start < total:
            end = min(start + UPLOAD_CHUNK_SIZE, total)
            chunk = content[start:end]
            # La URL de sesion ya esta preautenticada: no enviar Authorization.
            response = requests.put(
                upload_url,
                data=chunk,
                headers={
                    "Content-Length": str(len(chunk)),
                    "Content-Range": "bytes %d-%d/%d" % (start, end - 1, total),
                },
                timeout=HTTP_TIMEOUT,
            )
            if response.status_code >= 400:
                requests.delete(upload_url, timeout=HTTP_TIMEOUT)
                response.raise_for_status()
            start = end
        return response.json()

    def _get_download_url(self, item_id, drive_id=None):
        """Devuelve una URL de descarga efimera (preautenticada) del item."""
        if not drive_id:
            _, drive_id = self._resolve_location()
        url = "%s/drives/%s/items/%s?select=id,@microsoft.graph.downloadUrl" % (
            GRAPH_BASE,
            drive_id,
            item_id,
        )
        data = self._request("GET", url).json()
        return data.get("@microsoft.graph.downloadUrl")

    def _download_content(self, item_id, drive_id=None):
        """Descarga el contenido binario del item (para servir por proxy)."""
        if not drive_id:
            _, drive_id = self._resolve_location()
        url = "%s/drives/%s/items/%s/content" % (GRAPH_BASE, drive_id, item_id)
        return self._request("GET", url).content

    def _delete(self, item_id, drive_id=None):
        if not drive_id:
            _, drive_id = self._resolve_location()
        url = "%s/drives/%s/items/%s" % (GRAPH_BASE, drive_id, item_id)
        self._request("DELETE", url)

    def _list_drives(self):
        """Devuelve lista de dicts con id/name de las bibliotecas del sitio configurado."""
        cfg = self._config()
        if not cfg["site"]:
            raise UserError("Configura el sitio de SharePoint antes de listar las bibliotecas.")
        site = self._request("GET", "%s/sites/%s" % (GRAPH_BASE, cfg["site"])).json()
        site_id = site["id"]
        drives = (
            self._request("GET", "%s/sites/%s/drives" % (GRAPH_BASE, site_id))
            .json()
            .get("value", [])
        )
        return [{"id": d["id"], "name": d.get("name", d["id"])} for d in drives]

    def _get_drive_name(self, drive_id):
        data = self._request(
            "GET", "%s/drives/%s?$select=id,name" % (GRAPH_BASE, drive_id)
        ).json()
        return data.get("name") or drive_id

    def _drive_id_by_name(self, drive_name):
        """Resuelve el ID interno de un drive a partir de su nombre."""
        drives = self._list_drives()
        drive = next((d for d in drives if d["name"] == drive_name), None)
        if not drive:
            raise UserError("No se encontró la biblioteca '%s'." % drive_name)
        return drive["id"]

    def _get_drive_root_item_id(self, drive_name):
        """Devuelve (item_id, drive_id) de la raíz del drive."""
        drive_id = self._drive_id_by_name(drive_name)
        item = self._request(
            "GET", "%s/drives/%s/root?$select=id" % (GRAPH_BASE, drive_id)
        ).json()
        return item["id"], drive_id

    def _list_folders_by_item(self, drive_id, item_id):
        """Lista subcarpetas directas de un item dado su ID. Devuelve dicts id/name."""
        items = self._list_children_by_item(drive_id, item_id)
        return [{"id": i["id"], "name": i["name"]} for i in items if i["is_folder"]]

    def _test_root_folder(self):
        cfg = self._config()
        _, drive_id = self._resolve_location()
        item_id = cfg["root_item_id"]
        if not item_id:
            if cfg["drive"]:
                item_id, drive_id = self._get_drive_root_item_id(cfg["drive"])
            else:
                item = self._request(
                    "GET", "%s/drives/%s/root?$select=id" % (GRAPH_BASE, drive_id)
                ).json()
                item_id = item["id"]
        url = "%s/drives/%s/items/%s/children?$top=1&$select=id,name,folder,file" % (
            GRAPH_BASE,
            drive_id,
            item_id,
        )
        self._request("GET", url).json()
        return {"drive_id": drive_id, "item_id": item_id}

    def _get_child_item_id(self, drive_id, parent_item_id, child_name):
        """Resuelve el item_id de una subcarpeta dada el ID del padre y el nombre."""
        url = "%s/drives/%s/items/%s:/%s?$select=id,name" % (
            GRAPH_BASE,
            drive_id,
            parent_item_id,
            child_name,
        )
        return self._request("GET", url).json()["id"]

    def _get_item_parent_id(self, drive_id, item_id):
        """Devuelve el item_id del directorio padre."""
        url = "%s/drives/%s/items/%s?$select=id,parentReference" % (
            GRAPH_BASE,
            drive_id,
            item_id,
        )
        item = self._request("GET", url).json()
        return item.get("parentReference", {}).get("id")

    def _resolve_item_id_for_path(self, drive_name, path=""):
        """Devuelve (item_id, drive_id) de una ruta relativa a la raíz del drive."""
        drive_id = self._drive_id_by_name(drive_name)
        if path:
            url = "%s/drives/%s/root:/%s?$select=id" % (GRAPH_BASE, drive_id, path)
        else:
            url = "%s/drives/%s/root?$select=id" % (GRAPH_BASE, drive_id)
        return self._request("GET", url).json()["id"], drive_id

    def _list_folders(self, drive_name, path=""):
        """Devuelve nombres de subcarpetas dentro de path en el drive indicado.

        path vacío → raíz del drive.  Usa rutas para compatibilidad con código existente;
        para navegación nueva preferir _list_folders_by_item (más estable ante renombrados).
        """
        drive_id = self._drive_id_by_name(drive_name)
        if path:
            url = "%s/drives/%s/root:/%s:/children?$select=id,name,folder" % (
                GRAPH_BASE,
                drive_id,
                path,
            )
        else:
            url = "%s/drives/%s/root/children?$select=id,name,folder" % (
                GRAPH_BASE,
                drive_id,
            )
        items = self._request("GET", url).json().get("value", [])
        return [i["name"] for i in items if "folder" in i]

    def _test_connection(self):
        """Resuelve sitio y biblioteca; util para un boton 'Probar conexion'."""
        _LOCATION_CACHE.clear()
        site_id, drive_id = self._resolve_location()
        info = self._test_root_folder()
        return {
            "site_id": site_id,
            "drive_id": drive_id,
            "root_item_id": info["item_id"],
        }
