"""Shared test infrastructure for risk_module.

Provee ``RiskModuleTestCase``, una base para tests con factories
reusables (``make_portal_user``, ``make_submission``, ``make_document``,
``make_validation``). Cada factory construye solo lo que el test
necesita, evitando pagar el costo de un ``setUp`` pesado.

Convenciones:
    - Los factories usan defaults que reflejan los valores que el
      formulario publico real envia.
    - Las constantes de test viven como atributos de clase
      (``TEST_PLATE``, ``TEST_OWNER_EMAIL``, ...).
    - El tag ``post_install, -at_install`` se aplica a la base, asi
      las clases hijas no necesitan repetirlo.
"""
from datetime import timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class RiskModuleTestCase(TransactionCase):
    """Base class for risk_module tests."""

    TEST_PLATE = "ABC123"
    TEST_OWNER_EMAIL = "operaciones@example.com"
    TEST_DRIVER_EMAIL = "conductor@example.com"
    TEST_PORTAL_A = "portal-a@example.com"
    TEST_PORTAL_B = "portal-b@example.com"
    TEST_DUMMY_FILE = "ZHVtbXk="  # base64 of "dummy"
    TEST_DUMMY_FILENAME = "documento.pdf"

    def make_portal_user(self, login, name, **extra):
        """Create a portal user with the given login and name.

        Extra keyword args are merged into the ``res.users`` vals.
        The user gets the ``base.group_portal`` group by default.
        """
        values = {
            "name": name,
            "login": login,
            "email": login,
            "group_ids": [
                Command.set([self.env.ref("base.group_portal").id])
            ],
        }
        values.update(extra)
        return (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(values)
        )

    def make_submission(
        self,
        owner=None,
        state="draft",
        plate=None,
        with_owner=True,
        with_driver=True,
        **overrides,
    ):
        """Create a risk submission with sensible defaults.

        Args:
            owner: portal user that owns the submission. If given,
                ``partner_id``, ``portal_user_id`` and
                ``submitted_by_id`` are set from it.
            state: initial state of the submission.
            plate: vehicle plate (normalized to uppercase by the
                model). Defaults to ``TEST_PLATE``.
            with_owner: include owner demographics in defaults.
            with_driver: include driver demographics in defaults.
            **overrides: arbitrary ``risk.module`` field values.
        """
        values = {
            "vehicle_plate": plate or self.TEST_PLATE,
            "form_date": "2026-05-09",
            "state": state,
            "satellite_url": "https://rastreo.example.com",
        }
        if owner:
            values.update(
                self.env["risk.module"]._portal_ownership_values(owner)
            )
        if with_owner:
            values.update(
                {
                    "owner_name": "Transportes Demo",
                    "owner_document_type": "nit",
                    "owner_document_number": "123456789-0",
                    "owner_phone": "3001234567",
                    "owner_email": self.TEST_OWNER_EMAIL,
                }
            )
        if with_driver:
            values.update(
                {
                    "driver_name": "Conductor Demo",
                    "driver_document_number": "12345678",
                    "driver_phone": "3007654321",
                    "driver_email": self.TEST_DRIVER_EMAIL,
                    "driver_is_fit": "yes",
                    "driver_is_trained": "yes",
                }
            )
        if with_owner and with_driver:
            values.update(
                {
                    "owner_has_valid_study": "yes",
                    "driver_has_valid_study": "yes",
                }
            )
        values.update(overrides)
        return self.env["risk.module"].create(values)

    def make_document(
        self,
        submission,
        document_type="vehicle_registration",
        party="vehicle",
        name=None,
        state="pending",
        required=True,
        **overrides,
    ):
        """Create a risk document attached to ``submission``.

        If ``name`` is not given, the Spanish label is taken from
        the ``document_type`` selection on the model.
        """
        if name is None:
            name = dict(
                self.env["risk.module.document"]
                ._fields["document_type"]
                .selection
            ).get(document_type, document_type)
        values = {
            "submission_id": submission.id,
            "name": name,
            "document_type": document_type,
            "party": party,
            "state": state,
            "required": required,
        }
        values.update(overrides)
        return self.env["risk.module.document"].create(values)

    def make_validation(
        self,
        submission,
        status="pending",
        provider="validiti",
        profile="transport_driver_vehicle",
        **overrides,
    ):
        """Create a risk external validation record.

        The validation is left in the requested ``status``; callers
        that want to test the decision flow should call
        ``validation.apply_manual_result(...)`` explicitly so the
        test exercises the API under test.
        """
        values = {
            "submission_id": submission.id,
            "provider": provider,
            "profile": profile,
            "status": status,
        }
        values.update(overrides)
        return self.env["risk.external.validation"].create(values)

    def approve_document(
        self,
        document,
        file=None,
        filename=None,
        expiration_in_days=365,
        issued_today=True,
    ):
        """Approve a risk document, satisfying its date constraints.

        Reads the document's ``validity_required``, ``issue_date_required``,
        ``max_age_days`` and ``reject_expired`` flags and sets the
        required date fields with values that pass the constraints:

            - ``expiration_date`` = today + ``expiration_in_days``
            - ``issue_date`` = today (or stays unset if not required)

        Then writes ``state = "approved"`` in a separate call so the
        ``_check_approved_file`` constraint can validate the dates.
        Returns the document.
        """
        today = fields.Date.context_today(document)
        update = {
            "file": file or self.TEST_DUMMY_FILE,
            "filename": filename or self.TEST_DUMMY_FILENAME,
        }
        needs_expiration = document.validity_required or document.reject_expired
        if needs_expiration:
            update["expiration_date"] = today + timedelta(
                days=expiration_in_days
            )
        if issued_today and (
            document.issue_date_required or document.max_age_days
        ):
            update["issue_date"] = today
        document.write(update)
        document.write({"state": "approved"})
        return document
