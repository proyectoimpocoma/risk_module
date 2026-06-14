"""Post-migrate: 19.0.1.0.0 -> 19.0.1.0.1.

Mueve la logica de data-fix que antes vivia en
``risk.message.template.init()``. Ese metodo se ejecutaba en cada
carga del modulo; este script corre una sola vez al actualizar a
19.0.1.0.1, que es lo correcto.
"""

import logging

_logger = logging.getLogger(__name__)


CATEGORY_TO_MESSAGE_TYPE = {
    "document_rejection": "document",
    "submission_rejection": "final_rejection",
    "submission_correction": "correction",
    "document_request": "document",
    "document_rejected_email": "document",
}


def _category_default_values(cr, category):
    """Replica las defaults que vivian en el modelo.

    Mantenemos este dict sincronizado con
    ``risk.message.template._category_default_values``. Si se anade
    una nueva categoria, actualizar ambos sitios.
    """
    defaults = {
        "document_rejection": {
            "channel": "modal",
            "recipient_type": "third_party",
            "usage_location": "Modal de rechazo de documento y correo de documento rechazado.",
            "available_variables": "documento, solicitud, placa, tercero",
        },
        "submission_rejection": {
            "channel": "modal",
            "recipient_type": "third_party",
            "usage_location": "Modal Rechazar definitivamente en la solicitud.",
            "available_variables": "solicitud, placa, propietario, conductor, motivo",
        },
        "submission_correction": {
            "channel": "modal",
            "recipient_type": "third_party",
            "usage_location": "Modal Solicitar correccion y portal del tercero.",
            "available_variables": "solicitud, placa, secciones_a_corregir, motivo",
        },
        "document_request": {
            "channel": "email",
            "recipient_type": "third_party",
            "usage_location": "Correo enviado al solicitar documentos.",
            "available_variables": "solicitud, placa, documentos_solicitados",
        },
        "document_rejected_email": {
            "channel": "email",
            "recipient_type": "third_party",
            "usage_location": "Correo enviado al rechazar un documento individual.",
            "available_variables": "documento, solicitud, placa, motivo",
        },
    }
    return defaults.get(category, {})


def migrate(cr, version):
    if not version:
        _logger.info(
            "risk_module 19.0.1.0.1 post-migrate: fresh install detected, "
            "skipping data fix (data files will populate defaults)."
        )
        return

    _logger.info(
        "risk_module 19.0.1.0.1 post-migrate: applying category defaults "
        "to risk_message_template (previous version=%s).", version
    )

    for category, message_type in CATEGORY_TO_MESSAGE_TYPE.items():
        defaults = _category_default_values(cr, category)
        cr.execute(
            """
            UPDATE risk_message_template
               SET message_type = %s
             WHERE category = %s
               AND (message_type IS NULL OR message_type = 'document')
            """,
            [message_type, category],
        )
        cr.execute(
            """
            UPDATE risk_message_template
               SET channel = COALESCE(NULLIF(channel, ''), %s),
                   recipient_type = COALESCE(NULLIF(recipient_type, ''), %s),
                   usage_location = COALESCE(NULLIF(usage_location, ''), %s),
                   available_variables = COALESCE(NULLIF(available_variables, ''), %s)
             WHERE category = %s
            """,
            [
                defaults.get("channel"),
                defaults.get("recipient_type"),
                defaults.get("usage_location"),
                defaults.get("available_variables"),
                category,
            ],
        )

    _logger.info("risk_module 19.0.1.0.1 post-migrate: data fix complete.")
