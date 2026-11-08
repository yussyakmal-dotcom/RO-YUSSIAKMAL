"""Read-only consolidated store demand for the Admin Produksi workspace.

Aggregate ONLY final StoreOrder KIRIM by delivery date + kitchen + delivery
slot. Do not infer production date, create plans, or write to Odoo. Preserve
per-store traceability even when a SKU's template mapping changes later.
"""
from collections import defaultdict

from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    ProductionAssignment, ProductionConsolidationDraft, ProductionPlanSource, Schedule, StoreOrder, StoreOrderLine, Warehouse,
)


def _product_uom(value):
    """Use synced Odoo UoM, with 'pcs' only for missing master UoM."""
    return (value or "").strip() or "pcs"


def _qty_summary(groups, *, invalid=False):
    """No mixed-unit arithmetic or fractional values on an operations screen.

    Keep whole quantities in their original UoM. This is NOT unit conversion.
    """
    if invalid:
        return {
            "qty_total": None, "qty_uom": None, "qty_by_uom": [],
            "qty_invalid": True,
        }

    parts = [
        {"uom": unit["uom"], "qty": str(unit["qty"])}
        for _, unit in sorted(groups.items())
    ]
    if len(parts) == 1:
        return {
            "qty_total": parts[0]["qty"], "qty_uom": parts[0]["uom"],
            "qty_by_uom": parts, "qty_invalid": False,
        }
    if not parts:
        return {
            "qty_total": "0", "qty_uom": None,
            "qty_by_uom": [], "qty_invalid": False,
        }
    return {
        "qty_total": None, "qty_uom": None,
        "qty_by_uom": parts, "qty_invalid": False,
    }


def _order_qty_summaries(order_ids):
    """Calculate each order by UoM from its actual lines (no unsafe sums).

    The model currently stores one UoM on each Product rather than on each
    StoreOrderLine; this handles distinct products with differing units, not
    conversion/packing of one product into multiple line UoMs.
    """
    by_order = defaultdict(dict)
    invalid_ids = set()
    if order_ids:
        for order_id, qty, raw_uom in StoreOrderLine.objects.filter(
            order_id__in=order_ids
        ).values_list("order_id", "qty", "product__uom"):
            if qty < 1 or qty != qty.to_integral_value():
                invalid_ids.add(order_id)
                continue
            uom = _product_uom(raw_uom)
            key = uom.casefold()
            unit = by_order[order_id].setdefault(
                key, {"uom": uom, "qty": 0},
            )
            unit["qty"] += int(qty)
    return {
        order_id: _qty_summary(
            by_order[order_id], invalid=(order_id in invalid_ids)
        )
        for order_id in order_ids
    }


class ProductionDemandQuery(serializers.Serializer):
    delivery_date = serializers.DateField()
    kitchen_code = serializers.CharField(max_length=32)
    schedule_code = serializers.CharField(max_length=40)


def _production_access(user):
    if user.is_superuser or user.groups.filter(name__in=("ADMIN", "PRODUCTION")).exists():
        return
    raise PermissionDenied("Hanya Admin Produksi atau Administrator yang boleh melihat rekap.")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def production_demand(request):
    """Return aggregate and store-by-store drilldown; never change any record."""
    _production_access(request.user)
    query = ProductionDemandQuery(data=request.query_params)
    query.is_valid(raise_exception=True)
    params = query.validated_data

    kitchen = get_object_or_404(
        Warehouse,
        code=params["kitchen_code"].upper(),
        kind__in=(Warehouse.Kind.KITCHEN, Warehouse.Kind.PACKING),
        active=True,
    )
    schedule = get_object_or_404(
        Schedule, code=params["schedule_code"], active=True,
    )
    delivery_date = params["delivery_date"]
    order_scope = StoreOrder.objects.filter(
        kitchen=kitchen,
        schedule=schedule,
        delivery_date=delivery_date,
        store__kind=Warehouse.Kind.STORE,
        status__in=(StoreOrder.Status.KIRIM, StoreOrder.Status.PROSES_PRODUKSI),
    )
    headers = list(
        order_scope.select_related("store").order_by("store__code", "pk")
    )
    status_counts = {
        StoreOrder.Status.KIRIM: sum(
            order.status == StoreOrder.Status.KIRIM for order in headers
        ),
        StoreOrder.Status.PROSES_PRODUKSI: sum(
            order.status == StoreOrder.Status.PROSES_PRODUKSI for order in headers
        ),
    }
    store_statuses = [
        {
            "store_code": order.store.code,
            "store_name": order.store.name,
            "status": order.status,
            "order_id": order.pk,
            "auto_submitted": order.auto_submitted,
        }
        for order in headers
    ]

    lines = list(
        StoreOrderLine.objects.filter(order__in=order_scope)
        .select_related("product", "order__store")
        .order_by("product__sku", "product_id", "order__store__code", "order_id")
    )

    # An old order may have been modified before the integer-only API existed.
    # Never silently round, truncate, or exclude invalid lines from the total.
    invalid = [
        {"order_id": line.order_id, "sku": line.product.sku, "qty": str(line.qty)}
        for line in lines
        if line.qty < 1 or line.qty != line.qty.to_integral_value()
    ]
    if invalid:
        return Response({
            "detail": (
                "Rekap diblokir: ada baris pesanan final dengan Qty nol, negatif, "
                "atau desimal. Periksa data pesanan; tidak ada pembulatan otomatis."
            ),
            "invalid_lines": invalid[:50],
            "invalid_count": len(invalid),
        }, status=status.HTTP_409_CONFLICT)

    grouped = {}
    for line in lines:
        item = grouped.setdefault(line.product_id, {
            "product_id": line.product_id,
            "sku": line.product.sku,
            "name": line.product.name,
            "uom": _product_uom(line.product.uom),
            "qty_total": 0,
            "sources": [],
        })
        quantity = int(line.qty)
        item["qty_total"] += quantity
        item["sources"].append({
            "store_code": line.order.store.code,
            "store_name": line.order.store.name,
            "order_id": line.order_id,
            "qty": str(quantity),
            "auto_submitted": line.order.auto_submitted,
            "status": line.order.status,
        })

    # Display order is middleware-owned; current template flag MUST NOT
    # remove historical, already-submitted demand.
    assignments = {
        record.product_id: record.sort_order
        for record in ProductionAssignment.objects.filter(
            kitchen=kitchen, product_id__in=grouped.keys()
        )
    }
    items = sorted(
        grouped.values(),
        key=lambda entry: (
            assignments.get(entry["product_id"], 1_000_000),
            (entry["sku"] or "").casefold(),
            entry["product_id"],
        ),
    )
    for item in items:
        item["qty_total"] = str(item["qty_total"])
        item["store_count"] = len({s["store_code"] for s in item["sources"]})

    by_uom = {}
    for entry in items:
        key = entry["uom"].casefold()
        unit = by_uom.setdefault(key, {"uom": entry["uom"], "qty": 0})
        unit["qty"] += int(entry["qty_total"])
    qty_summary = _qty_summary(by_uom)

    return Response({
        "delivery_date": delivery_date.isoformat(),
        "kitchen": {"code": kitchen.code, "name": kitchen.name},
        "schedule": {"code": schedule.code, "name": schedule.name},
        "basis": "KIRIM_AND_PROSES_PRODUKSI",
        "production_date": None,
        "note": (
            "Tanggal produksi belum ditetapkan. Rekap ini berdasarkan "
            "tanggal dan jadwal kirim; bukan ProductionPlan atau MO."
        ),
        "summary": {
            "stores_total": len(headers),
            "stores_sent": status_counts[StoreOrder.Status.KIRIM],
            "stores_in_production": status_counts[StoreOrder.Status.PROSES_PRODUKSI],
            "sku_count": len(items),
            **qty_summary,
        },
        "store_statuses": store_statuses,
        "items": items,
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recent_final_store_orders(request):
    """Find real KIRIM scopes to navigate from rekap filters safely.

    This is deliberately independent of date/kitchen/schedule selected in
    the rekap. It is read-only, restricted to Production/Admin, and bounded.
    """
    _production_access(request.user)
    orders = (
        StoreOrder.objects.filter(
            status=StoreOrder.Status.KIRIM,
            store__kind=Warehouse.Kind.STORE,
        )
        .select_related("store", "kitchen", "schedule")
        .annotate(
            line_count=Count("lines"),
            qty_total=Sum("lines__qty"),
            recent_at=Coalesce("submitted_at", "created_at"),
        )
        .order_by("-recent_at", "-pk")[:30]
    )
    recent_summaries = _order_qty_summaries([order.pk for order in orders])
    return Response({
        "limit": 30,
        "items": [
            {
                "order_id": order.pk,
                "store_code": order.store.code,
                "store_name": order.store.name,
                "kitchen_code": order.kitchen.code,
                "kitchen_name": order.kitchen.name,
                "schedule_code": order.schedule.code,
                "schedule_name": order.schedule.name,
                "delivery_date": order.delivery_date.isoformat(),
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "auto_submitted": order.auto_submitted,
                "sku_count": order.line_count,
                **recent_summaries[order.pk],
            }
            for order in orders
        ],
    })


class ProductionInboxQuery(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=("ALL", StoreOrder.Status.KIRIM, StoreOrder.Status.PROSES_PRODUKSI),
        required=False, default="ALL",
    )
    page = serializers.IntegerField(min_value=1, max_value=100000, required=False, default=1)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def production_inbox(request):
    """Global production queue, no implicit date/kitchen/slot filter.

    Only KIRIM and PROSES_PRODUKSI are visible. DRAFT and NO_ORDER are
    intentionally not included, and neither pagination nor filtering writes
    database state. Status changes occur only after a real consolidation step.
    """
    _production_access(request.user)
    query = ProductionInboxQuery(data=request.query_params)
    query.is_valid(raise_exception=True)
    selected = query.validated_data["status"]
    page = query.validated_data["page"]

    eligible = StoreOrder.objects.filter(
        status__in=(StoreOrder.Status.KIRIM, StoreOrder.Status.PROSES_PRODUKSI),
        store__kind=Warehouse.Kind.STORE,
    )
    counts = {
        StoreOrder.Status.KIRIM: eligible.filter(status=StoreOrder.Status.KIRIM).count(),
        StoreOrder.Status.PROSES_PRODUKSI: eligible.filter(
            status=StoreOrder.Status.PROSES_PRODUKSI
        ).count(),
    }
    records = eligible if selected == "ALL" else eligible.filter(status=selected)
    page_size = 50
    total = records.count()
    start = (page - 1) * page_size

    orders = (
        records.select_related("store", "kitchen", "schedule")
        .annotate(
            line_count=Count("lines"),
            qty_total=Sum("lines__qty"),
            priority=Case(
                When(status=StoreOrder.Status.KIRIM, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        )
        .order_by("priority", "delivery_date", "kitchen__code", "schedule__sort_order", "store__code", "pk")
        [start:start + page_size]
    )

    order_ids = [order.pk for order in orders]
    inbox_summaries = _order_qty_summaries(order_ids)
    plan_by_order = dict(ProductionPlanSource.objects.filter(
        order_id__in=order_ids
    ).values_list("order_id", "plan_id"))
    # One resumable draft belongs to the delivery scope, not individual orders.
    # It is never a StoreOrder status and never reserves production capacity.
    scopes = {(order.kitchen_id, order.delivery_date, order.schedule_id) for order in orders}
    draft_scopes = set(
        ProductionConsolidationDraft.objects.filter(
            kitchen_id__in={x[0] for x in scopes},
            delivery_date__in={x[1] for x in scopes},
            delivery_schedule_id__in={x[2] for x in scopes},
        ).values_list("kitchen_id", "delivery_date", "delivery_schedule_id")
    )
    return Response({
        "status_filter": selected,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": start + page_size < total,
        "counts": {
            "kirim": counts[StoreOrder.Status.KIRIM],
            "proses_produksi": counts[StoreOrder.Status.PROSES_PRODUKSI],
            "all": sum(counts.values()),
        },
        "items": [
            {
                "order_id": order.pk,
                "status": order.status,
                "plan_id": plan_by_order.get(order.pk),
                "has_consolidation_draft": (
                    order.status == StoreOrder.Status.KIRIM and
                    (order.kitchen_id, order.delivery_date, order.schedule_id)
                    in draft_scopes
                ),
                "store_code": order.store.code,
                "store_name": order.store.name,
                "kitchen_code": order.kitchen.code,
                "kitchen_name": order.kitchen.name,
                "delivery_date": order.delivery_date.isoformat(),
                "schedule_code": order.schedule.code,
                "schedule_name": order.schedule.name,
                "sku_count": order.line_count,
                **inbox_summaries[order.pk],
                "auto_submitted": order.auto_submitted,
            }
            for order in orders
        ],
    })
