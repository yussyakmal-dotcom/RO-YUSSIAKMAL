"""Read-only consolidated store demand for the Admin Produksi workspace.

Aggregate ONLY final StoreOrder KIRIM by delivery date + kitchen + delivery
slot. Do not infer production date, create plans, or write to Odoo. Preserve
per-store traceability even when a SKU's template mapping changes later.
"""
from collections import defaultdict

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    ProductionAssignment, Schedule, StoreOrder, StoreOrderLine, Warehouse,
)


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
    )
    headers = {
        order.store_id: order
        for order in order_scope.select_related("store").order_by("store__code")
    }
    stores = list(
        Warehouse.objects.filter(kind=Warehouse.Kind.STORE, active=True)
        .order_by("code")
    )
    status_counts = {
        StoreOrder.Status.KIRIM: 0,
        StoreOrder.Status.NO_ORDER: 0,
        StoreOrder.Status.DRAFT: 0,
        "NOT_ENTERED": 0,
    }
    store_statuses = []
    for store in stores:
        order = headers.get(store.pk)
        label = order.status if order else "NOT_ENTERED"
        status_counts[label] += 1
        store_statuses.append({
            "store_code": store.code,
            "store_name": store.name,
            "status": label,
            "order_id": order.pk if order else None,
            "auto_submitted": order.auto_submitted if order else False,
        })

    lines = list(
        StoreOrderLine.objects.filter(
            order__in=order_scope.filter(status=StoreOrder.Status.KIRIM)
        ).select_related("product", "order__store")
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
                "Rekap diblokir: ada baris KIRIM dengan Qty nol, negatif, "
                "atau desimal. Periksa data pesanan; tidak ada pembulatan otomatis."
            ),
            "invalid_lines": invalid[:50],
            "invalid_count": len(invalid),
        }, status=status.HTTP_409_CONFLICT)

    grouped = {}
    total_units = 0
    for line in lines:
        item = grouped.setdefault(line.product_id, {
            "product_id": line.product_id,
            "sku": line.product.sku,
            "name": line.product.name,
            "qty_total": 0,
            "sources": [],
        })
        quantity = int(line.qty)
        item["qty_total"] += quantity
        total_units += quantity
        item["sources"].append({
            "store_code": line.order.store.code,
            "store_name": line.order.store.name,
            "order_id": line.order_id,
            "qty": str(quantity),
            "auto_submitted": line.order.auto_submitted,
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

    return Response({
        "delivery_date": delivery_date.isoformat(),
        "kitchen": {"code": kitchen.code, "name": kitchen.name},
        "schedule": {"code": schedule.code, "name": schedule.name},
        "basis": "FINAL_KIRIM_ONLY",
        "production_date": None,
        "note": (
            "Tanggal produksi belum ditetapkan. Rekap ini berdasarkan "
            "tanggal dan jadwal kirim; bukan ProductionPlan atau MO."
        ),
        "summary": {
            "stores_total": len(stores),
            "stores_sent": status_counts[StoreOrder.Status.KIRIM],
            "stores_no_order": status_counts[StoreOrder.Status.NO_ORDER],
            "stores_draft": status_counts[StoreOrder.Status.DRAFT],
            "stores_not_entered": status_counts["NOT_ENTERED"],
            "sku_count": len(items),
            "qty_total": str(total_units),
        },
        "store_statuses": store_statuses,
        "items": items,
    })
