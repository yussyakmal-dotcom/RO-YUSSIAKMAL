from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import (
    DocumentCounter, Product, ProductionPlan, ProductionPlanLine,
    Schedule, StoreOrder, Warehouse,
)


class HealthTest(TestCase):
    def test_health(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class ConstraintsTest(TestCase):
    def setUp(self):
        self.kitchen = Warehouse.objects.create(
            odoo_id=100, code="ROTI", name="Dapur Roti", kind="KITCHEN"
        )
        self.store = Warehouse.objects.create(
            odoo_id=200, code="T_BAN", name="Toko Bandara", kind="STORE"
        )
        self.schedule = Schedule.objects.create(code="SUBUH", name="Subuh")
        self.product = Product.objects.create(odoo_id=11, sku="ROTI-A", name="Roti A")

    def test_unique_order_per_store_kitchen_date_schedule(self):
        data = dict(
            store=self.store,
            kitchen=self.kitchen,
            order_date=date(2026, 11, 1),
            delivery_date=date(2026, 11, 3),
            schedule=self.schedule,
        )
        StoreOrder.objects.create(**data)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StoreOrder.objects.create(**data)

    def test_mo_capacity_is_hard_limit(self):
        plan = ProductionPlan.objects.create(
            kitchen=self.kitchen,
            production_date=date(2026, 11, 2),
            delivery_date=date(2026, 11, 3),
            schedule=self.schedule,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductionPlanLine.objects.create(
                    plan=plan, product=self.product,
                    qty_requested=Decimal("210"), qty_planned=Decimal("210"),
                    qty_mo=Decimal("300"), batch_qty=Decimal("100"),
                    capacity_qty=Decimal("200"),
                )

    def test_daily_counter_key_unique(self):
        DocumentCounter.objects.create(
            warehouse=self.kitchen, issue_date=date(2026, 11, 5), last_value=10001
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DocumentCounter.objects.create(
                    warehouse=self.kitchen, issue_date=date(2026, 11, 5), last_value=10002
                )
