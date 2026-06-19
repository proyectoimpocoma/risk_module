# Almacenamiento de documentos en SharePoint

Integración del módulo **Risk Module** para guardar en **SharePoint** los
documentos que los terceros suben desde el portal, manteniendo en Odoo solo
una **referencia** (modo *solo-SharePoint*).

---

## 1. Resumen

Cuando un tercero sube un documento desde el portal de habilitación, el archivo:

1. Se guarda **temporalmente** en Odoo (área de ingesta).
2. Un proceso en segundo plano (**cron**) lo sube a SharePoint vía **Microsoft
   Graph**.
3. Una vez confirmada la subida, Odoo guarda la **referencia** (id del archivo
   en SharePoint, enlace) y **borra la copia local** — el binario vive solo en
   SharePoint.

Si SharePoint está desactivado o mal configurado, el módulo funciona como
siempre (archivo solo en Odoo): **degradación elegante**, nunca se pierde una
subida del usuario.

---

## 2. Arquitectura

```
┌─────────────┐   sube archivo    ┌──────────────────────────┐
│  Tercero    │ ────────────────► │  risk.module.document     │
│  (portal)   │                   │  file (ingesta temporal)  │
└─────────────┘                   │  sharepoint_state=pending │
                                  └────────────┬─────────────┘
                                               │  (cada 5 min)
                                               ▼
                                  ┌──────────────────────────┐
                                  │  ir.cron                  │
                                  │  _cron_sync_sharepoint()  │
                                  └────────────┬─────────────┘
                                               ▼
                                  ┌──────────────────────────┐      ┌───────────────┐
                                  │ risk.sharepoint.service   │ ───► │  Microsoft    │
                                  │ (cliente Graph, app-only) │      │  Graph API    │
                                  └────────────┬─────────────┘      │  + SharePoint │
                                               │                    └───────────────┘
                                               ▼
                                  ┌──────────────────────────┐
                                  │  documento actualizado    │
                                  │  sharepoint_item_id=...   │
                                  │  sharepoint_state=synced  │
                                  │  file = (purgado)         │
                                  └──────────────────────────┘
```

### Patrón *outbox* (bandeja de salida)

No se sube en el momento de la petición (eso bloquearía al usuario y fallaría si
SharePoint está caído). En su lugar, el documento se marca `pending` y un
**cron cada 5 minutos** vacía la bandeja. El campo `sharepoint_state` es la
bandeja de salida.

---

## 3. Componentes (archivos)

| Componente | Archivo | Rol |
|---|---|---|
| Cliente Graph | [`models/risk_sharepoint_service.py`](../models/risk_sharepoint_service.py) | Toda la interacción HTTP con Microsoft Graph (auth, carpetas, subida, descarga). |
| Documento | [`models/risk_submission_document.py`](../models/risk_submission_document.py) | Campos SharePoint, orquestación, `_sync_to_sharepoint`, cron, reintentos. |
| Historial | [`models/risk_submission_document_version.py`](../models/risk_submission_document_version.py) | Un registro por cada subida/reenvío/fallo. |
| Configuración | [`models/res_config_settings.py`](../models/res_config_settings.py) | Ajustes + botones *Probar conexión* / *Back-fill*. |
| Cron | [`data/risk_sharepoint_cron.xml`](../data/risk_sharepoint_cron.xml) | Motor de sincronización (cada 5 min). |
| Descarga portal | [`controllers/risk_submission_portal_controller.py`](../controllers/risk_submission_portal_controller.py) | Proxy `/.../documentos/<id>/archivo` que sirve el archivo al tercero. |
| Vistas | [`views/backend/res_config_settings_views.xml`](../views/backend/res_config_settings_views.xml), [`views/backend/risk_submission_document_views.xml`](../views/backend/risk_submission_document_views.xml) | Pantalla de ajustes, sección SharePoint y pestaña Historial. |

---

## 4. Campos del documento (`risk.module.document`)

| Campo | Descripción |
|---|---|
| `file` | Archivo (ingesta temporal; se purga tras subir a SharePoint). |
| `has_file` | Verdadero si hay archivo local **o** ya está en SharePoint. |
| `sharepoint_item_id` | Id del archivo en SharePoint (la referencia). |
| `sharepoint_web_url` | Enlace para abrir el archivo en SharePoint. |
| `sharepoint_drive_id` | Id de la biblioteca (drive). |
| `sharepoint_state` | `disabled` · `pending` · `synced` · `error`. |
| `sharepoint_synced_at` | Fecha/hora de la última subida correcta. |
| `sharepoint_error` | Último mensaje de error de sincronización. |
| `sharepoint_attempts` | Reintentos acumulados (se corta al llegar al máximo). |
| `version_ids` | Historial de cargas (ver sección 6). |

### Estados (`sharepoint_state`)

- **`disabled`** — sin sincronizar (SharePoint apagado o documento sin archivo).
- **`pending`** — en la bandeja de salida, esperando al cron.
- **`synced`** — almacenado en SharePoint; la copia local fue purgada.
- **`error`** — falló tras agotar los reintentos; requiere revisión manual.

---

## 5. Flujos

### 5.1 Subida normal

1. El tercero sube el archivo → `file` se llena, `sharepoint_state = pending`,
   se crea una fila de historial (`pending`).
2. El cron lo toma, crea las carpetas en SharePoint y sube el archivo.
3. Éxito → guarda `sharepoint_item_id` / `web_url`, `sharepoint_state = synced`,
   purga `file`, marca la fila de historial como `uploaded`.

**Estructura de carpetas en SharePoint:**

```
{Carpeta raíz}/{Referencia solicitud} {Placa}/{Relacionado con}/{archivo}
   Solicitudes / SOL-00042 ABC123 / Conductor / cedula.pdf
```

### 5.2 Rechazo → reenvío

1. Riesgo rechaza el documento (`state = rejected`, con motivo y observaciones).
2. El tercero sube el documento corregido.
3. El módulo detecta que es un **reemplazo** (porque ya existe
   `sharepoint_item_id`), limpia el motivo de rechazo y vuelve a `received`.
4. El cron sube la nueva versión **al mismo archivo de SharePoint** (`PUT` sobre
   el `item_id`), de modo que SharePoint guarda el **historial de versiones
   nativo** (la versión rechazada queda accesible).
5. El contador `Veces reemplazado` (`replacement_count`) aumenta y se registra
   una nueva fila de historial con el motivo de rechazo que la originó.

### 5.3 Descarga / visualización

- **Mientras está `pending`/`error`:** se sirve la **copia local** (es la versión
  vigente; la de SharePoint aún sería la anterior).
- **Cuando está `synced`:** se abre/streamea desde SharePoint.
- **Portal (tercero):** ruta proxy
  `/mis-solicitudes-riesgo/<solicitud>/documentos/<documento>/archivo`, que hace
  *stream* del contenido **sin exponer** la URL de SharePoint al tercero.
- **Backend (analista):** botón *Abrir archivo* → enlace de SharePoint si está
  sincronizado.

---

## 6. Historial de cargas

Modelo `risk.module.document.version`. Se crea una fila por cada intento:

| Campo | Significado |
|---|---|
| `result` | `pending` (en proceso) · `uploaded` (subido) · `failed` (fallido). |
| `version_number` | Número de versión secuencial del documento. |
| `is_replacement` | Si fue un reenvío. |
| `triggered_by_rejection` | Motivo de rechazo que originó el reenvío. |
| `error_message` | Detalle del error si falló. |
| `uploaded_by_id` / `uploaded_at` | Quién y cuándo. |

**Dónde verlo:**
- En el **formulario del documento**, pestaña *Historial de cargas*.
- En el menú **Riesgo → Historial de cargas**, filtrable por *Subidos* /
  *Fallidos* / *En proceso*.

---

## 7. Tutorial de configuración

### Paso 1 — Registrar la aplicación en Azure AD

1. Entra a **Azure Portal → Microsoft Entra ID (Azure AD) → App registrations →
   New registration**.
2. Nombre: p. ej. `Odoo Riesgo SharePoint`. Tipo: *Single tenant*. Registrar.
3. Anota el **Application (client) ID** y el **Directory (tenant) ID**.
4. **Certificates & secrets → New client secret** → copia el **valor** del
   secreto (solo se muestra una vez). *(En producción se recomienda
   certificado en lugar de secreto.)*

### Paso 2 — Permiso Microsoft Graph `Sites.Selected`

1. En la app: **API permissions → Add a permission → Microsoft Graph →
   Application permissions →** busca **`Sites.Selected`** → añadir.
2. Pulsa **Grant admin consent** (lo hace un administrador del tenant).

> `Sites.Selected` da acceso **solo** a los sitios que se autoricen
> explícitamente (mínimo privilegio), no a todo SharePoint.

### Paso 3 — Conceder acceso al sitio concreto

Un administrador debe otorgar a la app permiso de **escritura** sobre el sitio
de riesgos. Vía Graph (por ejemplo desde *Graph Explorer*):

```http
POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
Content-Type: application/json

{
  "roles": ["write"],
  "grantedToIdentities": [
    { "application": { "id": "{client-id}", "displayName": "Odoo Riesgo SharePoint" } }
  ]
}
```

Para obtener el `{site-id}`:

```http
GET https://graph.microsoft.com/v1.0/sites/{host}:/sites/{ruta}
   ej: /sites/contoso.sharepoint.com:/sites/Riesgos
```

### Paso 4 — Dependencias e instalación del módulo

1. Instala la librería de autenticación en el entorno de Odoo:
   ```bash
   pip install msal
   ```
2. Actualiza el módulo para que aparezcan los campos y el menú:
   ```bash
   odoo -u risk_module -d <tu_base> --stop-after-init
   ```

### Paso 5 — Configurar en Odoo

Ve a **Riesgo → Configuración → Ajustes de SharePoint** (requiere el grupo
**Gestor de riesgo**) y rellena:

| Campo | Valor |
|---|---|
| Guardar documentos en SharePoint | ✅ activar |
| Tenant ID | *Directory (tenant) ID* del Paso 1 |
| Client ID | *Application (client) ID* del Paso 1 |
| Client Secret | el secreto del Paso 1 |
| Sitio de SharePoint | `contoso.sharepoint.com:/sites/Riesgos` |
| Biblioteca de documentos | nombre del *drive* (vacío = biblioteca por defecto) |
| Carpeta raíz | `Solicitudes` |
| Eliminar copia local tras subir | ✅ (modo solo-SharePoint) |
| Máximo de intentos | `5` |

### Paso 6 — Probar y poner en marcha

1. Pulsa **Probar conexión** → debe confirmar que resuelve el sitio/biblioteca.
2. (Opcional) Pulsa **Sincronizar documentos existentes** para subir los
   documentos que ya tenían archivo cargado.
3. Listo: las nuevas subidas del portal se sincronizarán automáticamente cada
   5 minutos.

> Los valores se guardan como parámetros del sistema (`risk_module.sp_*`), así
> que también pueden fijarse en **Ajustes técnicos → Parámetros del sistema**.

---

## 8. Operación y solución de problemas

| Síntoma | Causa / acción |
|---|---|
| Documento en `pending` mucho tiempo | El cron corre cada 5 min; revisa **Ajustes técnicos → Programado → "Riesgo: sincronizar documentos a SharePoint"** que esté activo. |
| Documento en `error` | Agotó los reintentos. Revisa `sharepoint_error` en el formulario y pulsa **Reintentar SharePoint** (resetea intentos y sube). |
| *Probar conexión* falla | Credenciales incorrectas, falta `Sites.Selected` con *admin consent*, o la app no tiene acceso al sitio (Paso 3). |
| `msal no instalada` | Ejecuta `pip install msal` en el entorno de Odoo. |
| No aparece el menú de ajustes | Falta actualizar el módulo (`-u risk_module`) o el usuario no es *Gestor de riesgo*. |

**Parámetros de afinado:**
- Frecuencia del cron: editar el registro `ir.cron` (por defecto 5 minutos).
- Reintentos: campo *Máximo de intentos* (por defecto 5).
- Conservar copia local: desactivar *Eliminar copia local tras subir* (modo
  espejo en vez de solo-referencia).

---

## 9. Seguridad

- Autenticación **app-only** (sin usuario): identidad de servicio con permiso
  **`Sites.Selected`** acotado al sitio de riesgos.
- Los secretos se guardan en parámetros del sistema (solo administradores). En
  producción, preferir **certificado** sobre *client secret*.
- El tercero **nunca** ve SharePoint: la descarga pasa por un proxy de Odoo que
  valida la propiedad de la solicitud.
- El menú de ajustes está restringido al grupo **Gestor de riesgo**.
