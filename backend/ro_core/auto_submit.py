"""Daily H-2 automatic finalization of store Draft orders.

Run via the server's systemd timer at 07:00 Asia/Jakarta. This module never
creates an order for combinations that have no Draft, and never writes Odoo.
A transaction and row lock per order make repeat/overlapping runs idempotent.
"""
from datetime import time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from .models import AuditLog, StoreOrder


JAKARTA = ZoneInfo("Asia/Jakarta")
CUTOFF = time(7, 0)
MIN_SUBMITTED_QTY = Decimal("1")


class BeforeCutoffError(ValueError):
    """The daily cutoff has not yet arrived in WIB."""


def auto_submit_drafts(*, apply=False, now=None):
    """Preview or finalize *existing* Drafts with delivery date exactly H+2.

    The target date is always derived from the current Jakarta business date;
    there is deliberately no arbitrary-date or bypass-cutoff option. Invalid
    legacy fractional Drafts are left untouched for manual correction.
    """
    current = timezone.localtime(now or timezone.now(), JAKARTA)
    delivery_date = current.date() + timedelta(days=2)
    due = current.time().replace(tzinfo=None) >= CUTOFF

    if apply and not due:
        raise BeforeCutoffError(
            "Belum pukul 07:00 WIB. Auto-submit H-2 tidak dijalankan."
        )

    ids = list(
        StoreOrder.objects.filter(
            delivery_date=delivery_date, status=StoreOrder.Status.DRAFT
        ).order_by("pk").values_list("pk", flat=True)
    )
    result = {
        "date_wib": current.date().isoformat(),
        "time_wib": current.strftime("%H:%M:%S"),
        "cutoff": "07:00 WIB",
        "delivery_date": delivery_date.isoformat(),
        "due": due,
        "mode": "APPLY" if apply else "PREVIEW",
        "drafts_found": len(ids),
        "sent": 0,
        "no_order": 0,
        "invalid_drafts": 0,
        "skipped_already_finalized": 0,
        "items_sent": 0,
        "items_removed": 0,
        "invalid_order_ids": [],
    }

    if not apply:
        # Preview has no write or row locks. It intentionally does not claim
        # future success; actual apply will validate every Draft under lock.
        for order_id in ids:
            lines = list(
                StoreOrder.objects.get(pk=order_id).lines.values_list("qty", flat=True)
            )
            if any(qty < 0 or qty != qty.to_integral_value() for qty in lines):
                result["invalid_drafts"] += 1
                result["invalid_order_ids"].append(order_id)
            elif any(qty >= MIN_SUBMITTED_QTY for qty in lines):
                result["sent"] += 1
                result["items_sent"] += sum(qty >= MIN_SUBMITTED_QTY for qty in lines)
                result["items_removed"] += sum(qty < MIN_SUBMITTED_QTY for qty in lines)
            else:
                result["no_order"] += 1
                result["items_removed"] += len(lines)
        return result

    for order_id in ids:
        with transaction.atomic():
            order = (
                StoreOrder.objects.select_for_update()
                .filter(
                    pk=order_id,
                    status=StoreOrder.Status.DRAFT,
                    delivery_date=delivery_date,
                )
                .first()
            )
            if order is None:
                result["skipped_already_finalized"] += 1
                continue

            lines = list(order.lines.only("pk", "qty").order_by("pk"))
            if any(
                line.qty < 0 or line.qty != line.qty.to_integral_value()
                for line in lines
            ):
                result["invalid_drafts"] += 1
                result["invalid_order_ids"].append(order_id)
                continue

            keep_ids = [
                line.pk for line in lines if line.qty >= MIN_SUBMITTED_QTY
            ]
            removed = len(lines) - len(keep_ids)
            if removed:
                order.lines.exclude(pk__in=keep_ids).delete()

            sent = bool(keep_ids)
            order.status = (
                StoreOrder.Status.KIRIM if sent else StoreOrder.Status.NO_ORDER
            )
            order.auto_submitted = True
            order.submitted_at = current
            order.save(update_fields=["status", "auto_submitted", "submitted_at"])
            AuditLog.objects.create(
                actor=None,
                entity="StoreOrder",
                entity_id=str(order.pk),
                action="AUTO_KIRIM" if sent else "AUTO_NO_ORDER",
                changes={
                    "items_sent": len(keep_ids),
                    "excluded_below_one": removed,
                    "automatic": True,
                    "delivery_date": delivery_date.isoformat(),
                    "cutoff": "07:00 WIB H-2",
                },
            )

            result["sent" if sent else "no_order"] += 1
            result["items_sent"] += len(keep_ids)
            result["items_removed"] += removed

    return result
