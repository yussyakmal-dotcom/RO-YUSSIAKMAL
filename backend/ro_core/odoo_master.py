"""Import Odoo master data into middleware, never write to Odoo.

Remote data is fetched completely before starting any local database write.
ProductionAssignment (SKU -> kitchen) is intentionally never modified.
"""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import AuditLog, Product, Warehouse
from .odoo_readonly import OdooReadError


# Confirmed warehouse and stock location names from the PRD.
WAREHOUSE_CONFIG = {
    "CDC": ("CENTRAL", "CDC/Stock"),
    "PCK": ("PACKING", "PCK/Packing"),
    "ASN": ("KITCHEN", "ASN/Stock"),
    "CKS": ("KITCHEN", "CKS/Stock"),
    "GRG": ("KITCHEN", "GRG/Stock"),
    "JP": ("KITCHEN", "JP/Stock"),
    "PST": ("KITCHEN", "PST/Stock"),
    "ROTI": ("KITCHEN", "ROTI/Stock"),
    "SUL": ("KITCHEN", "SUL/Stock"),
    "TART": ("KITCHEN", "TART/Stock"),
    "PREMI": ("KITCHEN", "PREMI/Stock"),
    "LEGIT": ("KITCHEN", "LEGIT/Stock"),
    "T_BAN": ("STORE", "T_BAN/Stock"),
    "T_SD": ("STORE", "T_SD/Stock"),
    "T_KD": ("STORE", "T_KD/Stock"),
    "T_MET": ("STORE", "T_MET/Stock"),
    "T_UNI": ("STORE", "T_UNI/Stock"),
    "T_RSA": ("STORE", "T_RSA/Stock"),
    "T_AR": ("STORE", "T_AR/Stock"),
}


def relation_id(value):
    if isinstance(value, (list, tuple)) and value and type(value[0]) is int:
        return value[0]
    return None


def relation_name(value):
    return str(value[1]) if isinstance(value, (list, tuple)) and len(value) > 1 else ""


def decimal_or_none(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (TypeError, ValueError, InvalidOperation):
        return None


@dataclass
class MasterSnapshot:
    warehouses: list
    locations: list
    products: list
    boms: list
    bom_lines: list


def download_master(client):
    """Read only: five Odoo models via JSON-2 search_read."""
    warehouses = list(client.all_records(
        "stock.warehouse", ["id", "code", "name", "lot_stock_id"]
    ))
    locations = list(client.all_records(
        "stock.location", ["id", "complete_name"],
        domain=[["complete_name", "in", [x[1] for x in WAREHOUSE_CONFIG.values()]]],
    ))
    products = list(client.all_records(
        "product.product",
        ["id", "default_code", "name", "categ_id", "uom_id", "product_tmpl_id"],
        domain=[["active", "=", True]],
    ))
    boms = list(client.all_records(
        "mrp.bom",
        ["id", "product_id", "product_tmpl_id", "product_qty", "product_uom_id", "type"],
        domain=[["active", "=", True]],
    ))
    bom_lines = []
    # Keep request size bounded even for thousands of BoMs.
    ids = [b["id"] for b in boms]
    for i in range(0, len(ids), 150):
        bom_lines.extend(client.all_records(
            "mrp.bom.line",
            ["id", "bom_id", "product_id", "product_qty", "product_uom_id"],
            domain=[["bom_id", "in", ids[i:i + 150]]],
        ))
    return MasterSnapshot(warehouses, locations, products, boms, bom_lines)


def build_preview(snapshot):
    """Build normalized dictionaries, detect ambiguity; no DB access."""
    matched_warehouses = {}
    for item in snapshot.warehouses:
        code = (item.get("code") or "").strip().upper()
        if code not in WAREHOUSE_CONFIG:
            continue
        if code in matched_warehouses:
            raise OdooReadError(f"Duplikat warehouse code di Odoo: {code}")
        matched_warehouses[code] = item
    if not matched_warehouses:
        raise OdooReadError(
            "Tidak ada kode warehouse RO yang cocok; periksa database Odoo"
        )

    locations = {}
    for item in snapshot.locations:
        location_name = item.get("complete_name")
        if location_name:
            locations[location_name] = item["id"]

    by_variant, by_template, lines_by_bom = defaultdict(list), defaultdict(list), defaultdict(list)
    for bom in snapshot.boms:
        if bom.get("type", "normal") != "normal":
            continue  # Phantom BoM/kit is not a manufacturing MO.
        pid, tid = relation_id(bom.get("product_id")), relation_id(bom.get("product_tmpl_id"))
        if pid is not None:
            by_variant[pid].append(bom)
        elif tid is not None:
            by_template[tid].append(bom)
    for line in snapshot.bom_lines:
        bid = relation_id(line.get("bom_id"))
        if bid is not None:
            lines_by_bom[bid].append(line)

    prepared_products = []
    ambiguous = []
    for p in snapshot.products:
        pid = p["id"]
        tid = relation_id(p.get("product_tmpl_id"))
        candidates = by_variant.get(pid) or by_template.get(tid, [])
        if len(candidates) > 1:
            ambiguous.append({"odoo_product_id": pid, "sku": p.get("default_code") or ""})
            bom_patch = None  # Preserve existing local BoM cache; warn operator.
        elif candidates:
            bom = candidates[0]
            output = decimal_or_none(bom.get("product_qty"))
            if output is None or output <= 0:
                ambiguous.append({"odoo_product_id": pid, "sku": p.get("default_code") or ""})
                bom_patch = None
            else:
                bom_patch = {
                    "bom_odoo_id": bom["id"],
                    "bom_output_qty": output,
                    "bom_components": [
                        {
                            "odoo_product_id": relation_id(line.get("product_id")),
                            "qty": str(decimal_or_none(line.get("product_qty")) or Decimal("0")),
                            "uom": relation_name(line.get("product_uom_id")),
                        }
                        for line in lines_by_bom.get(bom["id"], [])
                        if relation_id(line.get("product_id")) is not None
                    ],
                }
        else:
            bom_patch = {
                "bom_odoo_id": None, "bom_output_qty": None, "bom_components": []
            }

        prepared_products.append({
            "odoo_id": pid,
            "sku": (p.get("default_code") or "").strip(),
            "name": (p.get("name") or "").strip() or f"Product #{pid}",
            "category": relation_name(p.get("categ_id")),
            "uom": relation_name(p.get("uom_id")),
            "bom_patch": bom_patch,
        })

    expected_locations = {
        code: location for code, (_kind, location) in WAREHOUSE_CONFIG.items()
        if code in matched_warehouses
    }
    summary = {
        "warehouses": len(matched_warehouses),
        "missing_warehouses": sorted(set(WAREHOUSE_CONFIG) - set(matched_warehouses)),
        "location_matches": sum(1 for loc in expected_locations.values() if loc in locations),
        "missing_locations": [loc for loc in expected_locations.values() if loc not in locations],
        "products": len(prepared_products),
        "boms": len(snapshot.boms),
        "ambiguous_products": len(ambiguous),
        "ambiguous_examples": ambiguous[:10],
    }
    return matched_warehouses, locations, prepared_products, summary


@transaction.atomic
def apply_master(matched_warehouses, locations, prepared_products, summary):
    """Atomic local import. Never touches ProductionAssignment or remote Odoo."""
    for code, row in matched_warehouses.items():
        kind, expected_location = WAREHOUSE_CONFIG[code]
        defaults = {
            "code": code,
            "name": row["name"],
            "kind": kind,
            "active": True,
        }
        if expected_location in locations:
            defaults["stock_location_odoo_id"] = locations[expected_location]
        Warehouse.objects.update_or_create(odoo_id=row["id"], defaults=defaults)

    now = timezone.now()
    for row in prepared_products:
        defaults = {
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "uom": row["uom"],
            "active": True,
            "synced_at": now,
        }
        if row["bom_patch"] is not None:
            defaults.update(row["bom_patch"])
        Product.objects.update_or_create(odoo_id=row["odoo_id"], defaults=defaults)
    AuditLog.objects.create(
        entity="OdooMaster",
        entity_id="master-sync",
        action="APPLY",
        changes={key: value for key, value in summary.items() if key != "ambiguous_examples"},
    )
    return summary
