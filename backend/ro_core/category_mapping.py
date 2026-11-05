"""One-time Product Category -> production warehouse mapping.

Mappings are suggestions for INITIAL import only. Routine Odoo synchronisation
must not overwrite ProductionAssignment, even if the product category changes.
Only exact known category labels (case/space-insensitive) are eligible.
"""
from collections import Counter
from dataclasses import dataclass
from unicodedata import normalize

from django.db import transaction

from .models import AuditLog, Product, ProductionAssignment, Warehouse


# Category names are expected examples, not fuzzy matching.
# Unknown / nested categories are left for review and manual assignment.
CATEGORY_TO_WAREHOUSE = {
    "asin": "ASN",
    "cake slice": "CKS",
    "gorengan": "GRG",
    "jajan pasar": "JP",
    "pastry": "PST",
    "roti": "ROTI",
    "sultan & lemper": "SUL",
    "tart": "TART",
    "premik": "PREMI",
    "legit": "LEGIT",
    "paket": "PCK",
}


def normalized_label(category):
    """Case/whitespace normalization only; NEVER interpret a nested path."""
    return " ".join(normalize("NFKC", category or "").casefold().split())


@dataclass
class MappingPreview:
    candidates: list  # pairs (product_id, target_warehouse_code)
    summary: dict


def preview_category_mapping():
    """Read current PostgreSQL master cache without changing any records."""
    warehouses = {
        w.code: w for w in Warehouse.objects.filter(active=True)
    }
    existing_ids = set(
        ProductionAssignment.objects.values_list("product_id", flat=True)
    )

    candidates = []
    unmatched = Counter()
    mapped_categories = Counter()
    missing_targets = Counter()
    already_assigned = 0
    total = 0

    for product in Product.objects.filter(active=True).only("id", "category").iterator():
        total += 1
        if product.id in existing_ids:
            already_assigned += 1
            continue
        category = (product.category or "").strip()
        target_code = CATEGORY_TO_WAREHOUSE.get(normalized_label(category))
        if not target_code:
            unmatched[category or "(kosong)"] += 1
            continue
        target = warehouses.get(target_code)
        expected_kind = "PACKING" if target_code == "PCK" else "KITCHEN"
        if target is None or target.kind != expected_kind:
            missing_targets[target_code] += 1
            continue
        candidates.append((product.id, target_code))
        mapped_categories[f"{category} -> {target_code}"] += 1

    summary = {
        "total_active_products": total,
        "already_assigned_preserved": already_assigned,
        "new_mapping_candidates": len(candidates),
        "candidates_by_category": dict(sorted(mapped_categories.items())),
        "unmatched_products": sum(unmatched.values()),
        "unmatched_categories_top_30": dict(
            sorted(unmatched.items(), key=lambda x: (-x[1], x[0]))[:30]
        ),
        "missing_warehouse_targets": dict(sorted(missing_targets.items())),
        "note": (
            "Preview tidak menulis database. Hanya kategori yang cocok persis "
            "dengan daftar kategori dapur yang dikenali akan dipetakan."
        ),
    }
    return MappingPreview(candidates=candidates, summary=summary)


def apply_category_mapping(preview):
    """Insert missing assignments only. Existing/manual mappings never change."""
    if preview.summary["missing_warehouse_targets"]:
        raise ValueError("Warehouse tujuan tidak lengkap; mapping belum diterapkan.")

    created = 0
    # Unique OneToOne constraint additionally protects against concurrent runs.
    with transaction.atomic():
        warehouses = {
            w.code: w
            for w in Warehouse.objects.filter(active=True).select_for_update()
        }
        for product_id, code in preview.candidates:
            warehouse = warehouses.get(code)
            if warehouse is None:
                raise ValueError(f"Warehouse {code} tidak ada saat apply.")
            _, was_created = ProductionAssignment.objects.get_or_create(
                product_id=product_id,
                defaults={"kitchen": warehouse},
            )
            if was_created:
                created += 1
        if created:
            AuditLog.objects.create(
                entity="ProductionAssignment",
                entity_id="initial-category-import",
                action="INITIAL_IMPORT",
                changes={"created": created, "existing_preserved": preview.summary["already_assigned_preserved"]},
            )
    return created
