"""Excel-driven order templates, maintained entirely in RO Middleware.

A kitchen's list of ProductionAssignment records IS its order template.
Products and their names still come from Odoo; template visibility/order are
owned by middleware. Missing Excel rows are deliberately not removed.
"""
from dataclasses import dataclass
from io import BytesIO
from zipfile import BadZipFile

from django.db import transaction
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .models import AuditLog, Product, ProductionAssignment, Warehouse

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_SORT_ORDER = 1000000


@dataclass
class TemplatePreview:
    kitchen: Warehouse
    rows: list
    errors: list
    new_count: int
    update_count: int
    unchanged_count: int

    @property
    def is_valid(self):
        return not self.errors

    @property
    def total(self):
        return len(self.rows)


def _sku(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        raise ValueError("SKU tidak boleh bernilai boolean")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("SKU angka desimal tidak valid")
        return str(int(value))
    return str(value).strip()


def _active(value):
    if value is None or str(value).strip() == "":
        return True
    if isinstance(value, bool):
        return value
    value = str(value).strip().casefold()
    if value in {"aktif", "active", "ya", "yes", "true", "1"}:
        return True
    if value in {"nonaktif", "non aktif", "inactive", "tidak", "no", "false", "0"}:
        return False
    raise ValueError("AKTIF harus Aktif atau Nonaktif")


def _sort_order(value, default):
    if value is None or str(value).strip() == "":
        return default
    if isinstance(value, bool):
        raise ValueError("URUTAN harus bilangan bulat")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("URUTAN harus bilangan bulat") from None
    if str(value).strip().replace(".0", "") != str(result):
        raise ValueError("URUTAN harus bilangan bulat")
    if result < 0 or result > MAX_SORT_ORDER:
        raise ValueError("URUTAN harus antara 0 dan 1000000")
    return result


def preview_xlsx(kitchen, file_obj):
    """Return validation results without any database writes."""
    if kitchen.kind not in ("KITCHEN", "PACKING") or not kitchen.active:
        raise ValueError("Template hanya untuk dapur produksi atau Packing aktif.")
    filename = getattr(file_obj, "name", "") or ""
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("Gunakan Excel .xlsx, bukan .xls atau file lain.")
    if getattr(file_obj, "size", 0) > MAX_UPLOAD_BYTES:
        raise ValueError("File Excel terlalu besar (maksimum 5 MB).")
    content = file_obj.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File Excel terlalu besar (maksimum 5 MB).")

    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=False)
        worksheet = workbook.active
        if worksheet.max_row and worksheet.max_row > MAX_ROWS + 1:
            raise ValueError("Maksimal 5000 SKU per file.")
        header = next(worksheet.iter_rows(min_row=1, max_row=1), None)
        if not header:
            raise ValueError("File Excel kosong.")
        indices = {}
        for idx, cell in enumerate(header):
            title = str(cell.value or "").strip().upper()
            if title in {"SKU", "INTERNAL REFERENCE"}:
                indices["SKU"] = idx
            elif title in {"AKTIF", "URUTAN", "NAMA"}:
                indices[title] = idx
        if "SKU" not in indices:
            raise ValueError("Kolom SKU wajib ada di baris pertama.")
        extracted, errors, seen = [], [], set()
        for excel_row_num, cells in enumerate(
            worksheet.iter_rows(min_row=2), start=2
        ):
            if excel_row_num > MAX_ROWS + 1:
                raise ValueError("Maksimal 5000 SKU per file.")
            pick = lambda name: cells[indices[name]] if name in indices and indices[name] < len(cells) else None
            sku_cell = pick("SKU")
            if sku_cell is None or sku_cell.value is None or str(sku_cell.value).strip() == "":
                continue
            if sku_cell.data_type == "f":
                errors.append(f"Baris {excel_row_num}: SKU tidak boleh rumus Excel.")
                continue
            try:
                sku = _sku(sku_cell.value)
                active_cell = pick("AKTIF")
                order_cell = pick("URUTAN")
                if any(cell is not None and cell.data_type == "f" for cell in (active_cell, order_cell)):
                    raise ValueError("Rumus Excel tidak diizinkan")
                active = _active(active_cell.value if active_cell else None)
                order = _sort_order(order_cell.value if order_cell else None, excel_row_num - 2)
                if sku in seen:
                    raise ValueError(f"SKU {sku} duplikat dalam Excel")
                seen.add(sku)
                extracted.append({
                    "row_number": excel_row_num, "sku": sku,
                    "is_active": active, "sort_order": order,
                })
            except ValueError as exc:
                errors.append(f"Baris {excel_row_num}: {exc}")
        workbook.close()
    except (InvalidFileException, BadZipFile, OSError, ValueError) as exc:
        if isinstance(exc, ValueError) and (
            str(exc).startswith("File Excel") or str(exc).startswith("Kolom SKU")
            or str(exc).startswith("Maksimal")
        ):
            raise
        if isinstance(exc, (OSError, InvalidFileException, BadZipFile)):
            raise ValueError("File bukan Excel .xlsx yang valid.") from None
        raise

    skus = {row["sku"] for row in extracted}
    products_by_sku = {}
    for product in Product.objects.filter(sku__in=skus):
        products_by_sku.setdefault(product.sku, []).append(product)
    ids = [p.id for products in products_by_sku.values() for p in products]
    existing = {
        record.product_id: record
        for record in ProductionAssignment.objects.filter(product_id__in=ids)
    }

    new_count = update_count = unchanged_count = 0
    for row in extracted:
        possibilities = products_by_sku.get(row["sku"], [])
        if len(possibilities) == 0:
            errors.append(f"Baris {row['row_number']}: SKU {row['sku']} tidak ada di master Odoo.")
            continue
        if len(possibilities) > 1:
            errors.append(f"Baris {row['row_number']}: SKU {row['sku']} tidak unik di master Odoo.")
            continue
        product = possibilities[0]
        if not product.active:
            errors.append(f"Baris {row['row_number']}: SKU {row['sku']} nonaktif di master Odoo.")
            continue
        current = existing.get(product.id)
        if current and current.kitchen_id != kitchen.id:
            errors.append(
                f"Baris {row['row_number']}: SKU {row['sku']} sudah ditugaskan "
                "ke dapur lain; ubah secara manual di Administrator."
            )
            continue
        row["product_id"] = product.id
        row["name"] = product.name
        if current is None:
            row["action"] = "BARU"
            new_count += 1
        elif current.is_active != row["is_active"] or current.sort_order != row["sort_order"]:
            row["action"] = "UBAH"
            update_count += 1
        else:
            row["action"] = "SAMA"
            unchanged_count += 1

    if not extracted:
        errors.append("File tidak memiliki SKU untuk diimpor.")
    return TemplatePreview(
        kitchen=kitchen,
        rows=extracted,
        errors=errors,
        new_count=new_count,
        update_count=update_count,
        unchanged_count=unchanged_count,
    )


def apply_xlsx(preview, actor=None):
    """Upsert only the rows from the file, never delete absent products."""
    if not preview.is_valid:
        raise ValueError("Preview mengandung kesalahan; import dibatalkan.")
    created = updated = 0
    changes = []
    with transaction.atomic():
        product_ids = sorted(r["product_id"] for r in preview.rows)
        locked = {
            p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
        }
        if len(locked) != len(product_ids):
            raise ValueError("Master SKU berubah, jalankan preview ulang.")
        kitchen = Warehouse.objects.select_for_update().get(pk=preview.kitchen.pk)
        if kitchen.kind not in ("KITCHEN", "PACKING") or not kitchen.active:
            raise ValueError("Dapur tidak aktif atau bukan dapur produksi.")

        for row in preview.rows:
            product = locked[row["product_id"]]
            if not product.active or product.sku != row["sku"]:
                raise ValueError("Master SKU berubah, jalankan preview ulang.")
            assignment, was_created = ProductionAssignment.objects.get_or_create(
                product=product, defaults={
                    "kitchen": kitchen,
                    "is_active": row["is_active"],
                    "sort_order": row["sort_order"],
                },
            )
            if assignment.kitchen_id != kitchen.id:
                raise ValueError("SKU sudah menjadi milik dapur lain.")
            if was_created:
                created += 1
                changes.append({"sku": product.sku, "operation": "CREATE"})
            elif assignment.is_active != row["is_active"] or assignment.sort_order != row["sort_order"]:
                before = {"active": assignment.is_active, "order": assignment.sort_order}
                assignment.is_active, assignment.sort_order = row["is_active"], row["sort_order"]
                assignment.save(update_fields=["is_active", "sort_order", "updated_at"])
                updated += 1
                changes.append({
                    "sku": product.sku, "operation": "UPDATE", "before": before,
                    "after": {"active": row["is_active"], "order": row["sort_order"]},
                })
        if changes:
            AuditLog.objects.create(
                actor=actor,
                entity="KitchenOrderTemplate",
                entity_id=str(kitchen.id),
                action="XLSX_IMPORT",
                changes={"created": created, "updated": updated, "details": changes},
            )
    return {"created": created, "updated": updated, "unchanged": preview.unchanged_count}
