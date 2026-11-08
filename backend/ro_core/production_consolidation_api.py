"""V1 local-only, atomic production consolidation.

Delivery commitments (date/slot/Qty) are immutable. Operators explicitly
select a production date + production schedule and enter planned Qty per SKU.
Plans with shortfall are valid; capacity overruns or missing capacity are not.
NO Odoo write, BoM calculation, automatic rescheduling or invented MO Qty.
"""
from collections import defaultdict
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AuditLog, ProductCapacity, ProductionConsolidationDraft, ProductionPlan, ProductionPlanLine,
    ProductionPlanSource, Schedule, StoreOrder, StoreOrderLine, Warehouse,
)
from .production_demand_api import _production_access, _product_uom
from .store_order_api import WholeNumberQtyField, _qty_text


class ScopeQuery(serializers.Serializer):
    kitchen_code = serializers.CharField(max_length=32)
    delivery_date = serializers.DateField()
    delivery_schedule_code = serializers.CharField(max_length=40)
    production_date = serializers.DateField(required=False)
    production_schedule_code = serializers.CharField(max_length=40, required=False)


class PlannedItem(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    qty_planned = WholeNumberQtyField()


class SaveConsolidation(ScopeQuery):
    draft_version = serializers.IntegerField(min_value=0, required=False, default=0)
    production_date = serializers.DateField(required=True)
    production_schedule_code = serializers.CharField(max_length=40, required=True)
    order_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False,
    )
    items = PlannedItem(many=True, allow_empty=False)


class ConsolidationConflict(Exception):
    pass


def _recipe_output(product):
    value = product.bom_output_qty
    if not product.bom_odoo_id or value is None or value <= 0:
        return None
    return _qty_text(value)


def _context(params):
    kitchen = get_object_or_404(
        Warehouse, code=params["kitchen_code"].upper(),
        kind__in=(Warehouse.Kind.KITCHEN, Warehouse.Kind.PACKING), active=True,
    )
    delivery_schedule = get_object_or_404(
        Schedule, code=params["delivery_schedule_code"], active=True,
    )
    production_schedule = None
    if params.get("production_schedule_code"):
        production_schedule = get_object_or_404(
            Schedule, code=params["production_schedule_code"], active=True,
        )
    return kitchen, delivery_schedule, production_schedule


def _orders(kitchen, delivery_date, delivery_schedule, *, lock=False):
    qs = StoreOrder.objects.filter(
        kitchen=kitchen, delivery_date=delivery_date,
        schedule=delivery_schedule, store__kind=Warehouse.Kind.STORE,
    ).select_related("store").order_by("pk")
    if lock:
        qs = qs.select_for_update()
    return list(qs)


def _demand(orders):
    eligible = [o for o in orders if o.status == StoreOrder.Status.KIRIM]
    if not eligible:
        raise ConsolidationConflict(
            "Tidak ada pesanan KIRIM pada lingkup ini untuk konsolidasi baru."
        )
    lines = list(
        StoreOrderLine.objects.filter(order__in=eligible)
        .select_related("product", "order__store")
        .order_by("product__sku", "product_id", "order__store__code", "order_id")
    )
    if not lines:
        raise ConsolidationConflict("Pesanan KIRIM tidak memiliki Qty SKU yang valid.")
    grouped = {}
    snapshots = defaultdict(list)
    for line in lines:
        q = line.qty
        if q < 1 or q != q.to_integral_value():
            raise ConsolidationConflict(
                "Ada Qty pecahan, nol, atau negatif pada pesanan final; "
                "perbaiki sumber terlebih dahulu. Tidak ada pembulatan."
            )
        uom = _product_uom(line.product.uom)
        entry = grouped.setdefault(line.product_id, {
            "product_id": line.product_id,
            "sku": line.product.sku,
            "name": line.product.name,
            "uom": uom,
            "qty_requested": 0,
            "bom_output_qty": _recipe_output(line.product),
            "sources": [],
        })
        entry["qty_requested"] += int(q)
        entry["sources"].append({
            "order_id": line.order_id, "store_code": line.order.store.code,
            "store_name": line.order.store.name, "qty": str(int(q)),
        })
        snapshots[line.order_id].append({
            "product_id": line.product_id, "sku": line.product.sku,
            "name": line.product.name, "uom": uom, "qty": str(int(q)),
        })
    rows = sorted(grouped.values(), key=lambda e: (
        e["sku"].casefold(), e["product_id"],
    ))
    for row in rows:
        row["qty_requested"] = str(row["qty_requested"])
    return eligible, rows, snapshots


def _capacity(rows, production_date, production_schedule, *, lock=False):
    product_ids = [r["product_id"] for r in rows]
    if not production_schedule:
        return {pid: None for pid in product_ids}
    qs = ProductCapacity.objects.filter(
        product_id__in=product_ids, schedule=production_schedule,
    ).order_by("product_id")
    if lock:
        qs = qs.select_for_update()
    limits = {c.product_id: c.max_qty for c in qs}
    if production_date is None:
        return {
            pid: {"max": lim, "used": None, "remaining": None}
            for pid, lim in limits.items()
        }
    # Historical plans have unknown production schedule; block affected SKUs,
    # rather than silently pretending their capacity is free.
    if ProductionPlanLine.objects.filter(
        plan__production_date=production_date,
        plan__production_schedule__isnull=True,
        product_id__in=product_ids,
    ).exists():
        raise ConsolidationConflict(
            "Ada rencana historis tanpa jadwal produksi untuk tanggal dan SKU "
            "ini. Periksa rencana lama sebelum memakai kapasitas."
        )
    used_rows = ProductionPlanLine.objects.filter(
        plan__production_date=production_date,
        plan__production_schedule=production_schedule,
        product_id__in=product_ids,
    ).values("product_id").annotate(used=Sum("qty_planned"))
    used = {x["product_id"]: x["used"] for x in used_rows}
    output = {}
    for pid, maximum in limits.items():
        taken = used.get(pid, Decimal("0"))
        if taken < 0 or taken != taken.to_integral_value():
            raise ConsolidationConflict(
                "Ada Qty rencana historis yang tidak valid; periksa kapasitas."
            )
        remaining = maximum - taken
        output[pid] = {
            "max": maximum, "used": taken,
            "remaining": max(Decimal("0"), remaining),
        }
    return output


def _capacity_payload(entry):
    if entry is None:
        return {
            "capacity_qty": None, "capacity_used": None,
            "capacity_available": None,
        }
    return {
        "capacity_qty": str(int(entry["max"]))
        if entry["max"] == entry["max"].to_integral_value() else None,
        "capacity_used": str(int(entry["used"]))
        if entry["used"] is not None and entry["used"] == entry["used"].to_integral_value() else None,
        "capacity_available": str(int(entry["remaining"]))
        if entry["remaining"] is not None and entry["remaining"] == entry["remaining"].to_integral_value() else None,
    }


def _existing_plan(kitchen, delivery_date, delivery_schedule):
    return ProductionPlan.objects.filter(
        kitchen=kitchen, delivery_date=delivery_date,
        delivery_schedule=delivery_schedule,
    ).exists()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def preview_consolidation(request):
    _production_access(request.user)
    query = ScopeQuery(data=request.query_params)
    query.is_valid(raise_exception=True)
    params = query.validated_data
    kitchen, delivery_schedule, production_schedule = _context(params)
    delivery_date = params["delivery_date"]
    orders = _orders(kitchen, delivery_date, delivery_schedule)
    if _existing_plan(kitchen, delivery_date, delivery_schedule):
        return Response({
            "detail": "Lingkup kirim ini sudah memiliki rencana produksi. "
            "Tidak boleh dikonsolidasi ulang."
        }, status=status.HTTP_409_CONFLICT)
    try:
        eligible, rows, _ = _demand(orders)
        capacities = _capacity(
            rows, params.get("production_date"), production_schedule,
        )
    except ConsolidationConflict as e:
        return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
    for row in rows:
        row.update(_capacity_payload(capacities.get(row["product_id"])))
    return Response({
        "kitchen": {"code": kitchen.code, "name": kitchen.name},
        "delivery_date": delivery_date.isoformat(),
        "delivery_schedule": {
            "code": delivery_schedule.code, "name": delivery_schedule.name,
        },
        "production_date": (
            params["production_date"].isoformat()
            if params.get("production_date") else None
        ),
        "production_schedule": (
            {"code": production_schedule.code, "name": production_schedule.name}
            if production_schedule else None
        ),
        "production_schedules": list(
            Schedule.objects.filter(active=True).order_by("sort_order", "code")
            .values("code", "name")
        ),
        "order_ids": [o.pk for o in eligible],
        "orders": [{
            "order_id": o.pk, "store_code": o.store.code,
            "store_name": o.store.name,
        } for o in eligible],
        "items": rows,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_consolidation(request):
    _production_access(request.user)
    query = SaveConsolidation(data=request.data)
    query.is_valid(raise_exception=True)
    params = query.validated_data
    kitchen, delivery_schedule, production_schedule = _context(params)
    delivery_date = params["delivery_date"]
    production_date = params["production_date"]
    input_orders = params["order_ids"]
    input_rows = params["items"]

    if len(input_orders) != len(set(input_orders)):
        return Response({"detail": "Order sumber tidak boleh berulang."}, status=400)
    input_products = [r["product_id"] for r in input_rows]
    if len(input_products) != len(set(input_products)):
        return Response({"detail": "SKU rencana tidak boleh berulang."}, status=400)

    try:
        with transaction.atomic():
            # Shared scope lock ensures save-draft and finalize never race.
            Warehouse.objects.select_for_update().get(pk=kitchen.pk)
            orders = _orders(kitchen, delivery_date, delivery_schedule, lock=True)
            eligible, rows, snapshots = _demand(orders)
            # Prevent stale previews, phantom new KIRIM orders and replays.
            if sorted(input_orders) != [o.pk for o in eligible]:
                raise ConsolidationConflict(
                    "Pesanan KIRIM berubah sejak pratinjau. Muat ulang rencana."
                )
            if _existing_plan(kitchen, delivery_date, delivery_schedule):
                raise ConsolidationConflict(
                    "Lingkup tanggal/jadwal kirim sudah dikonsolidasi."
                )
            shared_draft = ProductionConsolidationDraft.objects.select_for_update().filter(
                kitchen=kitchen, delivery_date=delivery_date,
                delivery_schedule=delivery_schedule,
            ).first()
            actual_draft_version = shared_draft.version if shared_draft else 0
            if params["draft_version"] != actual_draft_version:
                raise ConsolidationConflict(
                    "Draft diubah operator lain. Buka ulang draft terbaru "
                    "sebelum konsolidasi final; tidak ada data yang diubah."
                )
            if sorted(input_products) != sorted(r["product_id"] for r in rows):
                raise ConsolidationConflict(
                    "Daftar SKU berubah sejak pratinjau. Muat ulang rencana."
                )
            capacity = _capacity(
                rows, production_date, production_schedule, lock=True,
            )
            selected = {r["product_id"]: r["qty_planned"] for r in input_rows}
            checked = []
            for row in rows:
                pid = row["product_id"]
                maximum = capacity.get(pid)
                if maximum is None:
                    raise ConsolidationConflict(
                        "Kapasitas produksi belum diatur untuk SKU "
                        f"{row['sku'] or pid} pada jadwal produksi ini."
                    )
                if any(
                    n != n.to_integral_value() for n in (
                        maximum["max"], maximum["remaining"],
                    )
                ):
                    raise ConsolidationConflict(
                        "Ada kapasitas pecahan pada master. "
                        "Perbaiki kapasitas sebelum konsolidasi."
                    )
                planned = selected[pid]
                if planned < 1:
                    raise ConsolidationConflict(
                        "Qty Produksi tiap SKU minimal 1 sampai kebijakan "
                        "Qty Produksi 0 ditetapkan."
                    )
                if planned > maximum["remaining"]:
                    raise ConsolidationConflict(
                        "Qty Produksi melebihi kapasitas tersedia untuk SKU "
                        f"{row['sku'] or pid}. Tidak bisa disimpan."
                    )
                checked.append((row, planned, maximum))
            plan = ProductionPlan.objects.create(
                kitchen=kitchen, delivery_date=delivery_date,
                delivery_schedule=delivery_schedule,
                production_date=production_date,
                production_schedule=production_schedule,
                status=ProductionPlan.Status.DRAFT,
            )
            for row, planned, maximum in checked:
                requested = Decimal(row["qty_requested"])
                ProductionPlanLine.objects.create(
                    plan=plan, product_id=row["product_id"],
                    qty_requested=requested,
                    qty_planned=planned,
                    capacity_qty=maximum["max"],
                    capacity_used_before=maximum["used"],
                    qty_shortfall=max(Decimal("0"), requested - planned),
                    qty_mo=None, batch_qty=None, bom_snapshot={},
                )
            for o in eligible:
                ProductionPlanSource.objects.create(
                    plan=plan, order=o, lines_snapshot=snapshots[o.pk],
                )
            StoreOrder.objects.filter(
                pk__in=[o.pk for o in eligible],
                status=StoreOrder.Status.KIRIM,
            ).update(status=StoreOrder.Status.PROSES_PRODUKSI)
            if shared_draft:
                shared_draft.delete()
            AuditLog.objects.create(
                actor=request.user, entity="ProductionPlan",
                entity_id=str(plan.pk), action="CONSOLIDATE",
                changes={
                    "delivery_date": delivery_date.isoformat(),
                    "delivery_schedule": delivery_schedule.code,
                    "production_date": production_date.isoformat(),
                    "production_schedule": production_schedule.code,
                    "order_ids": [o.pk for o in eligible],
                    "items": [{
                        "product_id": row["product_id"],
                        "uom": row["uom"],
                        "qty_requested": row["qty_requested"],
                        "qty_planned": str(int(planned)),
                        "capacity_qty": str(int(cap["max"])),
                        "capacity_used_before": str(int(cap["used"])),
                        "qty_shortfall": str(int(max(
                            Decimal("0"), Decimal(row["qty_requested"]) - planned
                        ))),
                    } for row, planned, cap in checked],
                },
            )
    except ConsolidationConflict as e:
        return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
    except IntegrityError:
        return Response({
            "detail": "Rencana sudah disimpan oleh operator lain. "
            "Muat ulang antrean."
        }, status=status.HTTP_409_CONFLICT)

    return Response({
        "plan_id": plan.pk, "status": plan.status,
        "order_ids": [o.pk for o in eligible],
        "shortfall_sku_count": sum(
            Decimal(row["qty_requested"]) > planned
            for row, planned, _ in checked
        ),
        "detail": "Konsolidasi tersimpan; kebutuhan kurang tetap tercatat.",
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def consolidation_detail(request, plan_id):
    _production_access(request.user)
    plan = get_object_or_404(
        ProductionPlan.objects.select_related(
            "kitchen", "delivery_schedule", "production_schedule",
        ), pk=plan_id,
    )
    sources = list(
        plan.sources.select_related("order__store").order_by("order_id")
    )
    rows = list(plan.lines.select_related("product").order_by(
        "product__sku", "product_id",
    ))
    return Response({
        "plan_id": plan.pk, "status": plan.status,
        "kitchen": {"code": plan.kitchen.code, "name": plan.kitchen.name},
        "delivery_date": plan.delivery_date.isoformat(),
        "delivery_schedule": {
            "code": plan.delivery_schedule.code,
            "name": plan.delivery_schedule.name,
        },
        "production_date": plan.production_date.isoformat(),
        "production_schedule": (
            {"code": plan.production_schedule.code,
             "name": plan.production_schedule.name}
            if plan.production_schedule else None
        ),
        "sources": [{
            "order_id": source.order_id,
            "store_code": source.order.store.code,
            "store_name": source.order.store.name,
            "lines_snapshot": source.lines_snapshot,
        } for source in sources],
        "items": [{
            "product_id": row.product_id,
            "sku": row.product.sku, "name": row.product.name,
            "uom": next((
                snap["uom"] for source in sources
                for snap in source.lines_snapshot
                if snap["product_id"] == row.product_id
            ), _product_uom(row.product.uom)),
            "qty_requested": str(int(row.qty_requested)),
            "qty_planned": str(int(row.qty_planned)),
            "capacity_qty": str(int(row.capacity_qty)),
            "capacity_used": str(int(row.capacity_used_before)),
            "capacity_available": str(int(
                max(Decimal("0"), row.capacity_qty - row.capacity_used_before)
            )),
            "qty_shortfall": str(int(row.qty_shortfall)),
            "qty_mo": str(row.qty_mo) if row.qty_mo is not None else None,
            "bom_output_qty": _recipe_output(row.product),
        } for row in rows],
        "shortfall_sku_count": sum(row.qty_shortfall > 0 for row in rows),
        "note": (
            "Status PROSES_PRODUKSI berarti sudah masuk perencanaan, bukan "
            "semua kebutuhan toko telah terpenuhi. Belum membuat MO Odoo."
        ),
    })
