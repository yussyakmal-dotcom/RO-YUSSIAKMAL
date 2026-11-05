"""Session login and lightweight menu metadata for the Admin Toko frontend.

All actions remain same-origin to Django /api/v1 with CSRF protection.
No OAuth, bearer token storage, or duplicate user database required for V1.
"""
import json

from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Schedule, UserWarehouseAccess, Warehouse


def _eligible(user):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=("STORE", "ADMIN")).exists()


@require_GET
@ensure_csrf_cookie
@never_cache
def csrf_cookie(request):
    return JsonResponse({"ok": True})


@require_GET
@never_cache
def session_info(request):
    if not _eligible(request.user):
        return JsonResponse({"detail": "Login sebagai Admin Toko atau Administrator diperlukan."}, status=401)
    admin = request.user.is_superuser or request.user.groups.filter(name="ADMIN").exists()
    stores = Warehouse.objects.filter(kind="STORE", active=True)
    if not admin:
        stores = stores.filter(userwarehouseaccess__user=request.user).distinct()
    kitchens = Warehouse.objects.filter(
        kind__in=("KITCHEN", "PACKING"), active=True
    ).annotate(
        item_count=Count(
            "productionassignment",
            filter=Q(
                productionassignment__is_active=True,
                productionassignment__product__active=True,
            ),
        ),
    ).order_by("name")
    schedules = Schedule.objects.filter(active=True).order_by("sort_order", "code")

    return JsonResponse({
        "user": {
            "username": request.user.get_username(),
            "full_name": request.user.get_full_name() or request.user.get_username(),
            "admin": admin,
        },
        "stores": list(stores.order_by("name").values("code", "name")),
        "kitchens": list(kitchens.values("code", "name", "item_count")),
        "schedules": list(schedules.values("code", "name")),
    })


@require_POST
@csrf_protect
@never_cache
def login_session(request):
    try:
        values = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Format login tidak valid."}, status=400)
    if not isinstance(values, dict):
        return JsonResponse({"detail": "Format login tidak valid."}, status=400)
    username, password = values.get("username"), values.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or len(username) > 150:
        return JsonResponse({"detail": "Username dan password wajib diisi."}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None or not _eligible(user):
        return JsonResponse({"detail": "Username, password, atau akses workspace tidak sesuai."}, status=401)
    login(request, user)
    return JsonResponse({"ok": True})


@require_POST
@csrf_protect
@never_cache
def logout_session(request):
    logout(request)
    return JsonResponse({"ok": True})
