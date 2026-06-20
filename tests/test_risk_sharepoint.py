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
GRAPH_CHILDREN_URL = (
    "https://graph.microsoft.com/v1.0/drives/"
    "b!gez_dayfjUOHGN7zIyyjsS4niVearxxOjuDIxfBOgt_o-0VZgd1PTpRbnPT0bI1_"
    "/items/01IHQFHOPOO3IRU3KVANHIQ7XLJCD6XP3U/children"
)


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

    def test_parse_graph_children_url(self):
        parsed = self.env["risk.sharepoint.service"]._parse_children_url(
            GRAPH_CHILDREN_URL
        )
        self.assertEqual(
            parsed["drive_id"],
            "b!gez_dayfjUOHGN7zIyyjsS4niVearxxOjuDIxfBOgt_o-0VZgd1PTpRbnPT0bI1_",
        )
        self.assertEqual(parsed["item_id"], "01IHQFHOPOO3IRU3KVANHIQ7XLJCD6XP3U")

    def test_store_file_uses_configured_root_item(self):
        set_param = self.env["ir.config_parameter"].sudo().set_param
        set_param(
            "risk_module.sp_drive_id",
            "b!gez_dayfjUOHGN7zIyyjsS4niVearxxOjuDIxfBOgt_o-0VZgd1PTpRbnPT0bI1_",
        )
        set_param("risk_module.sp_root_item_id", "01IHQFHOPOO3IRU3KVANHIQ7XLJCD6XP3U")
        service = self.env["risk.sharepoint.service"]
        with patch(
            SERVICE + "._ensure_folder_under_item",
            return_value="TARGET_FOLDER",
        ) as ensure_mock, patch(
            SERVICE + "._upload_to_parent_item",
            return_value=STORE_RESULT,
        ) as upload_mock:
            service._store_file(
                ["Solicitudes", "RISK ABC123", "Conductor"], "doc.pdf", b"abc"
            )
        ensure_mock.assert_called_once_with(
            "b!gez_dayfjUOHGN7zIyyjsS4niVearxxOjuDIxfBOgt_o-0VZgd1PTpRbnPT0bI1_",
            "01IHQFHOPOO3IRU3KVANHIQ7XLJCD6XP3U",
            ["RISK ABC123", "Conductor"],
        )
        upload_mock.assert_called_once()

    def test_list_children_by_item_returns_folders_and_files(self):
        service = self.env["risk.sharepoint.service"]
        with patch(SERVICE + "._request") as request_mock:
            request_mock.return_value.json.return_value = {
                "value": [
                    {"id": "F1", "name": "Carpeta", "folder": {}, "webUrl": "https://sp/f"},
                    {"id": "D1", "name": "doc.pdf", "file": {}, "size": 12, "webUrl": "https://sp/d"},
                ]
            }
            items = service._list_children_by_item("DRV", "ROOT")
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]["is_folder"])
        self.assertTrue(items[1]["is_file"])

    def test_wizard_upload_and_delete_test_file(self):
        wizard = self.env["risk.sharepoint.drive.selector"].create(
            {
                "stage": "folder",
                "drive_id": "Documentos",
                "selected_drive_id": "DRV",
                "current_item_id": "ROOT",
                "test_file": self.TEST_DUMMY_FILE,
                "test_filename": "prueba.pdf",
            }
        )
        with patch(
            SERVICE + "._upload_test_file",
            return_value={
                "id": "TEST_ITEM",
                "name": "prueba.pdf",
                "webUrl": "https://sp/prueba.pdf",
            },
        ) as upload_mock:
            wizard.action_upload_test_file()
        upload_mock.assert_called_once()
        self.assertEqual(wizard.test_upload_item_id, "TEST_ITEM")
        self.assertEqual(wizard.test_upload_web_url, "https://sp/prueba.pdf")
        with patch(SERVICE + "._delete") as delete_mock:
            wizard.action_delete_test_file()
        delete_mock.assert_called_once_with("TEST_ITEM", drive_id="DRV")
        self.assertFalse(wizard.test_upload_item_id)

    def test_wizard_create_folder(self):
        wizard = self.env["risk.sharepoint.drive.selector"].create(
            {
                "stage": "folder",
                "drive_id": "Documentos",
                "selected_drive_id": "DRV",
                "current_item_id": "ROOT",
                "new_folder_name": "Pruebas",
            }
        )
        with patch(SERVICE + "._create_folder_under_item") as create_mock:
            wizard.action_create_folder()
        create_mock.assert_called_once_with("DRV", "ROOT", "Pruebas")

    def test_wizard_lists_rows_and_opens_folder(self):
        root_children = [
            {
                "id": "F1",
                "name": "Contratos",
                "is_folder": True,
                "is_file": False,
                "size": 0,
                "web_url": "https://sp/f1",
            },
            {
                "id": "D1",
                "name": "guia.pdf",
                "is_folder": False,
                "is_file": True,
                "size": 12,
                "web_url": "https://sp/d1",
            },
        ]
        with patch(
            SERVICE + "._list_children_by_item",
            side_effect=[root_children, []],
        ) as list_mock:
            wizard = self.env["risk.sharepoint.drive.selector"].create(
                {
                    "stage": "folder",
                    "drive_id": "Documentos",
                    "selected_drive_id": "DRV",
                    "current_item_id": "ROOT",
                }
            )
            self.assertEqual(len(wizard.line_ids), 2)
            folder_line = wizard.line_ids.filtered(lambda line: line.is_folder)
            self.assertEqual(folder_line.name, "Contratos")
            folder_line.action_open_folder()
        self.assertEqual(wizard.current_item_id, "F1")
        self.assertEqual(wizard.current_path, "Contratos")
        self.assertEqual(list_mock.call_count, 2)
