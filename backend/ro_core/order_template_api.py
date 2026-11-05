"""Read-only kitchen order templates for the future Admin Toko quantity grid."""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ProductionAssignment, Warehouse


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def kitchen_order_template(request, kitchen_code):
    kitchen = get_object_or_404(
        Warehouse, code=kitchen_code.upper(), active=True,
        kind__in=("KITCHEN", "PACKING"),
    )
    rows = ProductionAssignment.objects.filter(
        kitchen=kitchen, is_active=True, product__active=True,
    ).select_related("product").order_by("sort_order", "product__name", "product_id")
    return Response({
        "kitchen": {"id": kitchen.id, "code": kitchen.code, "name": kitchen.name},
        "count": rows.count(),
        "items": [
            {
                "id": item.product_id,
                "sku": item.product.sku,
                "name": item.product.name,
                "qty": 0,
            }
            for item in rows
        ],
    })
