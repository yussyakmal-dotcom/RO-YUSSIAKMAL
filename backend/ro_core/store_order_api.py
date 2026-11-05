"""Small, transactional Draft/Kirim API for Admin Toko.

A saved Draft remains editable. Sending keeps only Qty >= 1, and locks the
order. Product lists come from the kitchen's manually maintained template,
not from Odoo Product Category.
"""
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AuditLog, Product, ProductionAssignment, Schedule, StoreOrder,
    StoreOrderLine, UserWarehouseAccess, Warehouse,
)


class OrderContextSerializer(serializers.Serializer):
    store_code = serializers.CharField(max_length=32)
    kitchen_code = serializers.CharField(max_length=32)
    delivery_date = serializers.DateField()
    schedule_code = serializers.CharField(max_length=40)


class OrderItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    qty = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"),
    )


class SaveDraftSerializer(OrderContextSerializer):
    items = OrderItemSerializer(many=True, allow_empty=True)


def _assert_store_access(user, store):
    if user.is_superuser or user.groups.filter(name="ADMIN").exists():
        return
    if not user.groups.filter(name="STORE").exists():
        raise PermissionDenied("Hanya Admin Toko atau Administrator boleh mengakses pesanan.")
    if not UserWarehouseAccess.objects.filter(user=user, warehouse=store).exists():
        raise PermissionDenied("Akun ini tidak ditugaskan pada toko tersebut.")


def _resolve_context(user, data):
    store = get_object_or_404(
        Warehouse, code=data["store_code"].upper(), kind="STORE", active=True
    )
    _assert_store_access(user, store)
    kitchen = get_object_or_404(
        Warehouse, code=data["kitchen_code"].upper(),
        kind__in=("KITCHEN", "PACKING"), active=True,
    )
    schedule = get_object_or_404(
        Schedule, code=data["schedule_code"], active=True
    )
    return store, kitchen, schedule


def _order_identity(store, kitchen, delivery_date, schedule):
    return dict(
        store=store, kitchen=kitchen, delivery_date=delivery_date,
        schedule=schedule,
    )


def _order_payload(order, store, kitchen, delivery_date, schedule):
    active_assignments = list(
        ProductionAssignment.objects.filter(
            kitchen=kitchen, is_active=True, product__active=True,
        ).select_related("product").order_by(
            "sort_order", "product__name", "product_id"
        )
    )
    existing_lines = {
        line.product_id: line
        for line in (
            StoreOrderLine.objects.filter(order=order).select_related("product")
            if order is not None else []
        )
    }
    active_ids = {entry.product_id for entry in active_assignments}
    items = [
        {
            "product_id": entry.product_id,
            "sku": entry.product.sku,
            "name": entry.product.name,
            "qty": str(existing_lines.get(entry.product_id).qty)
            if entry.product_id in existing_lines else "0",
            "active_in_template": True,
        }
        for entry in active_assignments
    ]
    # If the template changes after a Draft was saved, do not silently lose
    # its previously entered positive quantities. Show them for review.
    for product_id, line in existing_lines.items():
        if product_id not in active_ids:
            items.append({
                "product_id": product_id,
                "sku": line.product.sku,
                "name": line.product.name,
                "qty": str(line.qty),
                "active_in_template": False,
            })
    return {
        "id": order.id if order else None,
        "store": {"code": store.code, "name": store.name},
        "kitchen": {"code": kitchen.code, "name": kitchen.name},
        "delivery_date": delivery_date.isoformat(),
        "schedule": schedule.code,
        "status": order.status if order else StoreOrder.Status.DRAFT,
        "editable": order is None or order.status == StoreOrder.Status.DRAFT,
        "items": items,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def store_order_form(request):
    """GET by store+kitchen+date+schedule; POST replaces editable Draft Qty."""
    if request.method == "GET":
        serializer = OrderContextSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        store, kitchen, schedule = _resolve_context(request.user, data)
        order = StoreOrder.objects.filter(**_order_identity(
            store, kitchen, data["delivery_date"], schedule
        )).first()
        return Response(_order_payload(
            order, store, kitchen, data["delivery_date"], schedule
        ))

    serializer = SaveDraftSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    store, kitchen, schedule = _resolve_context(request.user, data)

    seen = set()
    for item in data["items"]:
        pid = item["product_id"]
        if pid in seen:
            raise ValidationError({"items": f"Product ID {pid} muncul dua kali."})
        seen.add(pid)

    with transaction.atomic():
        order, created = StoreOrder.objects.get_or_create(
            **_order_identity(store, kitchen, data["delivery_date"], schedule),
            defaults={"order_date": timezone.localdate()},
        )
        order = StoreOrder.objects.select_for_update().get(pk=order.pk)
        if order.status != StoreOrder.Status.DRAFT:
            return Response(
                {"detail": "Pesanan sudah Kirim/No Order dan tidak bisa diedit."},
                status=status.HTTP_409_CONFLICT,
            )

        active_product_ids = set(
            ProductionAssignment.objects.filter(
                kitchen=kitchen, is_active=True, product__active=True
            ).values_list("product_id", flat=True)
        )
        old_lines = {
            line.product_id: line.qty
            for line in order.lines.all()
        }
        allowed_ids = active_product_ids | set(old_lines)
        invalid_ids = seen - allowed_ids
        if invalid_ids:
            raise ValidationError({
                "items": f"Product ID bukan bagian template dapur: {sorted(invalid_ids)}"
            })

        # Sparse Draft: we only store positive entries. Missing items come
        # back with Qty 0 from the template when the form is reopened.
        new_qty = {
            item["product_id"]: item["qty"]
            for item in data["items"] if item["qty"] > 0
        }
        order.lines.exclude(product_id__in=new_qty).delete()
        for product_id, qty in new_qty.items():
            StoreOrderLine.objects.update_or_create(
                order=order, product_id=product_id, defaults={"qty": qty},
            )
        if old_lines != new_qty or created:
            AuditLog.objects.create(
                actor=request.user, entity="StoreOrder",
                entity_id=str(order.pk), action="SAVE_DRAFT",
                changes={
                    "before": {str(k): str(v) for k, v in old_lines.items()},
                    "after": {str(k): str(v) for k, v in new_qty.items()},
                },
            )
    return Response(
        _order_payload(order, store, kitchen, data["delivery_date"], schedule)
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_store_order(request, order_id):
    """Send the current Draft: remove Qty < 1 and lock its remaining lines."""
    with transaction.atomic():
        order = get_object_or_404(
            StoreOrder.objects.select_for_update().select_related(
                "store", "kitchen", "schedule"
            ), pk=order_id,
        )
        _assert_store_access(request.user, order.store)
        if order.status != StoreOrder.Status.DRAFT:
            return Response(
                {"detail": "Pesanan sudah diproses dan tidak dapat dikirim ulang."},
                status=status.HTTP_409_CONFLICT,
            )
        removed = order.lines.filter(qty__lt=Decimal("1")).delete()[0]
        item_count = order.lines.count()
        order.status = (
            StoreOrder.Status.KIRIM if item_count else StoreOrder.Status.NO_ORDER
        )
        order.submitted_at = timezone.now()
        order.auto_submitted = False
        order.save(update_fields=["status", "submitted_at", "auto_submitted"])
        AuditLog.objects.create(
            actor=request.user, entity="StoreOrder", entity_id=str(order.pk),
            action="KIRIM" if item_count else "NO_ORDER",
            changes={
                "items_sent": item_count,
                "excluded_below_one": removed,
                "automatic": False,
            },
        )
    return Response({
        "id": order.pk, "status": order.status,
        "editable": False, "items_sent": item_count,
        "excluded_below_one": removed,
    })
