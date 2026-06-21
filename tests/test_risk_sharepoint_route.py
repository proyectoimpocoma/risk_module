"""Tests del motor de plantillas y del modelo de rutas de SharePoint.

Estas pruebas no tocan la red: el renderer es texto puro y el contexto se
construye desde una solicitud/documento de prueba.
"""
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import RiskModuleTestCase

SERVICE = "odoo.addons.risk_module.models.risk_sharepoint_service.RiskSharepointService"


@tagged("post_install", "-at_install")
class TestRiskSharepointRoute(RiskModuleTestCase):
    def setUp(self):
        super().setUp()
        self.service = self.env["risk.sharepoint.service"]
        self.Route = self.env["risk.sharepoint.route"]

    # ── Renderer puro ─────────────────────────────────────────────────
    def test_render_template_replaces_known_tokens(self):
        result = self.service._render_template(
            "{placa}-{tipo}", {"placa": "ABC123", "tipo": "Conductor"}
        )
        self.assertEqual(result, "ABC123-Conductor")

    def test_render_template_drops_unknown_and_empty(self):
        # token desconocido y token vacio se eliminan (no quedan {x} colgando).
        result = self.service._render_template(
            "{placa}-{desconocido}{remolque}", {"placa": "X", "remolque": ""}
        )
        self.assertEqual(result, "X-")

    def test_path_segments_split_and_drop_empty(self):
        segments = self.service._render_path_segments(
            "{remolque}/{ref} {placa}/{tipo}",
            {"remolque": "", "ref": "SOL-1", "placa": "ABC123", "tipo": "Vehiculo"},
        )
        # El primer segmento (remolque vacio) se descarta.
        self.assertEqual(segments, ["SOL-1 ABC123", "Vehiculo"])

    def test_path_segments_sanitize_invalid_chars(self):
        segments = self.service._render_path_segments(
            "{tipo}", {"tipo": "a:b*c"}
        )
        # Los caracteres invalidos de SharePoint se sustituyen por espacio.
        self.assertEqual(segments, ["a b c"])

    def test_filename_template_keeps_extension(self):
        name = self.service._apply_filename_template(
            "{documento} {placa}",
            {"documento": "SOAT", "placa": "ABC123"},
            "original.pdf",
        )
        self.assertEqual(name, "SOAT ABC123.pdf")

    def test_filename_template_append_id_for_uniqueness(self):
        name = self.service._apply_filename_template(
            "{documento}",
            {"documento": "SOAT"},
            "foto.jpg",
            append_id=True,
            rec_id=7,
        )
        self.assertEqual(name, "SOAT (7).jpg")

    def test_filename_template_falls_back_to_original(self):
        # Plantilla que se resuelve vacia => se usa el nombre original.
        name = self.service._apply_filename_template(
            "{remolque}", {"remolque": ""}, "documento.pdf"
        )
        self.assertEqual(name, "documento.pdf")

    # ── Contexto de variables ─────────────────────────────────────────
    def test_token_context_from_submission(self):
        submission = self.make_submission(plate="XYZ789")
        document = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        ctx = document._sp_token_context()
        self.assertEqual(ctx["placa"], "XYZ789")
        self.assertEqual(ctx["propietario"], "Transportes Demo")
        self.assertEqual(ctx["conductor"], "Conductor Demo")
        self.assertEqual(ctx["tipo"], "Vehiculo")
        self.assertEqual(ctx["documento"], "SOAT")
        self.assertEqual(ctx["fecha"], "2026-05-09")
        self.assertEqual(ctx["anio"], "2026")
        self.assertEqual(ctx["mes"], "05")
        self.assertEqual(ctx["id"], document.id)

    def test_token_context_renders_default_route(self):
        # Integracion renderer + contexto con la plantilla por defecto del tipo.
        submission = self.make_submission(plate="XYZ789")
        document = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        route = self.Route._route_for_party("vehicle")
        ctx = document._sp_token_context()
        segments = self.service._render_path_segments(
            route.folder_template, ctx
        )
        # {ref} {placa}/Vehiculo => [<ref> XYZ789, Vehiculo]
        self.assertEqual(segments[-1], "Vehiculo")
        self.assertIn("XYZ789", segments[0])
        name = self.service._apply_filename_template(
            route.filename_template, ctx, document.filename or "doc.pdf"
        )
        self.assertEqual(name, "SOAT XYZ789.pdf")

    # ── Modelo de rutas ───────────────────────────────────────────────
    def test_seed_routes_loaded(self):
        parties = set(self.Route.search([]).mapped("party"))
        self.assertEqual(
            parties, {"driver", "owner", "vehicle", "semi_trailer", "other"}
        )

    def test_route_for_party_skips_inactive(self):
        route = self.Route._route_for_party("driver")
        self.assertTrue(route)
        route.active = False
        self.assertFalse(self.Route._route_for_party("driver"))

    def test_check_templates_rejects_unknown_token(self):
        route = self.Route._route_for_party("other")
        with self.assertRaises(ValidationError):
            # Las @api.constrains se validan al hacer flush, no en la asignacion.
            route.folder_template = "{ref}/{inexistente}"
            route.flush_recordset()

    def test_check_templates_accepts_known_tokens(self):
        route = self.Route._route_for_party("other")
        route.write({
            "folder_template": "{ref} {placa}/{propietario}",
            "filename_template": "{documento} {conductor}",
        })
        route.flush_recordset()
        self.assertEqual(route.folder_template, "{ref} {placa}/{propietario}")

    # ── Enganche en la subida (fase 3) ────────────────────────────────
    def test_folder_segments_use_active_route(self):
        submission = self.make_submission(plate="XYZ789")
        doc = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        segments = doc._sp_folder_segments()
        # raiz global + plantilla {ref} {placa}/Vehiculo
        self.assertEqual(segments[0], "Solicitudes")
        self.assertEqual(segments[-1], "Vehiculo")
        self.assertIn("XYZ789", segments[1])

    def test_folder_segments_fallback_without_route(self):
        submission = self.make_submission(plate="XYZ789")
        doc = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        self.Route._route_for_party("vehicle").active = False
        self.assertEqual(
            doc._sp_folder_segments(), doc._sp_classic_folder_segments()
        )

    def test_filename_single_uses_route(self):
        submission = self.make_submission(plate="XYZ789")
        doc = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        doc.filename = "soat.pdf"
        name = doc._sp_filename()
        self.assertTrue(name.startswith("SOAT XYZ789"))
        self.assertTrue(name.endswith(".pdf"))
        # append_id por defecto => garantiza unicidad con el id del documento.
        self.assertIn("(%s)" % doc.id, name)

    def test_filename_multi_forces_unique_id(self):
        submission = self.make_submission(plate="XYZ789")
        doc = self.make_document(
            submission,
            document_type="soat",
            party="vehicle",
            allow_multiple_files=True,
            max_files=5,
        )
        doc_file = self.env["risk.module.document.file"].create({
            "document_id": doc.id,
            "filename": "foto.jpg",
            "file": self.TEST_DUMMY_FILE,
        })
        name = doc._sp_filename(document_file=doc_file)
        self.assertTrue(name.endswith(".jpg"))
        self.assertIn("(%s)" % doc_file.id, name)

    def test_filename_fallback_without_route(self):
        submission = self.make_submission(plate="XYZ789")
        doc = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        doc.filename = "soat.pdf"
        self.Route._route_for_party("vehicle").active = False
        self.assertEqual(doc._sp_filename(), "soat.pdf")

    # ── Carpeta destino por tipo (fase 5) ─────────────────────────────
    def test_upload_target_without_dest_uses_global_root(self):
        submission = self.make_submission(plate="XYZ789")
        doc = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        segments, base, drive = doc._sp_upload_target()
        self.assertIsNone(base)
        self.assertIsNone(drive)
        # Sin destino: el primer segmento es la carpeta raiz global.
        self.assertEqual(segments[0], "Solicitudes")

    def test_upload_target_with_dest_is_relative(self):
        route = self.Route._route_for_party("vehicle")
        route.write({
            "dest_drive_id": "DRV",
            "dest_item_id": "ITEM",
            "dest_label": "Biblioteca / 2 Vehiculo",
        })
        submission = self.make_submission(plate="XYZ789")
        doc = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        segments, base, drive = doc._sp_upload_target()
        self.assertEqual(base, "ITEM")
        self.assertEqual(drive, "DRV")
        # Segmentos relativos a la carpeta destino: sin la raiz global.
        self.assertNotIn("Solicitudes", segments)
        self.assertEqual(segments[-1], "Vehiculo")

    def test_sync_passes_dest_to_store_file(self):
        route = self.Route._route_for_party("vehicle")
        route.write({
            "dest_drive_id": "DRV",
            "dest_item_id": "ITEM",
            "dest_label": "Biblioteca / 2 Vehiculo",
        })
        submission = self.make_submission(plate="XYZ789")
        doc = self.make_document(
            submission, document_type="soat", party="vehicle"
        )
        doc.write({"file": self.TEST_DUMMY_FILE, "filename": "soat.pdf"})
        store_result = {"item_id": "I", "web_url": "u", "drive_id": "DRV"}
        with patch(SERVICE + "._store_file", return_value=store_result) as mocked:
            doc._sync_to_sharepoint()
        self.assertEqual(mocked.call_args.kwargs.get("base_item_id"), "ITEM")
        self.assertEqual(mocked.call_args.kwargs.get("drive_id"), "DRV")

    def test_clear_folder_resets_to_global_root(self):
        route = self.Route._route_for_party("vehicle")
        route.write({
            "dest_drive_id": "DRV",
            "dest_item_id": "ITEM",
            "dest_label": "Biblioteca / 2 Vehiculo",
        })
        route.action_clear_folder()
        self.assertFalse(route.dest_item_id)
        self.assertFalse(route.dest_drive_id)
        self.assertFalse(route.dest_label)
