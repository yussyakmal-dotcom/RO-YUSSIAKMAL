"""Manual Excel kitchen order template contract tests."""
from io import BytesIO
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from .models import Product, ProductionAssignment, Warehouse, AuditLog
from .order_template_excel import preview_xlsx, apply_xlsx


def xlsx(rows, name="pastry.xlsx"):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class KitchenTemplateTests(TestCase):
    def setUp(self):
        self.pastry = Warehouse.objects.create(
            odoo_id=100, code="PST", name="Dapur Pastry", kind="KITCHEN",
        )
        self.roti = Warehouse.objects.create(
            odoo_id=200, code="ROTI", name="Dapur Roti", kind="KITCHEN",
        )
        self.packing = Warehouse.objects.create(
            odoo_id=300, code="PCK", name="Dapur Packing", kind="PACKING",
        )
        self.almond = Product.objects.create(
            odoo_id=10, sku="12300", name="Almond Croissant M", category="Bukan Pastry",
        )
        self.beef = Product.objects.create(
            odoo_id=11, sku="12306", name="Beef Croissant M", category="Makanan",
        )
        self.inactive_product = Product.objects.create(
            odoo_id=12, sku="DISCONTINUED", name="Stopped", active=False,
        )
        self.user = get_user_model().objects.create_superuser(
            username="templateadmin", password="test-password-local",
            email="admin@example.test",
        )

    def test_preview_excel_does_not_write_and_import_is_idempotent(self):
        rows = [
            ["SKU", "NAMA", "AKTIF", "URUTAN"],
            ["12300", "Teks nama Excel jangan overwrite Odoo", "Aktif", 20],
            ["12306", "Beef Croissant M", "Nonaktif", 10],
        ]
        preview = preview_xlsx(self.pastry, xlsx(rows))
        self.assertTrue(preview.is_valid, preview.errors)
        self.assertEqual(preview.new_count, 2)
        self.assertEqual(ProductionAssignment.objects.count(), 0)
        result = apply_xlsx(preview, actor=self.user)
        self.assertEqual(result["created"], 2)
        self.assertFalse(
            ProductionAssignment.objects.get(product=self.beef).is_active
        )
        self.assertEqual(self.almond.name, "Almond Croissant M")
        self.assertEqual(apply_xlsx(preview, actor=self.user)["created"], 0)
        self.assertEqual(ProductionAssignment.objects.count(), 2)
        self.assertEqual(AuditLog.objects.filter(action="XLSX_IMPORT").count(), 1)

        # Missing Excel rows are NOT deleted or automatically deactivated.
        another = preview_xlsx(
            self.pastry, xlsx([["SKU"], ["12300"]]),
        )
        self.assertTrue(another.is_valid, another.errors)
        apply_xlsx(another)
        self.assertTrue(
            ProductionAssignment.objects.filter(product=self.beef).exists()
        )

    def test_warehouse_conflict_and_unknown_sku_block_entire_import(self):
        ProductionAssignment.objects.create(product=self.almond, kitchen=self.roti)
        invalid = preview_xlsx(self.pastry, xlsx([
            ["SKU", "AKTIF"], ["12300", "Aktif"], ["12306", "Aktif"]
        ]))
        self.assertFalse(invalid.is_valid)
        with self.assertRaises(ValueError):
            apply_xlsx(invalid)
        self.assertFalse(
            ProductionAssignment.objects.filter(product=self.beef).exists()
        )
        missing = preview_xlsx(self.pastry, xlsx([
            ["SKU"], ["12306"], ["NOT-FOUND"]
        ]))
        self.assertFalse(missing.is_valid)
        with self.assertRaises(ValueError):
            apply_xlsx(missing)

    def test_duplicate_sku_and_oodo_master_ambiguity_rejected(self):
        duplicate = preview_xlsx(self.pastry, xlsx([
            ["SKU"], ["12300"], ["12300"]
        ]))
        self.assertFalse(duplicate.is_valid)
        Product.objects.create(odoo_id=99, sku="12300", name="Duplicate code")
        ambiguous = preview_xlsx(self.pastry, xlsx([["SKU"], ["12300"]]))
        self.assertFalse(ambiguous.is_valid)
        self.assertIn("tidak unik", str(ambiguous.errors))

    def test_invalid_xlsx_is_validation_error_not_server_error(self):
        fake = SimpleUploadedFile("broken.xlsx", b"not-a-zip-file")
        with self.assertRaisesMessage(ValueError, "tidak valid"):
            preview_xlsx(self.pastry, fake)

    def test_active_flag_does_not_change_master_product(self):
        preview = preview_xlsx(self.pastry, xlsx([
            ["SKU", "AKTIF"], ["12300", "Nonaktif"]
        ]))
        apply_xlsx(preview)
        assignment = ProductionAssignment.objects.get(product=self.almond)
        self.assertFalse(assignment.is_active)
        self.almond.refresh_from_db()
        self.assertTrue(self.almond.active)

    def test_read_only_order_template_only_active_rows(self):
        ProductionAssignment.objects.create(
            product=self.almond, kitchen=self.pastry, is_active=True, sort_order=12,
        )
        ProductionAssignment.objects.create(
            product=self.beef, kitchen=self.pastry, is_active=False, sort_order=1,
        )
        url = reverse("kitchen-order-template", args=["PST"])
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"], [
            {"id": self.almond.id, "sku": "12300", "name": "Almond Croissant M", "qty": 0},
        ])
        self.assertEqual(self.client.get(
            reverse("kitchen-order-template", args=["T_BAN"])
        ).status_code, 404)

    def test_admin_upload_preview_then_apply(self):
        self.client.force_login(self.user)
        upload_url = reverse("admin:ro_core_productionassignment_upload")
        form = lambda: {
            "kitchen": self.pastry.id,
            "excel_file": xlsx([["SKU", "AKTIF"], ["12300", "Aktif"]]),
        }
        response = self.client.post(upload_url, {**form(), "action": "preview"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hasil Preview")
        self.assertEqual(ProductionAssignment.objects.count(), 0)
        response = self.client.post(upload_url, {**form(), "action": "apply"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductionAssignment.objects.count(), 1)
        template_url = reverse("admin:ro_core_productionassignment_download_template")
        result = self.client.get(template_url)
        self.assertEqual(result.status_code, 200)
        template = load_workbook(BytesIO(result.content), read_only=True)
        self.assertEqual(
            [cell.value for cell in template.active[1]], ["SKU", "NAMA", "AKTIF", "URUTAN"]
        )
        template.close()

    def test_template_can_be_edited_manually_without_category(self):
        mapping = ProductionAssignment.objects.create(
            product=self.almond, kitchen=self.pastry, is_active=True,
        )
        self.client.force_login(self.user)
        url = reverse("admin:ro_core_productionassignment_change", args=[mapping.pk])
        response = self.client.post(url, {
            "product": self.almond.pk, "kitchen": self.roti.pk,
            "sort_order": 5, "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        mapping.refresh_from_db()
        self.assertEqual(mapping.kitchen, self.roti)
        self.assertFalse(mapping.is_active)  # unchecked boolean
        self.assertTrue(AuditLog.objects.filter(action="ADMIN_EDIT").exists())
