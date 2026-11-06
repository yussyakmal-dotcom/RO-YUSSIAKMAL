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

from .models import AuditLog, Product, ProductCapacity, ProductionAssignment, Schedule, Warehouse

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
    schedule_columns: list

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


MAX_CAPACITY = 99999999999999  # DecimalField(18,4), displayed as integer.


def _capacity_qty(value):
    """Whole Qty only, no decimal/ribuan ambiguity or Excel formulas."""
    if value is None or str(value).strip() == "":
        return None  # Empty = preserve master value; NOT zero.
    if isinstance(value, bool):
        raise ValueError("Kapasitas wajib bilangan bulat, bukan TRUE/FALSE")
    if isinstance(value, int):
        result = value
    elif isinstance(value, float) and value.is_integer():
        result = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value.strip())
    else:
        raise ValueError("Kapasitas wajib angka bulat tanpa titik/koma/desimal")
    if result < 0 or result > MAX_CAPACITY:
        raise ValueError("Kapasitas di luar batas 0 sampai 99999999999999")
    return result


def _display_capacity(value):
    if value is None:
        return "Belum diatur"
    if isinstance(value, int):
        return str(value)
    if value != value.to_integral_value():
        return "Perlu koreksi Qty"
    return str(int(value))


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

    schedules = list(Schedule.objects.filter(active=True).order_by(
        "sort_order", "code",
    ))
    allowed_schedules = {schedule.code.upper(): schedule for schedule in schedules}

    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=False)
        worksheet = workbook.active
        if worksheet.max_row and worksheet.max_row > MAX_ROWS + 1:
            raise ValueError("Maksimal 5000 SKU per file.")
        header = next(worksheet.iter_rows(min_row=1, max_row=1), None)
        if not header:
            raise ValueError("File Excel kosong.")
        indices = {}
        capacity_headers = {}
        for idx, cell in enumerate(header):
            title = str(cell.value or "").strip().upper()
            if title in {"SKU", "INTERNAL REFERENCE"}:
                if "SKU" in indices:
                    raise ValueError("Kolom SKU tidak boleh berulang.")
                indices["SKU"] = idx
            elif title in {"AKTIF", "URUTAN", "NAMA"}:
                if title in indices:
                    raise ValueError(f"Kolom {title} tidak boleh berulang.")
                indices[title] = idx
            elif title.startswith("KAPASITAS_"):
                code = title.removeprefix("KAPASITAS_")
                if code not in allowed_schedules:
                    raise ValueError(
                        f"Kolom {title} bukan jadwal produksi aktif. "
                        "Unduh format terbaru."
                    )
                schedule = allowed_schedules[code]
                if schedule.pk in capacity_headers:
                    raise ValueError(f"Kolom {title} tidak boleh berulang.")
                capacity_headers[schedule.pk] = idx
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
                capacities = {}
                for schedule in schedules:
                    idx = capacity_headers.get(schedule.pk)
                    if idx is None or idx >= len(cells):
                        continue
                    cell = cells[idx]
                    if cell.data_type == "f":
                        raise ValueError(
                            f"Kapasitas {schedule.code} tidak boleh rumus Excel"
                        )
                    value = _capacity_qty(cell.value)
                    if value is not None:
                        capacities[schedule.pk] = value
                if sku in seen:
                    raise ValueError(f"SKU {sku} duplikat dalam Excel")
                seen.add(sku)
                extracted.append({
                    "row_number": excel_row_num, "sku": sku,
                    "is_active": active, "sort_order": order,
                    "capacities": capacities,
                })
            except ValueError as exc:
                errors.append(f"Baris {excel_row_num}: {exc}")
        workbook.close()
    except (InvalidFileException, BadZipFile, OSError, ValueError) as exc:
        if isinstance(exc, ValueError) and (
            str(exc).startswith("File Excel") or str(exc).startswith("Kolom SKU")
            or str(exc).startswith("Maksimal")
            or str(exc).startswith("Kolom KAPASITAS")
            or str(exc).startswith("Kolom AKTIF")
            or str(exc).startswith("Kolom URUTAN")
            or str(exc).startswith("Kolom NAMA")
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
    old_capacities = {
        (cap.product_id, cap.schedule_id): cap.max_qty
        for cap in ProductCapacity.objects.filter(
            product_id__in=ids,
            schedule_id__in=[schedule.pk for schedule in schedules],
        )
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
        row["uom"] = product.uom.strip() or "pcs"
        capacity_changed = any(
            old_capacities.get((product.id, schedule_id)) != value
            for schedule_id, value in row["capacities"].items()
        )
        row["capacity_cells"] = [
            _display_capacity(
                row["capacities"].get(
                    schedule.pk, old_capacities.get((product.id, schedule.pk)),
                )
            )
            for schedule in schedules
        ]
        if current is None:
            row["action"] = "BARU"
            new_count += 1
        elif (
            current.is_active != row["is_active"] or
            current.sort_order != row["sort_order"] or capacity_changed
        ):
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
        schedule_columns=schedules,
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
            template_changed = (
                not was_created and
                (assignment.is_active != row["is_active"] or
                 assignment.sort_order != row["sort_order"])
            )
            before = {
                "active": assignment.is_active, "order": assignment.sort_order,
            } if template_changed else None
            if template_changed:
                assignment.is_active = row["is_active"]
                assignment.sort_order = row["sort_order"]
                assignment.save(update_fields=["is_active", "sort_order", "updated_at"])

            capacity_changes = []
            for schedule_id, qty in sorted(row["capacities"].items()):
                previous_capacity = ProductCapacity.objects.select_for_update().filter(
                    product_id=product.pk, schedule_id=schedule_id,
                ).first()
                old_qty = (
                    previous_capacity.max_qty if previous_capacity else None
                )
                if old_qty is not None and old_qty == qty:
                    continue
                ProductCapacity.objects.update_or_create(
                    product=product, schedule_id=schedule_id,
                    defaults={"max_qty": qty},
                )
                schedule = Schedule.objects.get(pk=schedule_id)
                capacity_changes.append({
                    "schedule": schedule.code,
                    "before": int(old_qty) if old_qty is not None and
                        old_qty == old_qty.to_integral_value() else None,
                    "after": qty,
                })

            if was_created:
                created += 1
            elif template_changed or capacity_changes:
                updated += 1
            if was_created or template_changed or capacity_changes:
                changes.append({
                    "sku": product.sku,
                    "operation": "CREATE" if was_created else "UPDATE",
                    "before": before,
                    "after": {
                        "active": row["is_active"],
                        "order": row["sort_order"],
                    },
                    "capacity_changes": capacity_changes,
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
