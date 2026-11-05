"""Production-demand rekap is read-only, final-only, and role-protected."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    AuditLog, Product, ProductionAssignment, Schedule,
    StoreOrder, StoreOrderLine, Warehouse,
)


class ProductionDemandTests(TestCase):
    def setUp(self):
        self.store_a = Warehouse.objects.create(
            odoo_id=101, code="T_BAN", name="Toko Bandara", kind="STORE",
        )
        self.store_b = Warehouse.objects.create(
            odoo_id=102, code="T_KD", name="Toko Kedaton", kind="STORE",
        )
        self.store_c = Warehouse.objects.create(
            odoo_id=103, code="T_MET", name="Toko Metro", kind="STORE",
        )
        self.kitchen = Warehouse.objects.create(
            odoo_id=201, code="JP", name="Dapur Jajan Pasar", kind="KITCHEN",
        )
        self.pastry = Warehouse.objects.create(
            odoo_id=202, code="PST", name="Dapur Pastry", kind="KITCHEN",
        )
        self.subuh = Schedule.objects.create(code="SUBUH", name="Subuh")
        self.pagi = Schedule.objects.create(code="PAGI", name="Pagi")
        self.risoles = Product.objects.create(
            odoo_id=301, sku="10005", name="Risoles Mayo",
        )
        self.lemper = Product.objects.create(
            odoo_id=302, sku="10006", name="Lemper Ayam",
        )
        ProductionAssignment.objects.create(
            product=self.risoles, kitchen=self.kitchen,
            sort_order=20, is_active=True,
        )
        ProductionAssignment.objects.create(
            product=self.lemper, kitchen=self.kitchen,
            sort_order=10, is_active=True,
        )
        self.production_user = get_user_model().objects.create_user(
            username="prod", password="test-local-prod",
        )
        self.store_user = get_user_model().objects.create_user(
            username="store", password="test-local-store",
        )
        self.admin = get_user_model().objects.create_superuser(
            username="admin", password="test-local-admin", email="a@example.test",
        )
        prod = Group.objects.create(name="PRODUCTION")
        store = Group.objects.create(name="STORE")
        self.production_user.groups.add(prod)
        self.store_user.groups.add(store)
        self.url = reverse("production-demand")

    def create_order(
        self, store, status, lines=(), kitchen=None, schedule=None,
        delivery_date="2026-11-08", auto_submitted=False,
    ):
        order = StoreOrder.objects.create(
            store=store, kitchen=kitchen or self.kitchen,
            schedule=schedule or self.subuh,
            order_date="2026-11-06", delivery_date=delivery_date,
            status=status, auto_submitted=auto_submitted,
        )
        for product, qty in lines:
            StoreOrderLine.objects.create(order=order, product=product, qty=qty)
        return order

    def request_recap(self, **overrides):
        params = {
            "delivery_date": "2026-11-08",
            "kitchen_code": "JP",
            "schedule_code": "SUBUH",
        }
        params.update(overrides)
        return self.client.get(self.url, params)

    def test_aggregate_kirim_only_and_show_store_breakdown(self):
        a = self.create_order(
            self.store_a, "KIRIM",
            [(self.risoles, 25), (self.lemper, 7)],
        )
        b = self.create_order(
            self.store_b, "KIRIM",
            [(self.risoles, 40), (self.lemper, 10)],
            auto_submitted=True,
        )
        self.create_order(self.store_c, "DRAFT", [(self.risoles, 999)])
        self.client.force_login(self.production_user)
        response = self.request_recap()
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["basis"], "FINAL_KIRIM_ONLY")
        self.assertIsNone(data["production_date"])
        self.assertEqual(data["summary"], {
            "stores_total": 3, "stores_sent": 2, "stores_no_order": 0,
            "stores_draft": 1, "stores_not_entered": 0,
            "sku_count": 2, "qty_total": "82",
        })
        self.assertEqual(
            [(row["sku"], row["qty_total"]) for row in data["items"]],
            [("10006", "17"), ("10005", "65")],
        )
        risoles = data["items"][1]
        self.assertEqual(risoles["store_count"], 2)
        self.assertEqual(
            [(source["store_code"], source["qty"]) for source in risoles["sources"]],
            [("T_BAN", "25"), ("T_KD", "40")],
        )
        self.assertEqual(
            {s["order_id"] for s in risoles["sources"]}, {a.pk, b.pk},
        )
        self.assertEqual(risoles["sources"][1]["auto_submitted"], True)
        self.assertEqual(
            {s["store_code"]: s["status"] for s in data["store_statuses"]}["T_MET"],
            "DRAFT",
        )
        self.assertFalse(AuditLog.objects.exists())
        self.assertFalse(
            StoreOrder.objects.exclude(status__in=["DRAFT", "KIRIM"]).exists()
        )

    def test_no_order_and_not_entered_are_not_implicitly_zero_orders(self):
        self.create_order(self.store_a, "NO_ORDER")
        self.create_order(self.store_b, "KIRIM", [(self.risoles, 10)])
        self.client.force_login(self.production_user)
        data = self.request_recap().json()
        self.assertEqual(data["summary"]["stores_no_order"], 1)
        self.assertEqual(data["summary"]["stores_not_entered"], 1)
        self.assertEqual(data["summary"]["stores_sent"], 1)
        self.assertEqual(data["items"][0]["qty_total"], "10")
        self.assertEqual(
            {s["store_code"]: s["status"] for s in data["store_statuses"]},
            {"T_BAN": "NO_ORDER", "T_KD": "KIRIM", "T_MET": "NOT_ENTERED"},
        )

    def test_isolates_kitchen_date_schedule_and_inactive_template(self):
        assignment = ProductionAssignment.objects.get(product=self.risoles)
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        self.create_order(self.store_a, "KIRIM", [(self.risoles, 5)])
        self.create_order(
            self.store_a, "KIRIM", [(self.risoles, 77)],
            schedule=self.pagi,
        )
        self.create_order(
            self.store_a, "KIRIM", [(self.risoles, 88)],
            delivery_date="2026-11-09",
        )
        self.create_order(
            self.store_a, "KIRIM", [(self.risoles, 99)],
            kitchen=self.pastry,
        )
        self.client.force_login(self.production_user)
        data = self.request_recap().json()
        self.assertEqual(data["summary"]["qty_total"], "5")
        self.assertEqual(data["items"][0]["sku"], "10005")
        self.assertEqual(
            self.request_recap(schedule_code="PAGI").json()["summary"]["qty_total"],
            "77",
        )
        self.assertEqual(
            self.request_recap(kitchen_code="PST").json()["summary"]["qty_total"],
            "99",
        )

    def test_blocks_fractional_old_final_line_without_rounding(self):
        order = self.create_order(
            self.store_a, "KIRIM",
            [(self.risoles, Decimal("1.5000"))],
        )
        self.client.force_login(self.production_user)
        response = self.request_recap()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["invalid_count"], 1)
        self.assertEqual(response.json()["invalid_lines"][0]["order_id"], order.pk)
        self.assertEqual(
            StoreOrderLine.objects.get(order=order).qty, Decimal("1.5"),
        )

    def test_anonymous_and_store_user_are_denied(self):
        self.assertIn(self.request_recap().status_code, (401, 403))
        self.client.force_login(self.store_user)
        self.assertEqual(self.request_recap().status_code, 403)
        self.client.force_login(self.production_user)
        self.assertEqual(self.request_recap().status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.request_recap().status_code, 200)

    def test_query_validation_and_no_writes(self):
        self.client.force_login(self.production_user)
        self.assertEqual(self.request_recap(delivery_date="not-a-date").status_code, 400)
        self.assertEqual(self.request_recap(kitchen_code="T_BAN").status_code, 404)
        self.assertEqual(self.request_recap(schedule_code="NOPE").status_code, 404)
        self.assertEqual(self.client.post(self.url, {}, content_type="application/json").status_code, 405)
        self.assertEqual(StoreOrder.objects.count(), 0)
        self.assertEqual(ProductionAssignment.objects.count(), 2)

    def test_production_group_can_login_without_store_permissions(self):
        self.client.force_login(self.production_user)
        me = self.client.get(reverse("store-session-me"))
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.json()["user"]["can_access_production"])
        self.assertFalse(me.json()["user"]["can_access_store"])
        self.assertEqual(me.json()["stores"], [])
        order_url = reverse("store-order-form")
        self.assertEqual(self.client.get(order_url, {
            "store_code": "T_BAN", "kitchen_code": "JP",
            "schedule_code": "SUBUH", "delivery_date": "2026-11-08",
        }).status_code, 403)
