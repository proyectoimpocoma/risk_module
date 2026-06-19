"""Tests de la integracion con SharePoint (Graph mockeado).

Se mockea ``risk.sharepoint.service._store_file`` para no tocar la red; los
parametros de ir.config_parameter se rellenan en ``setUp`` para que
``_is_enabled`` devuelva verdadero.
"""
from unittest.mock import patch

from odoo.tests.common import tagged

from .common import RiskModuleTestCase

SERVICE = "odoo.addons.risk_module.models.risk_sharepoint_service.RiskSharepointService"
STORE_RESULT = {"item_id": "ITEM1", "web_url": "https://sp/doc", "drive_id": "DRV"}


@tagged("post_install", "-at_install")
class TestRiskSharepoint(RiskModuleTestCase):
    def setUp(self):
        super().setUp()
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param("risk_module.sp_enabled", "True")
        set_param("risk_module.sp_tenant_id", "tid")
        set_param("risk_module.sp_client_id", "cid")
        set_param("risk_module.sp_client_secret", "secret")
        set_param("risk_module.sp_site", "contoso.sharepoint.com:/sites/Riesgos")
        set_param("risk_module.sp_root_folder", "Solicitudes")
        set_param("risk_module.sp_purge_local", "True")
        set_param("risk_module.sp_max_attempts", "3")
        self.submission = self.make_submission(state="documents_requested")
        self.document = self.make_document(self.submission, state="pending")

    def _upload(self, doc, file=None, filename="doc.pdf"):
        doc.write({"file": file or self.TEST_DUMMY_FILE, "filename": filename})

    # ------------------------------------------------------------------
    def test_upload_marks_pending_and_creates_version(self):
        self._upload(self.document)
        self.assertEqual(self.document.sharepoint_state, "pending")
        self.assertTrue(self.document.has_file)
        versions = self.document.version_ids
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions.result, "pending")
        self.assertFalse(versions.is_replacement)
        self.assertEqual(versions.version_number, 1)

    def test_sync_uploads_and_purges_local(self):
        self._upload(self.document)
        with patch(SERVICE + "._store_file", return_value=STORE_RESULT) as mocked:
            self.document._sync_to_sharepoint()
        mocked.assert_called_once()
        self.assertIsNone(mocked.call_args.kwargs.get("item_id"))
        self.assertEqual(self.document.sharepoint_state, "synced")
        self.assertEqual(self.document.sharepoint_item_id, "ITEM1")
        self.assertFalse(self.document.file)  # purgado
        self.assertTrue(self.document.has_file)  # via sharepoint_item_id
        self.assertEqual(self.document.version_ids.result, "uploaded")
        self.assertEqual(self.document.version_ids.sharepoint_item_id, "ITEM1")

    def test_reupload_after_rejection_uses_same_item(self):
        self._upload(self.document)
        with patch(SERVICE + "._store_file", return_value=STORE_RESULT):
            self.document._sync_to_sharepoint()
        self.document.write(
            {
                "state": "rejected",
                "rejection_reason": "illegible",
                "observations": "documento ilegible",
            }
        )
        # Reenvio del documento corregido.
        self._upload(self.document, file="Y29ycmVjdG8=", filename="fix.pdf")
        self.assertEqual(self.document.state, "received")
        self.assertFalse(self.document.rejection_reason)
        self.assertEqual(self.document.replacement_count, 1)
        self.assertEqual(self.document.sharepoint_state, "pending")
        last_version = self.document.version_ids.sorted("id")[-1]
        self.assertTrue(last_version.is_replacement)
        self.assertEqual(last_version.triggered_by_rejection, "illegible")
        self.assertEqual(last_version.version_number, 2)
        # La sincronizacion ahora sube una nueva version del mismo item.
        with patch(SERVICE + "._store_file", return_value=STORE_RESULT) as mocked:
            self.document._sync_to_sharepoint()
        self.assertEqual(mocked.call_args.kwargs.get("item_id"), "ITEM1")

    def test_sync_error_retries_then_fails(self):
        self._upload(self.document)
        with patch(SERVICE + "._store_file", side_effect=Exception("boom")):
            self.document._sync_to_sharepoint()
            self.assertEqual(self.document.sharepoint_state, "pending")
            self.assertEqual(self.document.sharepoint_attempts, 1)
            self.assertTrue(self.document.file)  # no se purga ante error
            self.document._sync_to_sharepoint()
            self.document._sync_to_sharepoint()
        self.assertEqual(self.document.sharepoint_attempts, 3)
        self.assertEqual(self.document.sharepoint_state, "error")
        self.assertEqual(self.document.version_ids.result, "failed")
        self.assertTrue(self.document.sharepoint_error)

    def test_action_open_file_prefers_local_until_synced(self):
        self._upload(self.document)
        action = self.document.action_open_file()
        self.assertIn("/web/content/", action["url"])
        with patch(SERVICE + "._store_file", return_value=STORE_RESULT):
            self.document._sync_to_sharepoint()
        action = self.document.action_open_file()
        self.assertEqual(action["url"], "https://sp/doc")

    def test_disabled_keeps_local_behaviour(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "risk_module.sp_enabled", "False"
        )
        doc = self.make_document(self.submission, state="pending")
        doc.write({"file": self.TEST_DUMMY_FILE, "filename": "x.pdf"})
        self.assertEqual(doc.sharepoint_state, "disabled")
        self.assertFalse(doc.version_ids)

    def test_cron_processes_pending(self):
        self._upload(self.document)
        with patch(SERVICE + "._store_file", return_value=STORE_RESULT) as mocked:
            self.env["risk.module.document"]._cron_sync_sharepoint()
        mocked.assert_called_once()
        self.assertEqual(self.document.sharepoint_state, "synced")

    # ------------------------------------------------------------------
    # Documentos multi-archivo (risk.module.document.file)
    # ------------------------------------------------------------------
    def _make_multifile_document(self):
        document = self.make_document(
            self.submission,
            document_type="vehicle_photo",
            party="vehicle",
            state="pending",
            allow_multiple_files=True,
            max_files=3,
        )
        files = self.env["risk.module.document.file"].create(
            [
                {
                    "document_id": document.id,
                    "filename": "foto1.jpg",
                    "file": self.TEST_DUMMY_FILE,
                    "sequence": 10,
                },
                {
                    "document_id": document.id,
                    "filename": "foto2.jpg",
                    "file": self.TEST_DUMMY_FILE,
                    "sequence": 20,
                },
            ]
        )
        return document, files

    def test_multifile_upload_marks_pending(self):
        document, files = self._make_multifile_document()
        self.assertEqual(set(files.mapped("sharepoint_state")), {"pending"})
        self.assertEqual(document.sharepoint_state, "pending")
        self.assertTrue(document.has_file)

    def test_multifile_cron_syncs_each_file_and_purges(self):
        document, files = self._make_multifile_document()
        with patch(SERVICE + "._store_file", return_value=STORE_RESULT) as mocked:
            self.env["risk.module.document"]._cron_sync_sharepoint()
        # Una llamada por archivo; el documento padre (sin file propio) no se sube.
        self.assertEqual(mocked.call_count, 2)
        for call in mocked.call_args_list:
            self.assertIsNone(call.kwargs.get("item_id"))
        self.assertEqual(set(files.mapped("sharepoint_state")), {"synced"})
        self.assertFalse(any(files.mapped("file")))  # purgado tras subir
        self.assertEqual(document.sharepoint_state, "synced")
        # Abrir el documento usa el enlace de SharePoint del primer archivo.
        action = document.action_open_file()
        self.assertEqual(action["url"], "https://sp/doc")

    def test_multifile_unique_filename_avoids_collision(self):
        document, files = self._make_multifile_document()
        # Aunque dos archivos tengan el mismo nombre original, el nombre en
        # SharePoint es unico por archivo (evita sobrescrituras).
        files[1].filename = "foto1.jpg"
        unique_names = files.mapped(lambda item: item._sp_unique_filename())
        self.assertEqual(len(set(unique_names)), len(files))

    def test_multifile_error_retries_then_fails(self):
        document, files = self._make_multifile_document()
        first_file, second_file = files[0], files[1]
        # El segundo archivo sube correctamente.
        with patch(SERVICE + "._store_file", return_value=STORE_RESULT):
            second_file._sync_to_sharepoint()
        # El primero falla hasta agotar los reintentos (max_attempts=3).
        with patch(SERVICE + "._store_file", side_effect=Exception("boom")):
            first_file._sync_to_sharepoint()
            self.assertEqual(first_file.sharepoint_state, "pending")
            self.assertEqual(first_file.sharepoint_attempts, 1)
            self.assertTrue(first_file.file)  # no se purga ante error
            first_file._sync_to_sharepoint()
            first_file._sync_to_sharepoint()
        self.assertEqual(first_file.sharepoint_attempts, 3)
        self.assertEqual(first_file.sharepoint_state, "error")
        # Sin archivos pendientes y con uno en error, el documento agrega "error".
        self.assertEqual(document.sharepoint_state, "error")
