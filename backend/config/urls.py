from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from ro_core.order_template_api import kitchen_order_template
from ro_core.store_order_api import store_order_form, send_store_order

def health(_request):
    return JsonResponse({"status": "ok", "service": "ro-middleware"})

urlpatterns = [
    path("health/", health, name="health"),
    path("api/v1/order-templates/<str:kitchen_code>/", kitchen_order_template, name="kitchen-order-template"),
    path("api/v1/store-orders/", store_order_form, name="store-order-form"),
    path("api/v1/store-orders/<int:order_id>/send/", send_store_order, name="store-order-send"),
    path("admin/", admin.site.urls),
]
