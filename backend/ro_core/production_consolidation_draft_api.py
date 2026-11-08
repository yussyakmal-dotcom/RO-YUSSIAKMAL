"""Draft consolidation inputs: resumable, non-final and non-reserving.

This endpoint never creates ProductionPlan, ProductionPlanLine, or alters
StoreOrder.status. It does not decrement or reserve capacity. A second
operator cannot silently overwrite a newer shared draft (version check).
"""
import re

from django.db import IntegrityError, transaction
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AuditLog, ProductionConsolidationDraft, Warehouse
from .production_consolidation_api import (
    ScopeQuery, ConsolidationConflict, _context, _orders, _demand,
    _existing_plan,
)
from .production_demand_api import _production_access


class DraftQty(serializers.CharField):
    def __init__(self, **kwargs):
        super().__init__(max_length=14, allow_blank=True, trim_whitespace=False, **kwargs)

    def run_validation(self, data=serializers.empty):
        result = super().run_validation(data)
        if result and re.fullmatch(r"[0-9]{1,14}", result) is None:
            raise serializers.ValidationError(
                "Qty Draft harus angka bulat tanpa titik, koma atau desimal."
            )
        return result


class DraftItem(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    qty_planned = DraftQty()


class DraftWrite(ScopeQuery):
    production_date = serializers.DateField(required=False, allow_null=True)
    production_schedule_code = serializers.CharField(
        required=False, allow_blank=True, max_length=40,
    )
    order_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False, max_length=1000,
    )
    items = serializers.ListField(
        child=DraftItem(), allow_empty=True, max_length=1000,
    )
    version = serializers.IntegerField(min_value=0, required=True)


def _draft_payload(draft):
    return {
        "id": draft.pk,
        "version": draft.version,
        "production_date": (
            draft.production_date.isoformat()
            if draft.production_date else None
        ),
        "production_schedule_code": (
            draft.production_schedule.code
            if draft.production_schedule_id else None
        ),
        "order_ids": draft.source_order_ids,
        "items": draft.planned_items,
        "updated_at": draft.updated_at.isoformat(),
        "updated_by": (
            draft.updated_by.get_username()
            if draft.updated_by_id else None
        ),
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def consolidation_draft(request):
    _production_access(request.user)
    query = (
        ScopeQuery(data=request.query_params) if request.method == "GET"
        else DraftWrite(data=request.data)
    )
    query.is_valid(raise_exception=True)
    params = query.validated_data
    kitchen, delivery_schedule, production_schedule = _context(params)
    delivery_date = params["delivery_date"]
    scope = {
        "kitchen": kitchen, "delivery_date": delivery_date,
        "delivery_schedule": delivery_schedule,
    }
    if request.method == "GET":
        if _existing_plan(kitchen, delivery_date, delivery_schedule):
            return Response({
                "detail": "Lingkup pengiriman ini sudah difinalisasi.",
            }, status=status.HTTP_409_CONFLICT)
        draft = ProductionConsolidationDraft.objects.filter(
            **scope,
        ).select_related("production_schedule", "updated_by").first()
        return Response({"draft": _draft_payload(draft) if draft else None})

    incoming_ids = params["order_ids"]
    incoming_items = params["items"]
    product_ids = [r["product_id"] for r in incoming_items]
    if len(incoming_ids) != len(set(incoming_ids)):
        return Response({"detail": "Order sumber draft tidak boleh berulang."}, status=400)
    if len(product_ids) != len(set(product_ids)):
        return Response({"detail": "SKU draft tidak boleh berulang."}, status=400)

    try:
        with transaction.atomic():
            # Use the same scope-lock ordering as final consolidation.
            Warehouse.objects.select_for_update().get(pk=kitchen.pk)
            if _existing_plan(kitchen, delivery_date, delivery_schedule):
                raise ConsolidationConflict(
                    "Lingkup pengiriman sudah difinalisasi; draft tidak boleh disimpan."
                )
            eligible, rows, _ = _demand(
                _orders(kitchen, delivery_date, delivery_schedule, lock=True)
            )
            if sorted(incoming_ids) != [o.pk for o in eligible]:
                raise ConsolidationConflict(
                    "Pesanan KIRIM berubah. Muat ulang sebelum menyimpan draft."
                )
            allowed = {row["product_id"] for row in rows}
            if any(pid not in allowed for pid in product_ids):
                raise ConsolidationConflict(
                    "SKU pesanan berubah. Muat ulang sebelum menyimpan draft."
                )

            draft = ProductionConsolidationDraft.objects.select_for_update().filter(
                **scope,
            ).first()
            actual_version = draft.version if draft else 0
            if params["version"] != actual_version:
                raise ConsolidationConflict(
                    "Draft diperbarui oleh operator lain. Tutup dan buka ulang "
                    "untuk melihat versi terbaru; perubahan Anda tidak ditimpa."
                )

            stored_items = [{
                "product_id": row["product_id"],
                "qty_planned": row["qty_planned"],
            } for row in incoming_items if row["qty_planned"] != ""]
            if draft is None:
                draft = ProductionConsolidationDraft.objects.create(
                    **scope,
                    production_date=params.get("production_date"),
                    production_schedule=production_schedule,
                    source_order_ids=[o.pk for o in eligible],
                    planned_items=stored_items,
                    updated_by=request.user,
                    version=1,
                )
                created = True
            else:
                draft.production_date = params.get("production_date")
                draft.production_schedule = production_schedule
                draft.source_order_ids = [o.pk for o in eligible]
                draft.planned_items = stored_items
                draft.version += 1
                draft.updated_by = request.user
                draft.save(update_fields=[
                    "production_date", "production_schedule",
                    "source_order_ids", "planned_items", "version",
                    "updated_by", "updated_at",
                ])
                created = False
            AuditLog.objects.create(
                actor=request.user,
                entity="ProductionConsolidationDraft",
                entity_id=str(draft.pk),
                action="SAVE_DRAFT",
                changes={
                    "delivery_date": delivery_date.isoformat(),
                    "kitchen": kitchen.code,
                    "delivery_schedule": delivery_schedule.code,
                    "draft_version": draft.version,
                    "order_ids": draft.source_order_ids,
                    "items": stored_items,
                    "production_date": (
                        draft.production_date.isoformat()
                        if draft.production_date else None
                    ),
                    "production_schedule": (
                        draft.production_schedule.code
                        if draft.production_schedule_id else None
                    ),
                },
            )
        return Response({"draft": _draft_payload(draft)}, status=(
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        ))
    except ConsolidationConflict as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    except IntegrityError:
        return Response({
            "detail": "Draft berubah saat disimpan. Muat ulang rencana."
        }, status=status.HTTP_409_CONFLICT)
