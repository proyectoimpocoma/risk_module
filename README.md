# Risk Module

Modulo Odoo 19 para gestionar la habilitacion de terceros en procesos de riesgo de Impocoma: captura publica de informacion de conductor/vehiculo, autorizaciones, firmas, validacion externa, aprobacion manual y control documental.

## Objetivo

El modulo cubre el primer flujo operativo para integrar conductores y vehiculos de carga pesada. Permite recibir una solicitud desde el sitio web, conservar trazabilidad de terminos y firmas, revisar internamente la solicitud, preparar una validacion externa con Validiti, aprobar o rechazar manualmente y solicitar documentos obligatorios antes de la aprobacion final.

## Dependencias

- `base`
- `website`
- `mail`
- `portal`
- `auth_signup`

## Modelos principales

- `risk.module`: solicitud principal de habilitacion.
- `risk.module.document`: documentos requeridos por solicitud.
- `risk.external.validation`: validaciones externas, actualmente preparadas para Validiti en modo manual.
- `risk.approval.wizard`: wizard de aprobacion/rechazo manual.
- `risk.external.validation.result.wizard`: wizard para registrar resultado manual de Validiti.

## Flujo funcional

1. El tercero ingresa a `/registro-conductor`.
2. Completa el formulario publico por pasos:
   - Vehiculo.
   - Propietario / tenedor.
   - Conductor.
   - Terminos y autorizaciones.
   - Firmas.
   - Revision e impresion.
3. El sistema crea una solicitud `risk.module`.
4. Desde backoffice, el equipo de riesgo mueve la solicitud por estados:
   - `draft`: borrador.
   - `submitted`: enviado.
   - `risk_review`: en revision de riesgo.
   - `external_validation_pending`: validacion externa pendiente.
   - `manual_approval_pending`: pendiente aprobacion manual.
   - `documents_requested`: documentos solicitados.
   - `documents_review`: documentos en revision.
   - `approved`: aprobado.
   - `rejected`: rechazado.
5. En validacion externa se puede preparar/enviar el payload para Validiti y registrar resultado manual.
6. Antes de aprobar definitivamente, se solicitan y aprueban documentos obligatorios.

## Formulario publico

Ruta principal:

```text
/registro-conductor
```

El tercero debe iniciar sesion antes de llenar la solicitud. Si no tiene cuenta, puede registrarse desde:

```text
/web/signup?redirect=/registro-conductor
```

El modulo activa el registro abierto de portal con `auth_signup.invitation_scope = b2c`, por lo que el login debe mostrar el enlace de creacion de cuenta despues de actualizar el modulo.

> **Diseno del formulario:** los 7 pasos usan el sistema de diseno Material 3 (`risk-vr-*`).
> La especificacion visual completa (paleta, tipografia, tamanos, componentes, breakpoints y
> hooks de JS) esta en [`DISENO_FORMULARIO.md`](DISENO_FORMULARIO.md).

Ruta imprimible protegida por token:

```text
/registro-conductor/imprimir/<submission_id>?token=<access_token>
```

El controlador guarda los pasos en sesion, valida campos obligatorios y crea/actualiza la solicitud:

- Placas colombianas.
- Correos.
- Cedulas y NIT.
- Celulares colombianos.
- Terminos aceptados.
- Firmas cuando propietario o conductor no tienen estudio vigente.

## Validacion externa con Validiti

La integracion queda implementada en modo manual/preparado porque no hay API publica documentada en el sitio de Validiti.

El boton **Enviar a Validiti** genera y almacena un payload con:

- Datos de la solicitud.
- Autorizacion de tratamiento de datos.
- Conductor.
- Propietario.
- Propietario registrado en licencia.
- Vehiculo y semi/remolque.

Luego el usuario puede registrar el resultado manualmente:

- `approved`: pasa a aprobacion manual.
- `manual_review`: pasa a aprobacion manual con trazabilidad.
- `rejected`: rechaza la solicitud.
- `error`: deja la solicitud pendiente de validacion externa.
- `skipped`: omite la validacion y pasa a aprobacion manual.

Pendiente para integracion API real:

- Endpoint de Validiti.
- Metodo de autenticacion.
- Ambiente sandbox/produccion.
- Esquema oficial de payload.
- Esquema oficial de respuesta.
- Webhook o consulta asincrona.
- Evidencia/PDF descargable.
- Politicas de retencion y tratamiento de datos.

## Documentos requeridos

Al usar **Solicitar documentos**, el modulo genera automaticamente documentos requeridos:

- Cedula del conductor.
- Licencia de conduccion.
- Cedula / NIT del propietario.
- Tarjeta de propiedad.
- SOAT.
- Revision tecnico-mecanica.
- Poliza.
- Estudio de seguridad vigente del propietario, si aplica.
- Estudio de seguridad vigente del conductor, si aplica.
- Documento del semi/remolque, si existe placa de semi/remolque.

Reglas implementadas:

- Un documento con archivo pasa de `pending` a `received`.
- No se puede aprobar un documento sin archivo.
- Rechazar documento exige observaciones.
- No se puede iniciar revision documental con documentos obligatorios pendientes.
- No se puede aprobar la solicitud si falta aprobar algun documento obligatorio.

## Backoffice

Menu principal:

```text
Riesgo
```

Submenus:

- `Vehiculos`: solicitudes de habilitacion.
- `Validaciones Externas`: registros de validacion externa.
- `Documentos`: documentos generados por solicitud.

La solicitud tiene pestañas para:

- Propietario / tenedor.
- Conductor.
- Firmas y terminos.
- Documentos.
- Validacion externa.
- Trazabilidad.
- Observaciones.

El chatter queda activo mediante `mail.thread` y `mail.activity.mixin`.

## Trazabilidad

El modulo guarda:

- Cambios de estado con tracking.
- Revisor de riesgo y fecha de revision.
- Usuario y fecha de aprobacion.
- Comentario de aprobacion.
- Usuario y fecha de rechazo.
- Motivo de rechazo.
- IP y user agent de firmas.
- Payload y resultado de validacion externa.

## Instalacion / actualizacion

Ejemplo en este entorno:

```bash
PYTHONPATH=/Users/angel/Documents/Projects/odoo/odoo-19.0.post20260606 \
/Users/angel/Documents/Projects/odoo/.venv/bin/python -m odoo \
  -c /Users/angel/Documents/Projects/odoo/config/odoo.config \
  -u risk_module \
  --stop-after-init
```

## Validaciones de desarrollo

Compilar Python:

```bash
python3 -m py_compile __init__.py models/*.py controllers/*.py wizards/*.py
```

Validar XML:

```bash
python3 - <<'PY'
from xml.etree import ElementTree as ET

files = [
    "views/risk_submission_report_actions.xml",
    "views/risk_submission_report_styles.xml",
    "views/risk_submission_report_templates.xml",
    "views/risk_submission_document_views.xml",
    "views/risk_external_validation_views.xml",
    "views/risk_submission_list_views.xml",
    "views/risk_submission_form_views.xml",
    "views/risk_submission_search_views.xml",
    "views/risk_submission_actions.xml",
    "views/risk_approval_wizard_views.xml",
    "views/risk_external_validation_result_wizard_views.xml",
    "views/risk_submission_menus.xml",
    "views/website_risk_submission_step_vehicle.xml",
    "views/website_risk_submission_step_owner.xml",
    "views/website_risk_submission_step_driver.xml",
    "views/website_risk_submission_step_terms.xml",
    "views/website_risk_submission_step_signatures.xml",
    "views/website_risk_submission_step_review.xml",
    "views/website_risk_submission_terms_modal.xml",
    "views/website_risk_submission_success.xml",
    "views/website_risk_submission_templates.xml",
]

for path in files:
    ET.parse(path)
    print(path, "ok")
PY
```

Validar JavaScript frontend:

```bash
node --check static/src/js/risk_submission_terms.js
node --check static/src/js/risk_submission_signatures.js
node --check static/src/js/risk_submission_print.js
```

Ejecutar tests del modulo:

```bash
PYTHONPATH=/Users/angel/Documents/Projects/odoo/odoo-19.0.post20260606 \
/Users/angel/Documents/Projects/odoo/.venv/bin/python -m odoo \
  -c /Users/angel/Documents/Projects/odoo/config/odoo.config \
  --http-port=8071 \
  -u risk_module \
  --test-enable \
  --test-tags /risk_module \
  --stop-after-init
```

## Estructura

```text
risk_module/
├── DISENO_FORMULARIO.md        # Especificacion visual del formulario publico (Material 3)
├── controllers/
│   ├── risk_submission_controller.py
│   ├── risk_submission_form_mapper.py
│   ├── risk_submission_form_schema.py
│   ├── risk_submission_form_session.py
│   ├── risk_submission_form_signatures.py
│   └── risk_submission_form_validation.py
├── models/
│   ├── risk_submission.py
│   ├── risk_submission_documents.py
│   ├── risk_submission_formatting.py
│   ├── risk_submission_validations.py
│   ├── risk_submission_validiti.py
│   ├── risk_submission_workflow.py
│   ├── risk_submission_document.py
│   └── risk_external_validation.py
├── security/
│   ├── groups.xml
│   └── ir.model.access.csv
├── static/src/
│   ├── css/
│   └── js/
├── views/
│   ├── risk_submission_list_views.xml
│   ├── risk_submission_form_views.xml
│   ├── risk_submission_search_views.xml
│   ├── risk_submission_actions.xml
│   ├── risk_submission_document_views.xml
│   ├── risk_external_validation_views.xml
│   ├── risk_submission_report_actions.xml
│   ├── risk_submission_report_styles.xml
│   ├── risk_submission_report_templates.xml
│   ├── risk_submission_menus.xml
│   ├── website_risk_submission_templates.xml
│   ├── website_risk_submission_step_*.xml
│   ├── website_risk_submission_terms_modal.xml
│   └── website_risk_submission_success.xml
├── wizards/
│   ├── risk_approval_wizard.py
│   └── risk_external_validation_result_wizard.py
└── tests/
    └── test_risk_submission.py
```

## Pendientes recomendados

- Asignar usuarios internos a los grupos `Usuario de Riesgo` o `Responsable de Riesgo`.
- Revisar periodicamente permisos de datos sensibles como claves satelitales, firmas, IP y documentos.
- Implementar API real de Validiti cuando haya documentacion.
- Agregar actividades automaticas para responsables de revision documental.
- Agregar alertas por vencimiento de documentos.
- Crear portal/carga publica de documentos si los terceros deben subir archivos directamente.
