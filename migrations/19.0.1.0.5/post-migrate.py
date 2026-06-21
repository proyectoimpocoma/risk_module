"""Post-migrate: 19.0.1.0.4 -> 19.0.1.0.5.

Ajusta la ruta de documentos de vehiculo para usar la placa como carpeta.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        _logger.info(
            "risk_module 19.0.1.0.5 post-migrate: fresh install detected, "
            "skipping data fix (data files will populate defaults)."
        )
        return

    _logger.info(
        "risk_module 19.0.1.0.5 post-migrate: setting vehicle SharePoint route "
        "folder template to plate (previous version=%s).",
        version,
    )
    cr.execute(
        """
        UPDATE risk_sharepoint_route
           SET folder_template = %s
         WHERE party = 'vehicle'
        """,
        ["{placa}"],
    )
    _logger.info(
        "risk_module 19.0.1.0.5 post-migrate: updated %s vehicle SharePoint routes.",
        cr.rowcount,
    )
