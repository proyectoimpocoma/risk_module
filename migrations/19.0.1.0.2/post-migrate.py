"""Post-migrate: 19.0.1.0.1 -> 19.0.1.0.2.

Actualiza los documentos existentes de tipo 'vehicle_photo' para que
permitan hasta 3 archivos (max_files = 3).
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        _logger.info(
            "risk_module 19.0.1.0.2 post-migrate: fresh install detected, "
            "skipping data fix (data files will populate defaults)."
        )
        return

    _logger.info(
        "risk_module 19.0.1.0.2 post-migrate: updating vehicle_photo documents "
        "to allow up to 3 files (previous version=%s).", version
    )

    cr.execute(
        """
        UPDATE risk_module_document
           SET max_files = 3
         WHERE document_type = 'vehicle_photo'
           AND (max_files IS NULL OR max_files = 1)
        """
    )

    _logger.info(
        "risk_module 19.0.1.0.2 post-migrate: updated %s vehicle_photo documents.",
        cr.rowcount,
    )
