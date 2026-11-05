"""Read-only connector and local master import regression tests."""
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from .models import Product, ProductionAssignment, Warehouse
from .odoo_readonly import OdooReadError, OdooReadOnlyClient
from .odoo_master import (
    MasterSnapshot, apply_master, build_preview, download_master,
)


class OdooClientTest(SimpleTestCase):
    def test_search_read_uses_json2_only_and_bearer(self):
        response = MagicMock()
        response.__enter__.return_value = BytesIO(
            b'[{"id": 11, "code": "ROTI", "name": "Dapur Roti"}]'
        )
        with patch("ro_core.odoo_readonly.urlopen", return_value=response) as urlopen:
            client = OdooReadOnlyClient("https://example.odoo.com", "test-api-key")
            rows = client.search_read(
                "stock.warehouse", ["id", "code", "name"], limit=1,
            )
        self.assertEqual(len(rows), 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            request.full_url,
            "https://example.odoo.com/json/2/stock.warehouse/search_read",
        )
        self.assertEqual(request.get_header("Authorization"), "bearer test-api-key")
        self.assertEqual(request.data.count(b"search_read"), 0)

    def test_non_https_and_unapproved_models_are_blocked(self):
        with self.assertRaises(OdooReadError):
            OdooReadOnlyClient("http://example.odoo.com", "api-key")
        client = OdooReadOnlyClient("https://example.odoo.com", "api-key")
        with self.assertRaises(OdooReadError):
            client.search_read("res.users", ["id"])
        with self.assertRaises(ValueError):
            client.search_read("stock.warehouse", [], limit=2)


def sample_snapshot():
    return MasterSnapshot(
        warehouses=[
            {"id": 101, "code": "ROTI", "name": "Dapur Roti", "lot_stock_id": False},
            {"id": 102, "code": "PCK", "name": "Dapur Packing", "lot_stock_id": False},
        ],
        locations=[
            {"id": 201, "complete_name": "ROTI/Stock"},
            {"id": 202, "complete_name": "PCK/Packing"},
        ],
        products=[
            {
                "id": 301, "default_code": "ROTI-A", "name": "Roti A",
                "categ_id": [11, "Produk Jadi"], "uom_id": [1, "Units"],
                "product_tmpl_id": [31, "Roti A"],
            },
            {
                "id": 302, "default_code": "PAKET-X", "name": "Paket X",
                "categ_id": [12, "PAKET"], "uom_id": [1, "Units"],
                "product_tmpl_id": [32, "Paket X"],
            },
        ],
        boms=[
            {
                "id": 401, "product_id": False, "product_tmpl_id": [31, "Roti A"],
                "product_qty": 200, "product_uom_id": [1, "Units"], "type": "normal",
            },
            {
                "id": 402, "product_id": False, "product_tmpl_id": [32, "Paket X"],
                "product_qty": 1, "product_uom_id": [1, "Units"], "type": "normal",
            },
        ],
        bom_lines=[
            {
                "id": 501, "bom_id": [402, "Paket X"],
                "product_id": [301, "Roti A"], "product_qty": 2,
                "product_uom_id": [1, "Units"],
            },
        ],
    )


class FakeClient:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    def all_records(self, model, fields, domain=None):
        self.calls.append(model)
        table = {
            "stock.warehouse": self.snapshot.warehouses,
            "stock.location": self.snapshot.locations,
            "product.product": self.snapshot.products,
            "mrp.bom": self.snapshot.boms,
            "mrp.bom.line": self.snapshot.bom_lines,
        }
        yield from table[model]


class OdooMasterTest(TestCase):
    def test_download_only_reads_five_whitelisted_models(self):
        client = FakeClient(sample_snapshot())
        snapshot = download_master(client)
        self.assertEqual(len(snapshot.products), 2)
        self.assertEqual(
            client.calls,
            ["stock.warehouse", "stock.location", "product.product",
             "mrp.bom", "mrp.bom.line"],
        )

    def test_import_preserves_mapping_and_package_bom(self):
        snapshot = sample_snapshot()
        ws, locations, products, preview = build_preview(snapshot)
        self.assertEqual(preview["warehouses"], 2)
        self.assertEqual(preview["location_matches"], 2)
        self.assertEqual(preview["ambiguous_products"], 0)
        apply_master(ws, locations, products, preview)
        bread = Product.objects.get(odoo_id=301)
        paket = Product.objects.get(odoo_id=302)
        self.assertEqual(bread.bom_output_qty, Decimal("200"))
        self.assertEqual(paket.bom_components[0]["odoo_product_id"], 301)
        self.assertEqual(paket.bom_components[0]["qty"], "2")
        kitchen = Warehouse.objects.get(code="ROTI")
        packing = Warehouse.objects.get(code="PCK")
        self.assertEqual(kitchen.stock_location_odoo_id, 201)
        ProductionAssignment.objects.create(product=bread, kitchen=kitchen)

        # Odoo product name changes, but middleware ownership of assignment stays.
        snapshot.products[0]["name"] = "Roti A Baru"
        ws, locations, products, preview = build_preview(snapshot)
        apply_master(ws, locations, products, preview)
        bread.refresh_from_db()
        self.assertEqual(bread.name, "Roti A Baru")
        self.assertEqual(ProductionAssignment.objects.get(product=bread).kitchen_id,
                         kitchen.pk)
        self.assertEqual(packing.stock_location_odoo_id, 202)
        self.assertEqual(Warehouse.objects.count(), 2)

    def test_ambiguous_bom_preserves_previous_cache(self):
        snapshot = sample_snapshot()
        ws, locations, products, summary = build_preview(snapshot)
        apply_master(ws, locations, products, summary)
        snapshot.boms.append({
            "id": 403, "product_id": False,
            "product_tmpl_id": [31, "Roti A"],
            "product_qty": 100, "product_uom_id": [1, "Units"],
            "type": "normal",
        })
        ws, locations, products, summary = build_preview(snapshot)
        self.assertEqual(summary["ambiguous_products"], 1)
        apply_master(ws, locations, products, summary)
        self.assertEqual(Product.objects.get(odoo_id=301).bom_odoo_id, 401)

    def test_no_matched_warehouse_refuses_wrong_tenant(self):
        snapshot = sample_snapshot()
        snapshot.warehouses = [
            {"id": 999, "code": "OTHER", "name": "Other"}
        ]
        with self.assertRaises(OdooReadError):
            build_preview(snapshot)
