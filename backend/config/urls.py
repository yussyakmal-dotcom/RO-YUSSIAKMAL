from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path
from ro_core.order_template_api import kitchen_order_template
from ro_core.store_order_api import store_order_form, send_store_order
from ro_core.store_auth import csrf_cookie, session_info, login_session, logout_session
from ro_core.production_demand_api import production_demand, recent_final_store_orders

def health(_request):
    return JsonResponse({"status": "ok", "service": "ro-middleware"})

def store_workspace(request):
    return render(request, "store_app.html")


urlpatterns = [
    path("", lambda request: redirect("store-workspace"), name="root"),
    path("toko/", store_workspace, name="store-workspace"),
    path("produksi/", store_workspace, name="production-workspace"),
    path("api/v1/production/demand/", production_demand, name="production-demand"),
    path("api/v1/production/recent-orders/", recent_final_store_orders, name="production-recent-orders"),
    path("api/v1/auth/csrf/", csrf_cookie, name="store-session-csrf"),
    path("api/v1/auth/me/", session_info, name="store-session-me"),
    path("api/v1/auth/login/", login_session, name="store-session-login"),
    path("api/v1/auth/logout/", logout_session, name="store-session-logout"),
    path("health/", health, name="health"),
    path("api/v1/order-templates/<str:kitchen_code>/", kitchen_order_template, name="kitchen-order-template"),
    path("api/v1/store-orders/", store_order_form, name="store-order-form"),
    path("api/v1/store-orders/<int:order_id>/send/", send_store_order, name="store-order-send"),
    path("admin/", admin.site.urls),
]
