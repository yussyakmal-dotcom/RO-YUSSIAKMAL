"""Production consolidation must preserve store commitments and capacity."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    AuditLog, Product, ProductCapacity, ProductionPlan,
    ProductionPlanLine, ProductionPlanSource, Schedule, StoreOrder,
    StoreOrderLine, Warehouse,
)


class ConsolidationTests(TestCase):
    def setUp(self):
        self.kitchen = Warehouse.objects.create(
            odoo_id=100, kind="KITCHEN", code="JP", name="Jajan Pasar",
        )
        self.store_a = Warehouse.objects.create(
            odoo_id=101, kind="STORE", code="T_BAN", name="Bandara",
        )
        self.store_b = Warehouse.objects.create(
            odoo_id=102, kind="STORE", code="T_KD", name="Kedaton",
        )
        self.subuh = Schedule.objects.create(
            code="SUBUH", name="Subuh", sort_order=1,
        )
        self.pagi = Schedule.objects.create(
            code="PAGI", name="Pagi", sort_order=2,
        )
        self.produk = Product.objects.create(
            odoo_id=301, sku="10005", name="Arem-arem Sultan Mini", uom="Pcs",
        )
        self.produk2 = Product.objects.create(
            odoo_id=302, sku="10006", name="Lemper", uom="Pcs",
        )
        self.cap = ProductCapacity.objects.create(
            product=self.produk, schedule=self.pagi,
            max_qty=Decimal("400.0000"),
        )
        self.production = get_user_model().objects.create_user(
            username="prod", password="prod-test",
        )
        self.store_user = get_user_model().objects.create_user(
            username="store", password="store-test",
        )
        prod = Group.objects.create(name="PRODUCTION")
        store = Group.objects.create(name="STORE")
        self.production.groups.add(prod)
        self.store_user.groups.add(store)
        self.a = self.make_order(self.store_a, 250)
        self.b = self.make_order(self.store_b, 250)
        self.preview_url = reverse("production-consolidation-preview")
        self.save_url = reverse("production-consolidation-save")
        self.payload = {
            "kitchen_code": "JP",
            "delivery_date": "2026-11-07",
            "delivery_schedule_code": "SUBUH",
            "production_date": "2026-11-06",
            "production_schedule_code": "PAGI",
            "order_ids": [self.a.pk, self.b.pk],
            "items": [{"product_id": self.produk.pk, "qty_planned": "400"}],
        }

    def make_order(
        self, store, qty, *,
        delivery_date="2026-11-07", delivery_schedule=None,
        status="KIRIM", product=None,
    ):
        order = StoreOrder.objects.create(
            store=store, kitchen=self.kitchen,
            schedule=delivery_schedule or self.subuh,
            delivery_date=delivery_date, order_date="2026-11-05",
            status=status,
        )
        if qty is not None:
            StoreOrderLine.objects.create(
                order=order, product=product or self.produk, qty=qty,
            )
        return order

    def save(self, payload=None):
        return self.client.post(
            self.save_url,
            json.dumps(self.payload if payload is None else payload),
            content_type="application/json",
        )

    def preview(self, **extra):
        return self.client.get(self.preview_url, {
            "kitchen_code": "JP", "delivery_date": "2026-11-07",
            "delivery_schedule_code": "SUBUH", **extra,
        })

    def test_preview_is_readonly_and_shows_master_capacity_without_auto_dates(self):
        self.client.force_login(self.production)
        no_date = self.preview().json()
        self.assertIsNone(no_date["production_date"])
        self.assertIsNone(no_date["production_schedule"])
        self.assertEqual(no_date["order_ids"], [self.a.pk, self.b.pk])
        self.assertEqual(no_date["items"][0]["qty_requested"], "500")
        self.assertIsNone(no_date["items"][0]["capacity_qty"])
        self.assertFalse(ProductionPlan.objects.exists())
        scoped = self.preview(
            production_date="2026-11-06",
            production_schedule_code="PAGI",
        ).json()
        self.assertEqual(scoped["delivery_schedule"]["code"], "SUBUH")
        self.assertEqual(scoped["production_schedule"]["code"], "PAGI")
        self.assertEqual(scoped["items"][0]["capacity_qty"], "400")
        self.assertEqual(scoped["items"][0]["capacity_used"], "0")
        self.assertEqual(scoped["items"][0]["capacity_available"], "400")
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_save_400_of_500_with_shortfall_and_original_delivery_unchanged(self):
        self.client.force_login(self.production)
        response = self.save()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["shortfall_sku_count"], 1)
        plan = ProductionPlan.objects.get()
        self.assertEqual(plan.production_date.isoformat(), "2026-11-06")
        self.assertEqual(plan.production_schedule, self.pagi)
        self.assertEqual(plan.delivery_date.isoformat(), "2026-11-07")
        self.assertEqual(plan.delivery_schedule, self.subuh)
        self.assertEqual(plan.status, "DRAFT")
        line = ProductionPlanLine.objects.get(plan=plan)
        self.assertEqual(line.qty_requested, 500)
        self.assertEqual(line.qty_planned, 400)
        self.assertEqual(line.capacity_qty, 400)
        self.assertEqual(line.capacity_used_before, 0)
        self.assertEqual(line.qty_shortfall, 100)
        self.assertIsNone(line.qty_mo)
        self.assertIsNone(line.batch_qty)
        self.assertEqual(ProductionPlanSource.objects.filter(plan=plan).count(), 2)
        self.assertEqual(
            ProductionPlanSource.objects.get(order=self.a).lines_snapshot[0],
            {
                "product_id": self.produk.pk, "sku": "10005",
                "name": "Arem-arem Sultan Mini", "uom": "Pcs", "qty": "250",
            },
        )
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertEqual(self.a.status, "PROSES_PRODUKSI")
        self.assertEqual(self.b.status, "PROSES_PRODUKSI")
        self.assertEqual(self.a.schedule, self.subuh)
        self.assertEqual(self.b.schedule, self.subuh)
        self.assertEqual(self.a.lines.get().qty, 250)
        self.assertEqual(self.b.lines.get().qty, 250)
        self.assertEqual(AuditLog.objects.filter(action="CONSOLIDATE").count(), 1)
        detail = self.client.get(reverse(
            "production-consolidation-detail", args=[plan.pk],
        ))
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(detail.json()["items"][0]["qty_shortfall"], "100")
        self.assertEqual(detail.json()["items"][0]["qty_planned"], "400")
        self.assertEqual(detail.json()["sources"][0]["store_code"], "T_BAN")
        self.assertEqual(detail.json()["production_schedule"]["code"], "PAGI")
        inbox = self.client.get(reverse("production-inbox")).json()
        self.assertEqual(
            [o["plan_id"] for o in inbox["items"]],
            [plan.pk, plan.pk],
        )
        self.assertEqual({o["status"] for o in inbox["items"]}, {
            "PROSES_PRODUKSI",
        })

    def test_double_submit_different_production_date_cannot_duplicate(self):
        self.client.force_login(self.production)
        self.assertEqual(self.save().status_code, 201)
        duplicate = {
            **self.payload, "production_date": "2026-11-07",
        }
        response = self.save(duplicate)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(ProductionPlan.objects.count(), 1)
        self.assertEqual(ProductionPlanSource.objects.count(), 2)

    def test_missing_capacity_blocks_save_and_keeps_every_order_kirim(self):
        self.cap.delete()
        self.client.force_login(self.production)
        response = self.save()
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn("Kapasitas", response.json()["detail"])
        self.assertFalse(ProductionPlan.objects.exists())
        self.assertEqual(
            StoreOrder.objects.filter(status="KIRIM").count(), 2,
        )
        self.assertFalse(AuditLog.objects.exists())

    def test_more_than_capacity_is_rejected_no_hidden_split(self):
        self.client.force_login(self.production)
        payload = {
            **self.payload,
            "items": [{"product_id": self.produk.pk, "qty_planned": "401"}],
        }
        response = self.save(payload)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(ProductionPlan.objects.exists())
        self.assertEqual(
            StoreOrder.objects.filter(status="KIRIM").count(), 2,
        )

    def test_zero_fraction_and_over_requested_are_blocked_without_rounding(self):
        self.client.force_login(self.production)
        for value, code in [("0", 409), ("500", 409), ("1.5", 400)]:
            payload = {
                **self.payload,
                "items": [{
                    "product_id": self.produk.pk, "qty_planned": value,
                }],
            }
            response = self.save(payload)
            self.assertEqual(response.status_code, code, response.content)
            self.assertFalse(ProductionPlan.objects.exists())
        self.a.lines.update(qty=Decimal("1.5000"))
        response = self.save()
        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(ProductionPlan.objects.exists())

    def test_stale_preview_new_order_blocks_save(self):
        self.client.force_login(self.production)
        self.make_order(
            self.store_b, 50, delivery_date="2026-11-08",
        )
        self.make_order(
            Warehouse.objects.create(
                odoo_id=103, kind="STORE", code="T_MET", name="Metro",
            ), 25,
        )
        response = self.save()
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn("berubah", response.json()["detail"])
        self.assertFalse(ProductionPlan.objects.exists())

    def test_different_delivery_schedule_may_use_same_production_day(self):
        self.cap.max_qty = 600
        self.cap.save(update_fields=["max_qty"])
        self.client.force_login(self.production)
        self.assertEqual(self.save().status_code, 201)
        second = self.make_order(
            self.store_a, 200, delivery_schedule=self.pagi,
        )
        other = {**self.payload,
            "delivery_schedule_code": "PAGI",
            "order_ids": [second.pk],
            "items": [{"product_id": self.produk.pk, "qty_planned": "200"}],
        }
        result = self.save(other)
        self.assertEqual(result.status_code, 201, result.content)
        plans = list(ProductionPlan.objects.order_by("pk"))
        self.assertEqual(len(plans), 2)
        self.assertEqual(
            {p.delivery_schedule.code for p in plans},
            {"SUBUH", "PAGI"},
        )
        self.assertEqual({p.production_date for p in plans}, {
            plans[0].production_date,
        })
        self.assertEqual(
            plans[1].lines.get().capacity_used_before, 400,
        )

    def test_all_or_nothing_with_second_sku_missing_capacity(self):
        StoreOrderLine.objects.create(
            order=self.a, product=self.produk2, qty=50,
        )
        self.client.force_login(self.production)
        payload = {**self.payload, "items": [
            {"product_id": self.produk.pk, "qty_planned": "400"},
            {"product_id": self.produk2.pk, "qty_planned": "50"},
        ]}
        response = self.save(payload)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertFalse(ProductionPlan.objects.exists())
        self.assertFalse(ProductionPlanSource.objects.exists())
        self.assertEqual(
            StoreOrder.objects.filter(status="KIRIM").count(), 2,
        )

    def test_store_and_anonymous_cannot_preview_save_or_view_plan(self):
        self.assertIn(self.preview().status_code, (401, 403))
        self.assertIn(self.save().status_code, (401, 403))
        self.client.force_login(self.store_user)
        self.assertEqual(self.preview().status_code, 403)
        self.assertEqual(self.save().status_code, 403)
        self.assertEqual(
            self.client.get(reverse(
                "production-consolidation-detail", args=[999],
            )).status_code, 403,
        )
        self.assertFalse(ProductionPlan.objects.exists())

    def test_historical_plan_with_no_production_schedule_not_reinterpreted(self):
        historical = ProductionPlan.objects.create(
            kitchen=self.kitchen, delivery_date="2026-11-06",
            delivery_schedule=self.subuh,
            production_date="2026-11-06", production_schedule=None,
        )
        historical.refresh_from_db()
        self.assertIsNone(historical.production_schedule)
        self.client.force_login(self.production)
        self.assertEqual(self.save().status_code, 201)  # Different date/scope
        original = self.make_order(
            self.store_a, 1, delivery_date="2026-11-06",
        )
        response = self.preview_url
        self.assertEqual(self.client.get(response, {
            "kitchen_code": "JP", "delivery_date": "2026-11-06",
            "delivery_schedule_code": "SUBUH",
        }).status_code, 409)
        original.refresh_from_db()
        self.assertEqual(original.status, "KIRIM")
