"""Post-migrate: 19.0.1.0.2 -> 19.0.1.0.3.

Habilita carga multiple para las fotos del vehiculo existentes.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        _logger.info(
            "risk_module 19.0.1.0.3 post-migrate: fresh install detected, "
            "skipping data fix (data files will populate defaults)."
        )
        return

    _logger.info(
        "risk_module 19.0.1.0.3 post-migrate: enabling vehicle_photo multiple uploads "
        "(previous version=%s).",
        version,
    )
    cr.execute(
        """
        UPDATE risk_document_requirement
           SET allow_multiple_files = TRUE,
               max_files = 3,
               allowed_file_extensions = 'jpg,jpeg,png'
         WHERE document_type = 'vehicle_photo'
        """
    )
    requirement_count = cr.rowcount
    cr.execute(
        """
        UPDATE risk_module_document
           SET allow_multiple_files = TRUE,
               max_files = 3,
               allowed_file_extensions = 'jpg,jpeg,png'
         WHERE document_type = 'vehicle_photo'
        """
    )
    document_count = cr.rowcount
    _logger.info(
        "risk_module 19.0.1.0.3 post-migrate: updated %s requirements and %s documents.",
        requirement_count,
        document_count,
    )
