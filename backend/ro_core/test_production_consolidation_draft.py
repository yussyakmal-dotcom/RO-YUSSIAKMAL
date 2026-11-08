"""Incomplete production planning is resumable without KIRIM transitions."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    AuditLog, Product, ProductCapacity, ProductionConsolidationDraft,
    ProductionPlan, ProductionPlanLine, ProductionPlanSource, Schedule,
    StoreOrder, StoreOrderLine, Warehouse,
)


class ProductionConsolidationDraftTests(TestCase):
    def setUp(self):
        self.kitchen = Warehouse.objects.create(
            odoo_id=501, code="JP", name="Jajan Pasar", kind="KITCHEN",
        )
        self.store1 = Warehouse.objects.create(
            odoo_id=502, code="T_BAN", name="Bandara", kind="STORE",
        )
        self.store2 = Warehouse.objects.create(
            odoo_id=503, code="T_KD", name="Kedaton", kind="STORE",
        )
        self.subuh = Schedule.objects.create(
            code="SUBUH", name="Subuh", sort_order=1,
        )
        self.pagi = Schedule.objects.create(
            code="PAGI", name="Pagi", sort_order=2,
        )
        self.sku = Product.objects.create(
            odoo_id=504, sku="10005", name="Arem-arem Mini", uom="Pcs",
        )
        self.sku2 = Product.objects.create(
            odoo_id=505, sku="10006", name="Lemper", uom="Pcs",
        )
        self.a = self.create_order(self.store1, 250)
        self.b = self.create_order(self.store2, 250)
        self.cap = ProductCapacity.objects.create(
            product=self.sku, schedule=self.pagi, max_qty=400,
        )
        self.user = get_user_model().objects.create_user(
            username="admin_produksi", password="local-test",
        )
        self.user2 = get_user_model().objects.create_user(
            username="admin_produksi2", password="local-test",
        )
        self.store_user = get_user_model().objects.create_user(
            username="admin_toko", password="local-test",
        )
        production = Group.objects.create(name="PRODUCTION")
        store = Group.objects.create(name="STORE")
        self.user.groups.add(production)
        self.user2.groups.add(production)
        self.store_user.groups.add(store)
        self.url = reverse("production-consolidation-draft")
        self.final_url = reverse("production-consolidation-save")
        self.preview_url = reverse("production-consolidation-preview")
        self.scope = {
            "kitchen_code": "JP",
            "delivery_date": "2026-11-07",
            "delivery_schedule_code": "SUBUH",
        }
        self.draft_payload = {
            **self.scope,
            "production_date": None,
            "production_schedule_code": "",
            "order_ids": [self.a.pk, self.b.pk],
            "items": [],
            "version": 0,
        }

    def create_order(self, store, qty):
        order = StoreOrder.objects.create(
            store=store, kitchen=self.kitchen,
            schedule=self.subuh, order_date="2026-11-05",
            delivery_date="2026-11-07", status="KIRIM",
        )
        StoreOrderLine.objects.create(
            order=order, product=self.sku, qty=qty,
        )
        return order

    def write_draft(self, **changes):
        return self.client.post(
            self.url,
            data=json.dumps({**self.draft_payload, **changes}),
            content_type="application/json",
        )

    def final(self, version=0, qty="400"):
        return self.client.post(
            self.final_url,
            data=json.dumps({
                **self.scope,
                "production_date": "2026-11-06",
                "production_schedule_code": "PAGI",
                "order_ids": [self.a.pk, self.b.pk],
                "items": [
                    {"product_id": self.sku.pk, "qty_planned": qty},
                ],
                "draft_version": version,
            }),
            content_type="application/json",
        )

    def test_empty_and_partial_drafts_are_saved_without_capacity_or_status_change(self):
        self.client.force_login(self.user)
        self.assertIsNone(self.client.get(self.url, self.scope).json()["draft"])
        response = self.write_draft(
            items=[{"product_id": self.sku.pk, "qty_planned": "275"}],
        )
        self.assertEqual(response.status_code, 201, response.content)
        draft = response.json()["draft"]
        self.assertEqual(draft["version"], 1)
        self.assertIsNone(draft["production_date"])
        self.assertIsNone(draft["production_schedule_code"])
        self.assertEqual(
            draft["items"], [{"product_id": self.sku.pk, "qty_planned": "275"}],
        )
        self.assertEqual(
            self.client.get(self.url, self.scope).json()["draft"]["items"],
            draft["items"],
        )
        self.assertEqual(ProductionConsolidationDraft.objects.count(), 1)
        self.assertFalse(ProductionPlan.objects.exists())
        self.assertFalse(ProductionPlanLine.objects.exists())
        self.assertFalse(ProductionPlanSource.objects.exists())
        self.assertEqual(StoreOrder.objects.filter(status="KIRIM").count(), 2)
        self.assertEqual(AuditLog.objects.filter(action="SAVE_DRAFT").count(), 1)
        # The draft has NOT reserved 275 Pcs against the 400 Pcs capacity.
        preview = self.client.get(self.preview_url, {
            **self.scope, "production_date": "2026-11-06",
            "production_schedule_code": "PAGI",
        }).json()
        self.assertEqual(preview["items"][0]["capacity_available"], "400")
        inbox = self.client.get(reverse("production-inbox")).json()
        self.assertEqual(
            [item["has_consolidation_draft"] for item in inbox["items"]],
            [True, True],
        )
        self.assertTrue(all(item["status"] == "KIRIM" for item in inbox["items"]))

    def test_save_empty_draft_and_resume_with_manual_date_schedule(self):
        self.client.force_login(self.user)
        saved = self.write_draft()
        self.assertEqual(saved.status_code, 201, saved.content)
        self.assertEqual(saved.json()["draft"]["items"], [])
        updated = self.write_draft(
            version=1,
            production_date="2026-11-06",
            production_schedule_code="PAGI",
            items=[{"product_id": self.sku.pk, "qty_planned": "400"}],
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        record = self.client.get(self.url, self.scope).json()["draft"]
        self.assertEqual(record["version"], 2)
        self.assertEqual(record["production_date"], "2026-11-06")
        self.assertEqual(record["production_schedule_code"], "PAGI")
        self.assertEqual(record["items"][0]["qty_planned"], "400")
        self.assertEqual(record["updated_by"], "admin_produksi")
        self.assertEqual(ProductionConsolidationDraft.objects.count(), 1)
        self.assertEqual(StoreOrder.objects.filter(status="KIRIM").count(), 2)

    def test_second_operator_cannot_silently_overwrite_draft(self):
        self.client.force_login(self.user)
        self.assertEqual(self.write_draft(
            items=[{"product_id": self.sku.pk, "qty_planned": "275"}],
        ).status_code, 201)
        self.client.force_login(self.user2)
        conflict = self.write_draft(
            version=0,
            items=[{"product_id": self.sku.pk, "qty_planned": "200"}],
        )
        self.assertEqual(conflict.status_code, 409, conflict.content)
        self.assertIn("operator lain", conflict.json()["detail"])
        persisted = self.client.get(self.url, self.scope).json()["draft"]
        self.assertEqual(persisted["items"][0]["qty_planned"], "275")
        self.assertEqual(persisted["version"], 1)

    def test_finalize_saved_draft_commits_plan_then_clears_draft_atomically(self):
        self.client.force_login(self.user)
        self.assertEqual(self.write_draft(
            production_date="2026-11-06",
            production_schedule_code="PAGI",
            items=[{"product_id": self.sku.pk, "qty_planned": "400"}],
        ).status_code, 201)
        final = self.final(version=1)
        self.assertEqual(final.status_code, 201, final.content)
        self.assertFalse(ProductionConsolidationDraft.objects.exists())
        self.assertEqual(ProductionPlan.objects.count(), 1)
        line = ProductionPlanLine.objects.get()
        self.assertEqual(line.qty_requested, Decimal("500"))
        self.assertEqual(line.qty_planned, Decimal("400"))
        self.assertEqual(line.qty_shortfall, Decimal("100"))
        self.assertEqual(
            StoreOrder.objects.filter(status="PROSES_PRODUKSI").count(), 2,
        )
        self.a.refresh_from_db()
        self.assertEqual(self.a.schedule, self.subuh)
        self.assertEqual(self.a.lines.get().qty, Decimal("250"))
        self.assertEqual(
            self.client.get(self.url, self.scope).status_code, 409,
        )
        self.assertEqual(self.write_draft(version=0).status_code, 409)

    def test_failed_finalization_keeps_draft_and_orders_untouched(self):
        self.client.force_login(self.user)
        self.assertEqual(self.write_draft(
            production_date="2026-11-06",
            production_schedule_code="PAGI",
            items=[{"product_id": self.sku.pk, "qty_planned": "400"}],
        ).status_code, 201)
        self.cap.max_qty = 300
        self.cap.save(update_fields=["max_qty"])
        refused = self.final(version=1)
        self.assertEqual(refused.status_code, 409, refused.content)
        self.assertEqual(
            ProductionConsolidationDraft.objects.get().planned_items[0]["qty_planned"],
            "400",
        )
        self.assertFalse(ProductionPlan.objects.exists())
        self.assertEqual(StoreOrder.objects.filter(status="KIRIM").count(), 2)

    def test_finalization_cannot_overwrite_a_newer_shared_draft(self):
        self.client.force_login(self.user)
        self.assertEqual(self.write_draft().status_code, 201)
        self.assertEqual(self.final(version=0).status_code, 409)
        self.assertFalse(ProductionPlan.objects.exists())
        self.assertEqual(ProductionConsolidationDraft.objects.get().version, 1)

    def test_reject_duplicate_products_invalid_quantities_or_stale_order_sources(self):
        self.client.force_login(self.user)
        for bad in ("1.0000", "1,000", "-2", "NaN"):
            response = self.write_draft(
                items=[{"product_id": self.sku.pk, "qty_planned": bad}],
            )
            self.assertEqual(response.status_code, 400, (bad, response.content))
        response = self.write_draft(items=[
            {"product_id": self.sku.pk, "qty_planned": "250"},
            {"product_id": self.sku.pk, "qty_planned": "300"},
        ])
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.write_draft(order_ids=[self.a.pk]).status_code, 409)
        self.assertFalse(ProductionConsolidationDraft.objects.exists())

    def test_store_user_and_anonymous_cannot_read_or_save_drafts(self):
        self.assertIn(self.client.get(self.url, self.scope).status_code, (401, 403))
        self.assertIn(self.write_draft().status_code, (401, 403))
        self.client.force_login(self.store_user)
        self.assertEqual(self.client.get(self.url, self.scope).status_code, 403)
        self.assertEqual(self.write_draft().status_code, 403)
        self.assertFalse(ProductionConsolidationDraft.objects.exists())
