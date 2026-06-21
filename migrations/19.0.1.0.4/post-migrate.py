"""Post-migrate: 19.0.1.0.3 -> 19.0.1.0.4.

Actualiza la estructura por defecto de carpetas SharePoint.
"""

import logging

_logger = logging.getLogger(__name__)

DEFAULT_FOLDER_TEMPLATE = "{conductor} {conductor_doc}"
VEHICLE_FOLDER_TEMPLATE = "{placa}"


def migrate(cr, version):
    if not version:
        _logger.info(
            "risk_module 19.0.1.0.4 post-migrate: fresh install detected, "
            "skipping data fix (data files will populate defaults)."
        )
        return

    _logger.info(
        "risk_module 19.0.1.0.4 post-migrate: updating SharePoint route folder templates "
        "(previous version=%s).",
        version,
    )
    cr.execute(
        """
        UPDATE risk_sharepoint_route
           SET folder_template = CASE
                    WHEN party = 'vehicle' THEN %s
                    ELSE %s
               END
         WHERE party IN ('driver', 'owner', 'vehicle', 'semi_trailer', 'other')
        """,
        [VEHICLE_FOLDER_TEMPLATE, DEFAULT_FOLDER_TEMPLATE],
    )
    _logger.info(
        "risk_module 19.0.1.0.4 post-migrate: updated %s SharePoint routes.",
        cr.rowcount,
    )
