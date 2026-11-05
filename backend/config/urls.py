from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from ro_core.order_template_api import kitchen_order_template

def health(_request):
    return JsonResponse({"status": "ok", "service": "ro-middleware"})

urlpatterns = [
    path("health/", health, name="health"),
    path("api/v1/order-templates/<str:kitchen_code>/", kitchen_order_template, name="kitchen-order-template"),
    path("admin/", admin.site.urls),
]
