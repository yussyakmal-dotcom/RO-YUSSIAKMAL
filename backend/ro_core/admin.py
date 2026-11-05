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


# Other models remain in technical Django Admin, not the operational frontend.
for model in (
    models.Warehouse, models.UserWarehouseAccess, models.Product,
    models.Schedule, models.ProductCapacity, models.MinStockRule,
    models.StoreOrder, models.StoreOrderLine, models.ProductionPlan,
    models.ProductionPlanLine, models.MaterialRequestLine,
    models.PackingAllocation, models.DocumentCounter, models.OdooDocument,
    models.AuditLog,
):
    admin.site.register(model)
