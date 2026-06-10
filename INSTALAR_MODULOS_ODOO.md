# Manual para instalar modulos en Odoo 19

Este proyecto tiene Odoo en:

```bash
odoo-19.0.post20260606
```

Y usa la base de datos:

```bash
mi_empresa
```

El servidor se ejecuta con el entorno virtual:

```bash
.venv/bin/python
```

## 1. Estructura esperada

Los modulos personalizados deben estar en la raiz del proyecto, por ejemplo:

```text
/Users/angel/Documents/Projects/odoo
├── config/
│   └── odoo.config
├── odoo-19.0.post20260606/
└── support_helpdesk_ticket/
    └── __manifest__.py
```

Cada modulo debe tener su archivo:

```text
__manifest__.py
```

## 2. Configurar addons_path

Edita:

```bash
config/odoo.config
```

La linea `addons_path` debe incluir:

1. Los addons base de Odoo.
2. La carpeta raiz donde estan los modulos personalizados.

Ejemplo:

```ini
addons_path = /Users/angel/Documents/Projects/odoo/odoo-19.0.post20260606/odoo/addons,/Users/angel/Documents/Projects/odoo
```

No apuntes directamente a la carpeta del modulo. Debe apuntar a la carpeta padre.

Incorrecto:

```ini
addons_path = /Users/angel/Documents/Projects/odoo/support_helpdesk_ticket
```

Correcto:

```ini
addons_path = /Users/angel/Documents/Projects/odoo
```

## 3. Detener Odoo si esta corriendo

Verifica el proceso en el puerto `8069`:

```bash
lsof -nP -iTCP:8069 -sTCP:LISTEN
```

Si aparece un proceso, detenlo usando su PID:

```bash
kill PID
```

Ejemplo:

```bash
kill 55719
```

## 4. Instalar un modulo

Para instalar un modulo nuevo:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config -i NOMBRE_TECNICO_DEL_MODULO --stop-after-init
```

Ejemplo:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config -i support_helpdesk_ticket --stop-after-init
```

El nombre tecnico normalmente es el nombre de la carpeta del modulo.

## 5. Actualizar o reinstalar un modulo ya instalado

En Odoo, lo mas comun para "reinstalar" un modulo sin borrar datos es actualizarlo con `-u`:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config -u NOMBRE_TECNICO_DEL_MODULO --stop-after-init
```

Ejemplo:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config -u support_helpdesk_ticket --stop-after-init
```

Esto recarga modelos, vistas, reglas de seguridad y datos XML del modulo.

## 6. Cargar datos demo

Si el modulo tiene una seccion `demo` en su `__manifest__.py`, los datos demo no siempre se cargan en una base normal.

Para forzar la carga de datos demo en la base actual:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo module force-demo -c config/odoo.config -d mi_empresa
```

Importante: `force-demo` puede cargar datos demo de todos los modulos instalados, no solo de un modulo especifico.

## 7. Levantar Odoo

Despues de instalar o actualizar modulos, inicia el servidor:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config
```

Luego abre:

```text
http://localhost:8069
```

## 8. Confirmar si un modulo esta instalado

Usa PostgreSQL:

```bash
PGPASSWORD=odoo psql -h localhost -U odoo -d mi_empresa -c "select name, state, latest_version from ir_module_module where name = 'support_helpdesk_ticket';"
```

Si esta instalado debe aparecer:

```text
installed
```

## 9. Si el modulo esta instalado pero no aparece en Odoo

Puede ser un problema de permisos.

Primero revisa los grupos del modulo:

```bash
PGPASSWORD=odoo psql -h localhost -U odoo -d mi_empresa -c "select g.id, g.name, imd.name as xmlid from res_groups g join ir_model_data imd on imd.model='res.groups' and imd.res_id=g.id where imd.module='support_helpdesk_ticket' order by g.id;"
```

Luego agrega el usuario admin al grupo necesario.

Ejemplo, si `admin` es `uid = 2` y el grupo `Helpdesk Manager` es `gid = 19`:

```bash
PGPASSWORD=odoo psql -h localhost -U odoo -d mi_empresa -c "insert into res_groups_users_rel (gid, uid) select 19, 2 where not exists (select 1 from res_groups_users_rel where gid=19 and uid=2);"
```

Despues reinicia Odoo y vuelve a iniciar sesion.

Tambien puedes hacerlo manualmente desde Odoo:

1. Entra a `Settings`.
2. Activa el modo desarrollador.
3. Ve a `Settings > Users & Companies > Users`.
4. Abre el usuario `Administrator`.
5. Agrega el grupo del modulo, por ejemplo `Helpdesk Manager`.
6. Guarda.
7. Cierra sesion y vuelve a entrar.

## 10. Comandos utiles

Ver procesos usando el puerto de Odoo:

```bash
lsof -nP -iTCP:8069 -sTCP:LISTEN
```

Ver ultimas lineas del log:

```bash
tail -n 100 odoo.log
```

Ver el log en tiempo real:

```bash
tail -f odoo.log
```

Para salir de `tail -f`, presiona:

```text
Ctrl + C
```

Si quieres que Odoo muestre los logs directamente en la terminal, comenta o elimina la linea `logfile` en `config/odoo.config`:

```ini
; logfile = /Users/angel/Documents/Projects/odoo/odoo.log
```

Luego vuelve a ejecutar Odoo. Sin `logfile`, la salida se imprime en la terminal.

Probar si Odoo responde:

```bash
curl -I http://localhost:8069
```

Ver modulos personalizados detectados por carpeta:

```bash
find . -maxdepth 4 -type f -name '__manifest__.py'
```

## 11. Problemas comunes

### El modulo no aparece en Apps

Actualiza la lista de aplicaciones desde Odoo o reinstala/actualiza por CLI:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config -u support_helpdesk_ticket --stop-after-init
```

### El menu no aparece aunque el modulo esta instalado

Revisa permisos/grupos del usuario. El menu puede estar restringido por grupos.

### Error de puerto ocupado

Significa que ya hay un Odoo corriendo en `8069`.

```bash
lsof -nP -iTCP:8069 -sTCP:LISTEN
kill PID
```

### Error de base no inicializada

Inicializa la base con:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config -i base --stop-after-init
```

## 12. Crear un modulo personalizado desde cero

Ejemplo de modulo:

```text
mi_modulo
```

### 12.1 Crear carpetas

Desde la raiz del proyecto:

```bash
mkdir -p mi_modulo/models mi_modulo/controllers mi_modulo/views mi_modulo/security
```

La estructura esperada:

```text
mi_modulo/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── solicitud.py
├── controllers/
│   ├── __init__.py
│   └── main.py
├── views/
│   └── templates.xml
└── security/
    └── ir.model.access.csv
```

### 12.2 Crear `__manifest__.py`

Archivo:

```text
mi_modulo/__manifest__.py
```

Contenido:

```python
{
    "name": "Mi Modulo",
    "version": "19.0.1.0.0",
    "category": "Custom",
    "summary": "Mi primer modulo personalizado",
    "depends": ["base", "website"],
    "data": [
        "security/ir.model.access.csv",
        "views/templates.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
```

### 12.3 Crear `__init__.py` principal

Archivo:

```text
mi_modulo/__init__.py
```

Contenido:

```python
from . import models
from . import controllers
```

### 12.4 Crear un modelo

Archivo:

```text
mi_modulo/models/__init__.py
```

Contenido:

```python
from . import solicitud
```

Archivo:

```text
mi_modulo/models/solicitud.py
```

Contenido:

```python
from odoo import fields, models


class MiSolicitud(models.Model):
    _name = "mi.solicitud"
    _description = "Mi Solicitud"

    name = fields.Char(required=True)
    email = fields.Char(required=True)
    message = fields.Text()
```

### 12.5 Crear permisos

Archivo:

```text
mi_modulo/security/ir.model.access.csv
```

Contenido:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_mi_solicitud_user,mi.solicitud.user,model_mi_solicitud,base.group_user,1,1,1,1
```

Sin este archivo, Odoo puede crear el modelo, pero los usuarios no podran verlo ni usarlo correctamente.

### 12.6 Crear un controlador web

Archivo:

```text
mi_modulo/controllers/__init__.py
```

Contenido:

```python
from . import main
```

Archivo:

```text
mi_modulo/controllers/main.py
```

Contenido:

```python
from odoo import http
from odoo.http import request


class MiFormulario(http.Controller):

    @http.route("/mi-formulario", type="http", auth="public", website=True)
    def formulario(self, **kwargs):
        return request.render("mi_modulo.formulario_template")

    @http.route("/mi-formulario/enviar", type="http", auth="public", website=True, methods=["POST"], csrf=True)
    def enviar(self, **post):
        request.env["mi.solicitud"].sudo().create({
            "name": post.get("name"),
            "email": post.get("email"),
            "message": post.get("message"),
        })
        return request.render("mi_modulo.gracias_template")
```

### 12.7 Crear vistas web

Archivo:

```text
mi_modulo/views/templates.xml
```

Contenido:

```xml
<odoo>
    <template id="formulario_template" name="Mi Formulario">
        <t t-call="website.layout">
            <div class="container py-5">
                <h1>Mi formulario</h1>

                <form action="/mi-formulario/enviar" method="post">
                    <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>

                    <label>Nombre</label>
                    <input type="text" name="name" required="required" class="form-control"/>

                    <label>Email</label>
                    <input type="email" name="email" required="required" class="form-control"/>

                    <label>Mensaje</label>
                    <textarea name="message" class="form-control"/>

                    <button type="submit" class="btn btn-primary mt-3">
                        Enviar
                    </button>
                </form>
            </div>
        </t>
    </template>

    <template id="gracias_template" name="Gracias">
        <t t-call="website.layout">
            <div class="container py-5">
                <h1>Gracias</h1>
                <p>Tu solicitud fue enviada correctamente.</p>
            </div>
        </t>
    </template>
</odoo>
```

### 12.8 Instalar el modulo

Deten Odoo si esta corriendo:

```bash
lsof -nP -iTCP:8069 -sTCP:LISTEN
kill PID
```

Instala el modulo:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config -i mi_modulo --stop-after-init
```

### 12.9 Levantar Odoo

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config
```

### 12.10 Probar el formulario

Abre:

```text
http://localhost:8069/mi-formulario
```

### 12.11 Actualizar despues de cambios

Cada vez que cambies modelos, vistas, seguridad o templates:

```bash
PYTHONPATH=odoo-19.0.post20260606 .venv/bin/python odoo-19.0.post20260606/setup/odoo -c config/odoo.config -u mi_modulo --stop-after-init
```

Luego vuelve a levantar Odoo.
