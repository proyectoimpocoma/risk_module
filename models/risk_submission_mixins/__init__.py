"""Mixins que extienden ``risk.module``.

Cada modulo aqui dentro aporta una preocupacion especifica y un
namespace de logger propio, manteniendo ``risk_submission.py`` con
solo los campos, el form-lock y los overrides de CRUD.
"""

from . import risk_submission_signature

__all__ = [
    "risk_submission_signature",
]
