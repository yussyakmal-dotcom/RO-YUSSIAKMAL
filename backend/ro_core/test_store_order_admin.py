"""Store order admin is readable but cannot bypass Draft/Kirim invariants."""
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Product, Schedule, StoreOrder, StoreOrderLine, Warehouse


class StoreOrderAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin-review", password="test-admin", email="admin@example.test",
        )
        self.store = Warehouse.objects.create(
            odoo_id=8101, code="T_BAN", name="Toko Bandara", kind="STORE",
        )
        self.kitchen = Warehouse.objects.create(
            odoo_id=8102, code="JP", name="Dapur Jajan Pasar", kind="KITCHEN",
        )
        self.schedule = Schedule.objects.create(code="PAGI", name="Pagi")
        self.product = Product.objects.create(
            odoo_id=8103, sku="11649", name="Produk Jajan Pasar",
        )
        self.order = StoreOrder.objects.create(
            store=self.store, kitchen=self.kitchen, order_date="2026-11-05",
            delivery_date="2026-11-07", schedule=self.schedule, status="KIRIM",
        )
        self.line = StoreOrderLine.objects.create(
            order=self.order, product=self.product, qty=Decimal("78.0000"),
        )
        self.client.force_login(self.user)

    def test_human_readable_labels(self):
        self.assertIn("11649", str(self.product))
        self.assertIn("Produk Jajan Pasar", str(self.product))
        self.assertIn("T_BAN", str(self.order))
        self.assertIn("JP", str(self.order))
        self.assertIn("11649", str(self.line))
        self.assertIn("Qty 78", str(self.line))
        self.assertNotIn("object (", str(self.line))

    def test_admin_list_shows_store_kitchen_sku_name_integer_qty(self):
        url = reverse("admin:ro_core_storeorderline_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        for label in ("Toko Bandara", "Dapur Jajan Pasar", "11649", "Produk Jajan Pasar", "78"):
            self.assertContains(response, label)
        self.assertNotContains(response, "StoreOrderLine object")

    def test_admin_detail_is_read_only_and_cannot_change_final_qty(self):
        url = reverse("admin:ro_core_storeorderline_change", args=[self.line.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Qty (unit)")
        self.assertContains(response, "78")
        self.assertNotContains(response, 'name="qty"')
        rejected = self.client.post(url, {"qty": "99", "_save": "Simpan"})
        self.assertEqual(rejected.status_code, 403)
        self.line.refresh_from_db()
        self.assertEqual(self.line.qty, Decimal("78"))
        self.assertFalse(admin.site._registry[StoreOrderLine].has_add_permission(
            rejected.wsgi_request
        ))

    def test_admin_cannot_edit_order_header_or_delete_rows(self):
        header_url = reverse("admin:ro_core_storeorder_change", args=[self.order.pk])
        self.assertEqual(self.client.get(header_url).status_code, 200)
        self.assertEqual(self.client.post(header_url, {"status": "DRAFT"}).status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "KIRIM")
        delete_url = reverse("admin:ro_core_storeorderline_delete", args=[self.line.pk])
        self.assertEqual(self.client.post(delete_url).status_code, 403)
        self.assertTrue(StoreOrderLine.objects.filter(pk=self.line.pk).exists())

    def test_fractional_legacy_qty_is_visible_not_rounded(self):
        self.line.qty = Decimal("1.5000")
        self.line.save(update_fields=["qty"])
        response = self.client.get(reverse("admin:ro_core_storeorderline_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "perlu koreksi desimal")
        self.line.refresh_from_db()
        self.assertEqual(self.line.qty, Decimal("1.5"))

    def test_admin_filters_by_status_and_searches_sku(self):
        url = reverse("admin:ro_core_storeorderline_changelist")
        self.assertContains(self.client.get(url, {"q": "11649"}), "Produk Jajan Pasar")
        self.assertContains(self.client.get(url, {"order__status__exact": "KIRIM"}), "11649")
