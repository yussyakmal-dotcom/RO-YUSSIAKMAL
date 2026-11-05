"""Store ordering contract: editable Draft, Qty >= 1 on Kirim, locked afterward."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    AuditLog, Product, ProductionAssignment, Schedule, StoreOrder,
    StoreOrderLine, UserWarehouseAccess, Warehouse,
)


class StoreOrderFlowTests(TestCase):
    def setUp(self):
        self.store = Warehouse.objects.create(
            odoo_id=301, code="T_BAN", name="Toko Bandara", kind="STORE"
        )
        self.other_store = Warehouse.objects.create(
            odoo_id=302, code="T_KD", name="Toko Kedaton", kind="STORE"
        )
        self.kitchen = Warehouse.objects.create(
            odoo_id=401, code="JP", name="Dapur Jajan Pasar", kind="KITCHEN"
        )
        self.other_kitchen = Warehouse.objects.create(
            odoo_id=402, code="PST", name="Dapur Pastry", kind="KITCHEN"
        )
        self.schedule = Schedule.objects.create(code="SUBUH", name="Subuh")
        self.other_schedule = Schedule.objects.create(code="PAGI", name="Pagi")
        self.products = [
            Product.objects.create(odoo_id=n, sku=str(n), name=f"SKU {n}")
            for n in (10005, 10006, 10007)
        ]
        for n, product in enumerate(self.products, start=1):
            ProductionAssignment.objects.create(
                product=product, kitchen=self.kitchen, sort_order=n
            )
        self.pastry_product = Product.objects.create(
            odoo_id=11000, sku="11000", name="Pastry"
        )
        ProductionAssignment.objects.create(
            product=self.pastry_product, kitchen=self.other_kitchen
        )
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="admin-toko", password="test")
        self.other_user = user_model.objects.create_user(username="other-user", password="test")
        group = Group.objects.create(name="STORE")
        self.user.groups.add(group)
        self.other_user.groups.add(group)
        UserWarehouseAccess.objects.create(user=self.user, warehouse=self.store)
        UserWarehouseAccess.objects.create(user=self.other_user, warehouse=self.other_store)
        self.admin_user = user_model.objects.create_superuser(
            username="supervisor", password="test", email="supervisor@example.test"
        )
        self.form_url = reverse("store-order-form")

    def context(self, **overrides):
        obj = {
            "store_code": "T_BAN",
            "kitchen_code": "JP",
            "delivery_date": "2026-11-07",
            "schedule_code": "SUBUH",
        }
        obj.update(overrides)
        return obj

    def save(self, items, **context_overrides):
        return self.client.post(
            self.form_url,
            self.context(items=items, **context_overrides),
            content_type="application/json",
        )

    def test_draft_can_reopen_edit_and_kirim_locks(self):
        self.client.force_login(self.user)
        empty = self.client.get(self.form_url, self.context())
        self.assertEqual(empty.status_code, 200)
        self.assertIsNone(empty.json()["id"])
        self.assertEqual(empty.json()["status"], "DRAFT")
        self.assertEqual(len(empty.json()["items"]), 3)
        self.assertTrue(all(row["qty"] == "0" for row in empty.json()["items"]))

        saved = self.save([
            {"product_id": self.products[0].id, "qty": "3"},
            {"product_id": self.products[1].id, "qty": "1"},
            {"product_id": self.products[2].id, "qty": "0"},
        ])
        self.assertEqual(saved.status_code, 200, saved.content)
        order_id = saved.json()["id"]
        self.assertEqual(saved.json()["status"], "DRAFT")
        self.assertTrue(saved.json()["editable"])
        self.assertEqual(StoreOrderLine.objects.filter(order_id=order_id).count(), 2)

        reopened = self.client.get(self.form_url, self.context()).json()
        by_sku = {row["sku"]: row["qty"] for row in reopened["items"]}
        self.assertEqual(by_sku["10005"], "3.0000")
        self.assertEqual(by_sku["10006"], "1.0000")
        self.assertEqual(by_sku["10007"], "0")

        edited = self.save([
            {"product_id": self.products[0].id, "qty": "5"},
            {"product_id": self.products[1].id, "qty": "0"},
            {"product_id": self.products[2].id, "qty": "2"},
        ])
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(StoreOrderLine.objects.filter(order_id=order_id).count(), 2)

        send_url = reverse("store-order-send", args=[order_id])
        sent = self.client.post(send_url, {}, content_type="application/json")
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.json()["status"], "KIRIM")
        self.assertEqual(sent.json()["items_sent"], 2)
        order = StoreOrder.objects.get(pk=order_id)
        self.assertIsNotNone(order.submitted_at)
        self.assertEqual(order.status, "KIRIM")
        self.assertEqual(
            {line.product.sku: line.qty for line in order.lines.select_related("product")},
            {"10005": Decimal("5"), "10007": Decimal("2")},
        )
        self.assertEqual(self.save([]).status_code, 409)
        self.assertEqual(self.client.post(send_url).status_code, 409)
        self.assertFalse(self.client.get(self.form_url, self.context()).json()["editable"])
        self.assertTrue(AuditLog.objects.filter(action="SAVE_DRAFT").exists())
        self.assertEqual(AuditLog.objects.filter(action="KIRIM").count(), 1)

    def test_only_qty_at_least_one_is_sent(self):
        self.client.force_login(self.user)
        saved = self.save([
            {"product_id": self.products[0].id, "qty": "0.5000"},
            {"product_id": self.products[1].id, "qty": "1.0000"},
            {"product_id": self.products[2].id, "qty": "0"},
        ])
        self.assertEqual(saved.status_code, 200)
        order_id = saved.json()["id"]
        result = self.client.post(
            reverse("store-order-send", args=[order_id]), {}, content_type="application/json"
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["items_sent"], 1)
        self.assertEqual(result.json()["excluded_below_one"], 1)
        self.assertEqual(
            StoreOrderLine.objects.get(order_id=order_id).product_id,
            self.products[1].id,
        )

    def test_all_zero_becomes_no_order(self):
        self.client.force_login(self.user)
        saved = self.save([
            {"product_id": self.products[0].id, "qty": "0"},
            {"product_id": self.products[1].id, "qty": "0"},
        ])
        result = self.client.post(
            reverse("store-order-send", args=[saved.json()["id"]]),
            {}, content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "NO_ORDER")
        self.assertEqual(result.json()["items_sent"], 0)
        self.assertFalse(StoreOrderLine.objects.filter(order_id=saved.json()["id"]).exists())
        self.assertEqual(self.save([]).status_code, 409)

    def test_access_scope_store_user_and_administrator(self):
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(self.form_url, self.context()).status_code, 403)
        self.assertEqual(
            self.save([{"product_id": self.products[0].id, "qty": "2"}]).status_code,
            403,
        )
        self.client.force_login(self.admin_user)
        saved = self.save([{"product_id": self.products[0].id, "qty": "1"}])
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(
            AuditLog.objects.filter(action="SAVE_DRAFT").first().actor_id,
            self.admin_user.id,
        )
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.post(
                reverse("store-order-send", args=[saved.json()["id"]])
            ).status_code, 403,
        )

    def test_inactive_items_hidden_in_new_template_but_existing_draft_visible(self):
        self.client.force_login(self.user)
        saved = self.save([{"product_id": self.products[0].id, "qty": "6"}])
        assignment = ProductionAssignment.objects.get(product=self.products[0])
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        opened = self.client.get(self.form_url, self.context()).json()
        historic = [row for row in opened["items"] if row["sku"] == "10005"]
        self.assertEqual(historic[0]["qty"], "6.0000")
        self.assertFalse(historic[0]["active_in_template"])
        # Existing Draft quantity can be edited or cleared despite template changes.
        self.assertEqual(
            self.save([{"product_id": self.products[0].id, "qty": "0"}]).status_code,
            200,
        )
        reopened = self.client.get(self.form_url, self.context()).json()
        self.assertNotIn("10005", {x["sku"] for x in reopened["items"]})

    def test_invalid_product_duplicate_negative_and_overprecision_rejected(self):
        self.client.force_login(self.user)
        good = {"product_id": self.products[0].id, "qty": "2"}
        for items in (
            [good, good],
            [{"product_id": self.pastry_product.id, "qty": "2"}],
            [{"product_id": self.products[0].id, "qty": "-1"}],
            [{"product_id": self.products[0].id, "qty": "1.12345"}],
        ):
            response = self.save(items)
            self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(StoreOrder.objects.exists())

    def test_different_slots_and_stores_have_independent_drafts(self):
        self.client.force_login(self.admin_user)
        a = self.save([{"product_id": self.products[0].id, "qty": "4"}])
        b = self.save(
            [{"product_id": self.products[0].id, "qty": "2"}],
            schedule_code="PAGI",
        )
        c = self.save(
            [{"product_id": self.products[0].id, "qty": "3"}],
            store_code="T_KD",
        )
        self.assertEqual([a.status_code, b.status_code, c.status_code], [200, 200, 200])
        self.assertEqual(StoreOrder.objects.count(), 3)
        self.assertEqual(StoreOrder.objects.filter(status="DRAFT").count(), 3)
