"""Initial category assignment: no Odoo writes; preserve local ownership."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .category_mapping import (
    CATEGORY_TO_WAREHOUSE, apply_category_mapping, preview_category_mapping,
)
from .models import Product, ProductionAssignment, Warehouse


class InitialMappingTest(TestCase):
    def setUp(self):
        self.legit = Warehouse.objects.create(
            odoo_id=41, code="LEGIT", name="Dapur Legit", kind="KITCHEN"
        )
        self.pastry = Warehouse.objects.create(
            odoo_id=42, code="PST", name="Dapur Pastry", kind="KITCHEN"
        )
        self.packing = Warehouse.objects.create(
            odoo_id=43, code="PCK", name="Dapur Packing", kind="PACKING"
        )
        self.legit_sku = Product.objects.create(
            odoo_id=101, sku="LEGIT-A", name="Legit A", category="Legit"
        )
        self.paket_sku = Product.objects.create(
            odoo_id=102, sku="PKT-A", name="Paket A", category="Paket"
        )
        self.pastry_sku = Product.objects.create(
            odoo_id=103, sku="PST-A", name="Pastry A", category="  PASTRY  "
        )
        self.raw_sku = Product.objects.create(
            odoo_id=104, sku="FLOUR", name="Tepung", category="Raw Materials"
        )
        self.nested_sku = Product.objects.create(
            odoo_id=105, sku="RAW-PST", name="Bahan Pastry",
            category="Raw Materials / Pastry",
        )

    def test_preview_is_read_only_and_no_fuzzy_nested_matching(self):
        preview = preview_category_mapping()
        self.assertEqual(preview.summary["new_mapping_candidates"], 3)
        self.assertEqual(preview.summary["unmatched_products"], 2)
        self.assertEqual(ProductionAssignment.objects.count(), 0)
        call_command("init_kitchen_mapping", stdout=StringIO())
        self.assertEqual(ProductionAssignment.objects.count(), 0)

    def test_apply_once_and_preserves_manual_changes(self):
        preview = preview_category_mapping()
        self.assertEqual(apply_category_mapping(preview), 3)
        self.assertEqual(
            ProductionAssignment.objects.get(product=self.paket_sku).kitchen,
            self.packing,
        )
        self.assertEqual(
            ProductionAssignment.objects.get(product=self.pastry_sku).kitchen,
            self.pastry,
        )
        self.assertFalse(
            ProductionAssignment.objects.filter(product=self.raw_sku).exists()
        )
        self.assertEqual(apply_category_mapping(preview), 0)  # idempotent

        # Once user changes kitchen in middleware, initial import won't revert it.
        assignment = ProductionAssignment.objects.get(product=self.legit_sku)
        assignment.kitchen = self.pastry
        assignment.save()
        self.legit_sku.category = "Pastry"
        self.legit_sku.save()
        self.assertEqual(apply_category_mapping(preview_category_mapping()), 0)
        assignment.refresh_from_db()
        self.assertEqual(assignment.kitchen_id, self.pastry.pk)

    def test_command_apply(self):
        out = StringIO()
        call_command("init_kitchen_mapping", "--apply", stdout=out)
        self.assertEqual(ProductionAssignment.objects.count(), 3)
        self.assertIn("Berhasil membuat 3 mapping", out.getvalue())

    def test_missing_or_wrong_warehouse_never_creates_partial_assignments(self):
        self.packing.kind = "STORE"
        self.packing.save()
        preview = preview_category_mapping()
        self.assertEqual(preview.summary["new_mapping_candidates"], 2)
        self.assertEqual(preview.summary["missing_warehouse_targets"], {"PCK": 1})
        with self.assertRaisesMessage(ValueError, "tidak lengkap"):
            apply_category_mapping(preview)
        self.assertEqual(ProductionAssignment.objects.count(), 0)
