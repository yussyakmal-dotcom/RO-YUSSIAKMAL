"""Technical Django Admin for editing and uploading per-kitchen order templates."""
from io import BytesIO

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from . import models
from .order_template_excel import apply_xlsx, preview_xlsx


class UploadTemplateForm(forms.Form):
    kitchen = forms.ModelChoiceField(
        label="Dapur untuk template",
        queryset=models.Warehouse.objects.none(),
    )
    excel_file = forms.FileField(label="Excel .xlsx berisi SKU")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kitchen"].queryset = models.Warehouse.objects.filter(
            kind__in=("KITCHEN", "PACKING"), active=True
        ).order_by("name")


@admin.register(models.ProductionAssignment)
class ProductionAssignmentAdmin(admin.ModelAdmin):
    """One SKU -> one kitchen, with template active flag and order."""
    change_list_template = "admin/ro_core/productionassignment/change_list.html"
    list_display = (
        "product_sku", "product_name", "kitchen", "is_active",
        "sort_order", "updated_at",
    )
    list_filter = ("kitchen", "is_active")
    search_fields = ("product__sku", "product__name")
    ordering = ("kitchen__name", "sort_order", "product__name")
    raw_id_fields = ("product",)
    list_per_page = 100

    @admin.display(description="SKU", ordering="product__sku")
    def product_sku(self, obj):
        return obj.product.sku

    @admin.display(description="Nama produk", ordering="product__name")
    def product_name(self, obj):
        return obj.product.name

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "kitchen":
            kwargs["queryset"] = models.Warehouse.objects.filter(
                kind__in=("KITCHEN", "PACKING"), active=True,
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        # Turn off items via is_active; preserve mapping/history instead of deleting.
        return False

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            old = models.ProductionAssignment.objects.get(pk=obj.pk)
            previous = {
                "kitchen": old.kitchen_id, "active": old.is_active,
                "sort_order": old.sort_order,
            }
        super().save_model(request, obj, form, change)
        new_state = {
            "kitchen": obj.kitchen_id, "active": obj.is_active,
            "sort_order": obj.sort_order,
        }
        if previous != new_state:
            models.AuditLog.objects.create(
                actor=request.user, entity="KitchenOrderTemplate",
                entity_id=str(obj.product_id),
                action="ADMIN_EDIT",
                changes={"before": previous, "after": new_state},
            )

    def get_urls(self):
        custom = [
            path(
                "upload-excel/",
                self.admin_site.admin_view(self.upload_view),
                name="ro_core_productionassignment_upload",
            ),
            path(
                "download-template/",
                self.admin_site.admin_view(self.download_template_view),
                name="ro_core_productionassignment_download_template",
            ),
        ]
        return custom + super().get_urls()

    def _require_permission(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied

    def upload_view(self, request):
        self._require_permission(request)
        form = UploadTemplateForm(
            request.POST if request.method == "POST" else None,
            request.FILES if request.method == "POST" else None,
        )
        preview = None
        if request.method == "POST" and form.is_valid():
            try:
                preview = preview_xlsx(
                    form.cleaned_data["kitchen"], form.cleaned_data["excel_file"]
                )
                if request.POST.get("action") == "apply":
                    if not preview.is_valid:
                        messages.error(request, "Impor dibatalkan: perbaiki error Excel dahulu.")
                    else:
                        result = apply_xlsx(preview, actor=request.user)
                        messages.success(
                            request,
                            "Template tersimpan: %s SKU baru, %s diperbarui, %s tetap."
                            % (result["created"], result["updated"], result["unchanged"]),
                        )
                        return redirect(
                            reverse("admin:ro_core_productionassignment_changelist")
                        )
            except (ValueError, OSError) as exc:
                form.add_error("excel_file", str(exc))

        context = {
            **self.admin_site.each_context(request),
            "title": "Upload template pemesanan per dapur",
            "opts": self.model._meta,
            "form": form,
            "preview": preview,
        }
        return render(
            request,
            "admin/ro_core/productionassignment/upload.html",
            context,
        )

    def download_template_view(self, request):
        self._require_permission(request)
        wb = Workbook()
        sheet = wb.active
        sheet.title = "SKU Template"
        sheet.append(["SKU", "NAMA", "AKTIF", "URUTAN"])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = "A1:D1"
        for cell in sheet[1]:
            cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
            cell.fill = PatternFill(fill_type="solid", fgColor="1768AC")
            cell.alignment = Alignment(horizontal="center")
        for col, width in {"A": 25, "B": 48, "C": 20, "D": 15}.items():
            sheet.column_dimensions[col].width = width
        dropdown = DataValidation(
            type="list", formula1='"Aktif,Nonaktif"', allow_blank=True,
        )
        sheet.add_data_validation(dropdown)
        dropdown.add("C2:C5001")
        sheet["C2"] = "Aktif"
        sheet["D2"] = 1
        note = wb.create_sheet("Petunjuk")
        for row in [
            ["Kolom", "Fungsi"],
            ["SKU", "WAJIB. Internal Reference dari Odoo; formatkan sebagai teks jika ada nol di depan."],
            ["NAMA", "Opsional untuk pengecekan; tidak digunakan untuk mengubah master Odoo."],
            ["AKTIF", "Aktif / Nonaktif. Jika kosong, dianggap Aktif."],
            ["URUTAN", "Bilangan 0 atau lebih; jika kosong memakai urutan baris Excel."],
            ["PENTING", "Baris SKU yang tidak tercantum TIDAK dihapus atau dinonaktifkan."],
            ["PENTING", "Untuk menonaktifkan SKU, masukkan SKU tersebut dan pilih Nonaktif."],
            ["PENTING", "Qty pesanan tidak diisi di Excel; Qty diisi Admin Toko saat memesan."],
            ["PENTING", "Hapus contoh sel C2 dan D2 jika tidak diperlukan; isi SKU mulai A2."],
        ]:
            note.append(row)
        note.column_dimensions["A"].width = 18
        note.column_dimensions["B"].width = 105
        note["A1"].font = Font(bold=True)
        note["B1"].font = Font(bold=True)
        stream = BytesIO()
        wb.save(stream)
        response = HttpResponse(
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="RO-Template-SKU-Dapur.xlsx"'
        return response


@admin.register(models.StoreOrder)
class StoreOrderAdmin(admin.ModelAdmin):
    """Read-only order headers; status transitions belong to the order API."""
    list_display = (
        "id", "store", "kitchen", "delivery_date", "schedule",
        "status", "auto_submitted", "submitted_at",
    )
    list_filter = ("status", "auto_submitted", "delivery_date", "store", "kitchen")
    search_fields = ("=id", "store__code", "store__name", "kitchen__code")
    list_select_related = ("store", "kitchen", "schedule")
    ordering = ("-delivery_date", "-id")
    date_hierarchy = "delivery_date"
    fields = (
        "store", "kitchen", "order_date", "delivery_date", "schedule",
        "status", "auto_submitted", "submitted_at", "created_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.StoreOrderLine)
class StoreOrderLineAdmin(admin.ModelAdmin):
    """Human-readable *inspection only*: never bypass integer Qty and Kirim lock."""
    list_display = (
        "order_number", "store_name", "kitchen_name", "delivery_day",
        "delivery_slot", "sku", "product_name", "qty_units", "order_status",
    )
    list_filter = (
        "order__status", "order__store", "order__kitchen",
        "order__delivery_date",
    )
    search_fields = (
        "product__sku", "product__name", "order__store__code",
        "order__store__name", "order__kitchen__code",
    )
    ordering = ("-order__delivery_date", "order__store__code", "product__sku")
    list_per_page = 100
    fields = ("order_description", "product_description", "qty_units", "order_status")
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "order__store", "order__kitchen", "order__schedule", "product",
        )

    @admin.display(description="Order ID", ordering="order_id")
    def order_number(self, obj):
        return f"#{obj.order_id}"

    @admin.display(description="Toko", ordering="order__store__code")
    def store_name(self, obj):
        return obj.order.store.name

    @admin.display(description="Dapur", ordering="order__kitchen__code")
    def kitchen_name(self, obj):
        return obj.order.kitchen.name

    @admin.display(description="Tanggal kirim", ordering="order__delivery_date")
    def delivery_day(self, obj):
        return obj.order.delivery_date

    @admin.display(description="Jadwal", ordering="order__schedule__code")
    def delivery_slot(self, obj):
        return obj.order.schedule.name

    @admin.display(description="SKU", ordering="product__sku")
    def sku(self, obj):
        return obj.product.sku

    @admin.display(description="Nama produk", ordering="product__name")
    def product_name(self, obj):
        return obj.product.name

    @admin.display(description="Qty (unit)", ordering="qty")
    def qty_units(self, obj):
        if obj.qty == obj.qty.to_integral_value():
            return str(int(obj.qty))
        return f"{obj.qty} (perlu koreksi desimal)"

    @admin.display(description="Status", ordering="order__status")
    def order_status(self, obj):
        return obj.order.get_status_display()

    @admin.display(description="Pesanan")
    def order_description(self, obj):
        return str(obj.order)

    @admin.display(description="Produk")
    def product_description(self, obj):
        return str(obj.product)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Other models remain in technical Django Admin, not the operational frontend.
for model in (
    models.Warehouse, models.UserWarehouseAccess, models.Product,
    models.Schedule, models.ProductCapacity, models.MinStockRule,
    models.MaterialRequestLine,
    models.PackingAllocation, models.DocumentCounter, models.OdooDocument,
    models.AuditLog,
):
    admin.site.register(model)


class ReadOnlyProductionModelAdmin(admin.ModelAdmin):
    """Plan/source truth is changed only by audited production API transactions."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.ProductionPlan)
class ProductionPlanAdmin(ReadOnlyProductionModelAdmin):
    list_display = (
        "id", "kitchen", "delivery_date", "delivery_schedule",
        "production_date", "production_schedule", "status",
    )
    list_filter = ("kitchen", "delivery_date", "production_date", "status")


@admin.register(models.ProductionPlanLine)
class ProductionPlanLineAdmin(ReadOnlyProductionModelAdmin):
    list_display = (
        "id", "plan", "product", "qty_requested", "qty_planned",
        "capacity_qty", "capacity_used_before", "qty_shortfall",
    )
    list_select_related = ("plan", "product")


@admin.register(models.ProductionPlanSource)
class ProductionPlanSourceAdmin(ReadOnlyProductionModelAdmin):
    list_display = ("id", "plan", "order")
    list_select_related = ("plan", "order")
