"""Admin Produksi queue grouped by delivery commitment, not store order.

Pagination and status filters operate on delivery scopes:
  delivery_date × kitchen × delivery_schedule.
Each scope includes ALL final store orders, even when the scope has both KIRIM
and PROSES_PRODUKSI due to a late-arriving store order. No automatic re-plan.
"""
from collections import defaultdict

from django.db.models import Count, Q
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    ProductionConsolidationDraft, ProductionPlan, Schedule, StoreOrder,
    StoreOrderLine, Warehouse,
)
from .production_demand_api import _production_access, _product_uom, _qty_summary


class QueueQuery(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=("ALL", "KIRIM", "PROSES_PRODUKSI"),
        default="ALL", required=False,
    )
    page = serializers.IntegerField(min_value=1, max_value=100000, default=1, required=False)


def _scope_query(rows):
    query = Q(pk__in=[])  # A zero-row result must never match all orders.
    for row in rows:
        query |= Q(
            kitchen_id=row["kitchen_id"],
            delivery_date=row["delivery_date"],
            schedule_id=row["schedule_id"],
        )
    return query


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def production_delivery_queue(request):
    """One row per shipping date/kitchen/delivery slot, all final orders intact."""
    _production_access(request.user)
    query = QueueQuery(data=request.query_params)
    query.is_valid(raise_exception=True)
    status_filter = query.validated_data["status"]
    page = query.validated_data["page"]
    eligible = StoreOrder.objects.filter(
        status__in=("KIRIM", "PROSES_PRODUKSI"),
        store__kind=Warehouse.Kind.STORE,
    )
    scopes = eligible.values(
        "delivery_date", "kitchen_id", "kitchen__code", "kitchen__name",
        "schedule_id", "schedule__code", "schedule__name", "schedule__sort_order",
    ).annotate(
        kirim_count=Count("pk", filter=Q(status="KIRIM")),
        proses_produksi_count=Count("pk", filter=Q(status="PROSES_PRODUKSI")),
    )
    counts = {
        "all": scopes.count(),
        "kirim": scopes.filter(kirim_count__gt=0).count(),
        "proses_produksi": scopes.filter(proses_produksi_count__gt=0).count(),
    }
    filtered = scopes
    if status_filter == "KIRIM":
        filtered = scopes.filter(kirim_count__gt=0)
    if status_filter == "PROSES_PRODUKSI":
        filtered = scopes.filter(proses_produksi_count__gt=0)
    filtered = filtered.order_by(
        "delivery_date", "kitchen__code", "schedule__sort_order", "schedule__code",
    )
    total = filtered.count()
    page_size = 50
    start = (page - 1) * page_size
    selected = list(filtered[start:start + page_size])

    if not selected:
        return Response({
            "status_filter": status_filter, "page": page,
            "page_size": page_size, "total": total,
            "has_more": start + page_size < total,
            "counts": counts, "items": [],
        })

    matcher = _scope_query(selected)
    all_orders = list(
        eligible.filter(matcher).select_related("store", "kitchen", "schedule")
        .order_by("delivery_date", "kitchen__code", "schedule__sort_order", "store__code", "pk")
    )
    order_scope = {}
    grouped_orders = defaultdict(list)
    for order in all_orders:
        key = (order.delivery_date, order.kitchen_id, order.schedule_id)
        order_scope[order.pk] = key
        grouped_orders[key].append(order)

    aggregates = defaultdict(lambda: {
        "sku_ids": set(), "by_uom": {}, "invalid": False,
    })
    for order_id, product_id, value, raw_uom in StoreOrderLine.objects.filter(
        order_id__in=order_scope,
    ).values_list("order_id", "product_id", "qty", "product__uom"):
        scope = order_scope[order_id]
        agg = aggregates[scope]
        agg["sku_ids"].add(product_id)
        if value < 1 or value != value.to_integral_value():
            agg["invalid"] = True
            continue
        unit = _product_uom(raw_uom)
        entry = agg["by_uom"].setdefault(
            unit.casefold(), {"uom": unit, "qty": 0},
        )
        entry["qty"] += int(value)

    plan_by_scope = {}
    for plan in ProductionPlan.objects.filter(matcher).order_by("pk"):
        key = (plan.delivery_date, plan.kitchen_id, plan.delivery_schedule_id)
        plan_by_scope[key] = plan.pk
    draft_scopes = set(ProductionConsolidationDraft.objects.filter(matcher).values_list(
        "delivery_date", "kitchen_id", "delivery_schedule_id",
    ))

    items = []
    for row in selected:
        key = (row["delivery_date"], row["kitchen_id"], row["schedule_id"])
        orders = grouped_orders[key]
        agg = aggregates[key]
        kirim_count = sum(order.status == "KIRIM" for order in orders)
        proses_count = sum(order.status == "PROSES_PRODUKSI" for order in orders)
        state = ("CAMPURAN" if kirim_count and proses_count else
                 "KIRIM" if kirim_count else "PROSES_PRODUKSI")
        items.append({
            "delivery_date": row["delivery_date"].isoformat(),
            "kitchen_code": row["kitchen__code"],
            "kitchen_name": row["kitchen__name"],
            "schedule_code": row["schedule__code"],
            "schedule_name": row["schedule__name"],
            "status": state,
            "order_count": len(orders),
            "store_count": len({order.store_id for order in orders}),
            "kirim_count": kirim_count,
            "proses_produksi_count": proses_count,
            "plan_id": plan_by_scope.get(key),
            "has_consolidation_draft": key in draft_scopes and not plan_by_scope.get(key),
            "sku_count": len(agg["sku_ids"]),
            **_qty_summary(agg["by_uom"], invalid=agg["invalid"]),
            "stores": [{
                "order_id": order.pk,
                "store_code": order.store.code,
                "store_name": order.store.name,
                "status": order.status,
            } for order in orders],
        })
    return Response({
        "status_filter": status_filter, "page": page,
        "page_size": page_size, "total": total,
        "has_more": start + page_size < total,
        "counts": counts, "items": items,
    })
