import logging

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
            "root_folder": (get("risk_module.sp_root_folder") or "Solicitudes").strip(),
            "purge_local": get("risk_module.sp_purge_local")
            in ("True", "1", "true", None),
            "max_attempts": int(get("risk_module.sp_max_attempts") or 5),
        }

    def _is_enabled(self):
        cfg = self._config()
        return bool(
            cfg["enabled"] and cfg["tenant_id"] and cfg["client_id"] and cfg["site"]
        )

    @staticmethod
    def _sanitize_name(name):
        """Limpia un segmento de ruta para que sea valido en SharePoint."""
        cleaned = "".join(
            " " if ch in _INVALID_NAME_CHARS else ch for ch in (name or "")
        )
        cleaned = cleaned.strip().strip(".")
        return cleaned or "sin_nombre"

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
        key = (cfg["site"], cfg["drive"])
        cached = _LOCATION_CACHE.get(key)
        if cached:
            return cached
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
        safe_name = self._sanitize_name(filename)
        if item_id:
            item = self._upload_to_item(drive_id, item_id, content)
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

    def _list_folders(self, drive_name, path=""):
        """Devuelve nombres de subcarpetas dentro de path en el drive indicado.

        path vacío → raíz del drive.
        """
        cfg = self._config()
        if not cfg["site"]:
            raise UserError("Configura el sitio de SharePoint antes de navegar carpetas.")
        # Resolve drive id by name.
        drives = self._list_drives()
        drive = next((d for d in drives if d["name"] == drive_name), None)
        if not drive:
            raise UserError("No se encontró la biblioteca '%s'." % drive_name)
        drive_id = drive["id"]
        if path:
            url = "%s/drives/%s/root:/%s:/children?$select=name,folder&$filter=folder ne null" % (
                GRAPH_BASE,
                drive_id,
                path,
            )
        else:
            url = "%s/drives/%s/root/children?$select=name,folder&$filter=folder ne null" % (
                GRAPH_BASE,
                drive_id,
            )
        items = self._request("GET", url).json().get("value", [])
        return [i["name"] for i in items if "folder" in i]

    def _test_connection(self):
        """Resuelve sitio y biblioteca; util para un boton 'Probar conexion'."""
        _LOCATION_CACHE.clear()
        site_id, drive_id = self._resolve_location()
        return {"site_id": site_id, "drive_id": drive_id}
