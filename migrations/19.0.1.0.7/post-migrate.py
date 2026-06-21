"""Post-migrate: 19.0.1.0.6 -> 19.0.1.0.7.

Corrige las rutas SharePoint para que cada tipo use su propia entidad.
"""

import logging

_logger = logging.getLogger(__name__)

FOLDER_TEMPLATES = {
    "driver": "{conductor} {conductor_doc}",
    "owner": "{propietario} {propietario_doc}",
    "vehicle": "{placa}",
    "semi_trailer": "{remolque}",
    "other": "{documento}",
}


def migrate(cr, version):
    if not version:
        _logger.info(
            "risk_module 19.0.1.0.7 post-migrate: fresh install detected, "
            "skipping data fix (data files will populate defaults)."
        )
        return

    _logger.info(
        "risk_module 19.0.1.0.7 post-migrate: updating SharePoint route "
        "folder templates by party (previous version=%s).",
        version,
    )
    updated = 0
    for party, template in FOLDER_TEMPLATES.items():
        cr.execute(
            """
            UPDATE risk_sharepoint_route
               SET folder_template = %s
             WHERE party = %s
            """,
            [template, party],
        )
        updated += cr.rowcount
    _logger.info(
        "risk_module 19.0.1.0.7 post-migrate: updated %s SharePoint routes.",
        updated,
    )
