"""Production queue groups by delivery commitment, not per-store rows."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    AuditLog, Product, ProductionConsolidationDraft, ProductionPlan,
    Schedule, StoreOrder, StoreOrderLine, Warehouse,
)


class DeliveryQueueTests(TestCase):
    def setUp(self):
        self.kitchen = Warehouse.objects.create(
            odoo_id=9001, code="JP", name="Dapur JP", kind="KITCHEN",
        )
        self.kitchen_b = Warehouse.objects.create(
            odoo_id=9002, code="PST", name="Dapur Pastry", kind="KITCHEN",
        )
        self.store1 = Warehouse.objects.create(
            odoo_id=9003, code="T_BAN", name="Toko Bandara", kind="STORE",
        )
        self.store2 = Warehouse.objects.create(
            odoo_id=9004, code="T_KD", name="Toko Kedaton", kind="STORE",
        )
        self.store3 = Warehouse.objects.create(
            odoo_id=9005, code="T_MET", name="Toko Metro", kind="STORE",
        )
        self.subuh = Schedule.objects.create(code="SUBUH", name="Subuh", sort_order=1)
        self.pagi = Schedule.objects.create(code="PAGI", name="Pagi", sort_order=2)
        self.pcs = Product.objects.create(
            odoo_id=9010, sku="10005", name="Arem-arem", uom="Pcs",
        )
        self.kg = Product.objects.create(
            odoo_id=9011, sku="10006", name="Tepung", uom="Kg",
        )
        self.production = get_user_model().objects.create_user(
            username="prod", password="pwd",
        )
        self.store = get_user_model().objects.create_user(
            username="toko", password="pwd",
        )
        g = Group.objects.create(name="PRODUCTION")
        self.production.groups.add(g)
        self.store.groups.add(Group.objects.create(name="STORE"))
        self.url = reverse("production-delivery-queue")

    def order(
        self, store, *, kitchen=None, schedule=None, day="2026-11-07",
        status="KIRIM", quantities=None,
    ):
        o = StoreOrder.objects.create(
            store=store, kitchen=kitchen or self.kitchen,
            schedule=schedule or self.subuh,
            delivery_date=day, order_date="2026-11-05",
            status=status,
        )
        for product, qty in quantities or []:
            StoreOrderLine.objects.create(order=o, product=product, qty=qty)
        return o

    def get(self, **params):
        return self.client.get(self.url, params)

    def test_two_stores_same_date_kitchen_schedule_are_one_row_and_sum_by_uom(self):
        first = self.order(self.store1, quantities=[(self.pcs, 250), (self.kg, 1)])
        second = self.order(self.store2, quantities=[(self.pcs, 250), (self.kg, 2)])
        self.order(self.store3, status="DRAFT", quantities=[(self.pcs, 9000)])
        self.client.force_login(self.production)
        data = self.get().json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["counts"], {
            "all": 1, "kirim": 1, "proses_produksi": 0,
        })
        row = data["items"][0]
        self.assertEqual(row["delivery_date"], "2026-11-07")
        self.assertEqual(row["kitchen_code"], "JP")
        self.assertEqual(row["schedule_code"], "SUBUH")
        self.assertEqual(row["store_count"], 2)
        self.assertEqual(row["order_count"], 2)
        self.assertEqual(row["sku_count"], 2)
        self.assertEqual(row["status"], "KIRIM")
        self.assertIsNone(row["qty_total"])
        self.assertIsNone(row["qty_uom"])
        self.assertEqual(row["qty_by_uom"], [
            {"uom": "Kg", "qty": "3"}, {"uom": "Pcs", "qty": "500"},
        ])
        self.assertEqual(
            {x["order_id"] for x in row["stores"]}, {first.pk, second.pk},
        )
        self.assertEqual(StoreOrder.objects.filter(status="KIRIM").count(), 2)
        self.assertFalse(AuditLog.objects.exists())

    def test_dates_sort_first_and_different_kitchens_schedules_separate(self):
        self.order(self.store1, quantities=[(self.pcs, 2)], day="2026-11-08")
        self.order(self.store2, quantities=[(self.pcs, 3)], day="2026-11-07")
        self.order(self.store1, quantities=[(self.pcs, 4)],
                   day="2026-11-07", schedule=self.pagi)
        self.order(self.store1, quantities=[(self.pcs, 5)],
                   day="2026-11-07", kitchen=self.kitchen_b)
        self.client.force_login(self.production)
        data = self.get().json()
        self.assertEqual(data["total"], 4)
        self.assertEqual(
            [(x["delivery_date"], x["kitchen_code"], x["schedule_code"])
             for x in data["items"]],
            [
                ("2026-11-07", "JP", "SUBUH"),
                ("2026-11-07", "JP", "PAGI"),
                ("2026-11-07", "PST", "SUBUH"),
                ("2026-11-08", "JP", "SUBUH"),
            ],
        )

    def test_mixed_status_late_store_order_keeps_one_scope_and_no_silent_replan(self):
        first = self.order(
            self.store1, status="PROSES_PRODUKSI",
            quantities=[(self.pcs, 400)],
        )
        next_order = self.order(
            self.store2, quantities=[(self.pcs, 100)],
        )
        plan = ProductionPlan.objects.create(
            kitchen=self.kitchen,
            delivery_date="2026-11-07",
            delivery_schedule=self.subuh,
            production_date="2026-11-06",
            production_schedule=self.pagi,
        )
        self.client.force_login(self.production)
        data = self.get().json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["counts"], {
            "all": 1, "kirim": 1, "proses_produksi": 1,
        })
        row = data["items"][0]
        self.assertEqual(row["status"], "CAMPURAN")
        self.assertEqual(row["kirim_count"], 1)
        self.assertEqual(row["proses_produksi_count"], 1)
        self.assertEqual(row["plan_id"], plan.pk)
        self.assertEqual(row["qty_total"], "500")
        self.assertEqual(
            {x["order_id"] for x in row["stores"]}, {first.pk, next_order.pk},
        )
        self.assertEqual(len(self.get(status="KIRIM").json()["items"]), 1)
        self.assertEqual(len(self.get(status="PROSES_PRODUKSI").json()["items"]), 1)
        next_order.refresh_from_db()
        self.assertEqual(next_order.status, "KIRIM")

    def test_draft_flag_by_scope_and_final_plan_history(self):
        o = self.order(self.store1, quantities=[(self.pcs, 15)])
        ProductionConsolidationDraft.objects.create(
            kitchen=self.kitchen, delivery_date=o.delivery_date,
            delivery_schedule=self.subuh, source_order_ids=[o.pk],
            planned_items=[{"product_id": self.pcs.pk, "qty_planned": "5"}],
        )
        self.client.force_login(self.production)
        row = self.get().json()["items"][0]
        self.assertTrue(row["has_consolidation_draft"])
        self.assertIsNone(row["plan_id"])
        self.assertEqual(row["status"], "KIRIM")

    def test_historical_fraction_warns_without_rounding(self):
        self.order(self.store1, quantities=[(self.pcs, Decimal("1.5000"))])
        self.client.force_login(self.production)
        row = self.get().json()["items"][0]
        self.assertTrue(row["qty_invalid"])
        self.assertIsNone(row["qty_total"])
        self.assertEqual(row["qty_by_uom"], [])

    def test_50_groups_per_page_does_not_split_one_date_scope(self):
        for offset in range(51):
            day = f"2027-01-{offset+1:02d}" if offset < 28 else f"2027-02-{offset-27:02d}"
            # Use separate day/schedule to avoid impossible dates beyond month-end.
            if offset >= 28:
                # February dates 1..23 are valid in 2027.
                pass
            self.order(self.store1, day=day, quantities=[(self.pcs, 1)])
            self.order(self.store2, day=day, quantities=[(self.pcs, 2)])
        self.client.force_login(self.production)
        first = self.get(page=1).json()
        second = self.get(page=2).json()
        self.assertEqual(first["total"], 51)
        self.assertEqual(len(first["items"]), 50)
        self.assertEqual(len(second["items"]), 1)
        self.assertTrue(first["has_more"])
        self.assertFalse(second["has_more"])
        self.assertTrue(all(x["order_count"] == 2 for x in first["items"] + second["items"]))
        self.assertNotEqual(first["items"][-1]["delivery_date"], second["items"][0]["delivery_date"])

    def test_protection_and_invalid_filters(self):
        self.assertIn(self.get().status_code, (401, 403))
        self.client.force_login(self.store)
        self.assertEqual(self.get().status_code, 403)
        self.client.force_login(self.production)
        self.assertEqual(self.get(status="DRAFT").status_code, 400)
        self.assertEqual(self.get(page=0).status_code, 400)
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)
