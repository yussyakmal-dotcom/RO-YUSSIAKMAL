"""Regression tests for the 07:00 WIB H-2 cutoff."""
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from django.test import TestCase
from .auto_submit import BeforeCutoffError, auto_submit_drafts
from .models import AuditLog, Product, Schedule, StoreOrder, StoreOrderLine, Warehouse

WIB = ZoneInfo("Asia/Jakarta")


class AutoSubmitTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 5, 7, 0, tzinfo=WIB)
        self.delivery = self.now.date() + timedelta(days=2)
        self.store = Warehouse.objects.create(odoo_id=1001, code="T_BAN", name="Bandara", kind="STORE")
        self.kitchen = Warehouse.objects.create(odoo_id=1002, code="JP", name="Jajan Pasar", kind="KITCHEN")
        self.subuh = Schedule.objects.create(code="SUBUH", name="Subuh")
        self.pagi = Schedule.objects.create(code="PAGI", name="Pagi")
        self.product = Product.objects.create(odoo_id=1003, sku="JP-1", name="Produk")

    def make_order(self, *, qty=None, schedule=None, delivery=None, status="DRAFT"):
        order = StoreOrder.objects.create(
            store=self.store, kitchen=self.kitchen, schedule=schedule or self.subuh,
            order_date=self.now.date(), delivery_date=delivery or self.delivery, status=status,
        )
        if qty is not None:
            StoreOrderLine.objects.create(order=order, product=self.product, qty=qty)
        return order

    def test_cutoff_preview_and_apply(self):
        order = self.make_order(qty=Decimal("3"))
        before = self.now - timedelta(seconds=1)
        preview = auto_submit_drafts(now=before)
        self.assertEqual(preview["drafts_found"], 1)
        self.assertFalse(preview["due"])
        with self.assertRaises(BeforeCutoffError):
            auto_submit_drafts(apply=True, now=before)
        self.assertEqual(StoreOrder.objects.get(pk=order.pk).status, "DRAFT")
        self.assertFalse(AuditLog.objects.exists())
        result = auto_submit_drafts(apply=True, now=self.now)
        self.assertEqual((result["sent"], result["no_order"]), (1, 0))
        order.refresh_from_db()
        self.assertEqual(order.status, "KIRIM")
        self.assertTrue(order.auto_submitted)
        self.assertEqual(order.submitted_at, self.now)
        self.assertEqual(AuditLog.objects.get().action, "AUTO_KIRIM")

    def test_only_h_plus_two_drafts_across_schedules(self):
        eligible = self.make_order(qty=5)
        second = self.make_order(qty=2, schedule=self.pagi)
        future = self.make_order(qty=7, delivery=self.delivery + timedelta(days=1))
        empty = self.make_order(qty=None, delivery=self.delivery + timedelta(days=2))
        result = auto_submit_drafts(apply=True, now=self.now)
        self.assertEqual(result["sent"], 2)
        self.assertEqual(result["drafts_found"], 2)
        self.assertEqual(StoreOrder.objects.get(pk=eligible.pk).status, "KIRIM")
        self.assertEqual(StoreOrder.objects.get(pk=second.pk).status, "KIRIM")
        self.assertEqual(StoreOrder.objects.get(pk=future.pk).status, "DRAFT")
        self.assertEqual(StoreOrder.objects.get(pk=empty.pk).status, "DRAFT")

    def test_empty_and_zero_become_no_order(self):
        empty = self.make_order()
        zero = self.make_order(qty=0, schedule=self.pagi)
        result = auto_submit_drafts(apply=True, now=self.now)
        self.assertEqual(result["no_order"], 2)
        self.assertEqual(result["items_removed"], 1)
        self.assertEqual(StoreOrder.objects.get(pk=empty.pk).status, "NO_ORDER")
        self.assertEqual(StoreOrder.objects.get(pk=zero.pk).status, "NO_ORDER")
        self.assertFalse(StoreOrderLine.objects.filter(order=zero).exists())

    def test_fractional_legacy_draft_is_skipped_and_not_rounded(self):
        invalid = self.make_order(qty=Decimal("1.5"))
        valid = self.make_order(qty=Decimal("2"), schedule=self.pagi)
        result = auto_submit_drafts(apply=True, now=self.now)
        self.assertEqual(result["invalid_order_ids"], [invalid.pk])
        self.assertEqual(result["sent"], 1)
        self.assertEqual(StoreOrder.objects.get(pk=invalid.pk).status, "DRAFT")
        self.assertEqual(StoreOrderLine.objects.get(order=invalid).qty, Decimal("1.5"))
        self.assertEqual(StoreOrder.objects.get(pk=valid.pk).status, "KIRIM")

    def test_retry_does_not_duplicate_audit_or_resend(self):
        self.make_order(qty=5)
        self.assertEqual(auto_submit_drafts(apply=True, now=self.now)["sent"], 1)
        self.assertEqual(auto_submit_drafts(apply=True, now=self.now)["sent"], 0)
        self.assertEqual(AuditLog.objects.filter(action="AUTO_KIRIM").count(), 1)

    def test_cutoff_uses_jakarta_even_when_clock_utc(self):
        from datetime import timezone as dt_timezone
        utc_time = datetime(2026, 11, 5, 0, 0, tzinfo=dt_timezone.utc)
        order = self.make_order(qty=1)
        result = auto_submit_drafts(apply=True, now=utc_time)
        self.assertEqual(result["date_wib"], "2026-11-05")
        self.assertEqual(result["time_wib"], "07:00:00")
        self.assertEqual(result["delivery_date"], "2026-11-07")
        self.assertEqual(StoreOrder.objects.get(pk=order.pk).status, "KIRIM")

    def test_command_preview_default_and_apply(self):
        from io import StringIO
        from unittest.mock import patch
        from django.core.management import call_command

        self.make_order(qty=3)
        preview = StringIO()
        with patch("ro_core.auto_submit.timezone.now", return_value=self.now):
            call_command("auto_submit_store_orders", stdout=preview)
        self.assertIn('"mode": "PREVIEW"', preview.getvalue())
        self.assertEqual(StoreOrder.objects.filter(status="DRAFT").count(), 1)
        applied = StringIO()
        with patch("ro_core.auto_submit.timezone.now", return_value=self.now):
            call_command("auto_submit_store_orders", "--apply", stdout=applied)
        self.assertIn('"mode": "APPLY"', applied.getvalue())
        self.assertEqual(StoreOrder.objects.filter(status="KIRIM").count(), 1)

    def test_command_refuses_early_apply(self):
        from io import StringIO
        from unittest.mock import patch
        from django.core.management import call_command
        from django.core.management.base import CommandError

        self.make_order(qty=1)
        early = self.now - timedelta(minutes=1)
        with patch("ro_core.auto_submit.timezone.now", return_value=early):
            with self.assertRaisesMessage(CommandError, "07:00 WIB"):
                call_command("auto_submit_store_orders", "--apply", stdout=StringIO())
        self.assertEqual(StoreOrder.objects.filter(status="DRAFT").count(), 1)
