"""Inspect Manufacturing Operation Types from Odoo, without DB writes.

This is the first step to link middleware kitchens with Odoo
mrp.production.picking_type_id. Never infer production kitchen from Product
Category or blindly overwrite ProductionAssignment.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from ro_core.odoo_readonly import OdooReadError, OdooReadOnlyClient


class Command(BaseCommand):
    help = "List Odoo Manufacturing Operation Types (READ-ONLY)."

    def handle(self, *args, **options):
        try:
            client = OdooReadOnlyClient.from_env()
            records = list(client.all_records(
                "stock.picking.type",
                ["id", "name", "code", "warehouse_id",
                 "default_location_src_id", "default_location_dest_id"],
                domain=[["code", "=", "mrp_operation"]],
            ))
        except OdooReadError as exc:
            raise CommandError(str(exc)) from None

        result = []
        for row in records:
            warehouse = row.get("warehouse_id")
            source = row.get("default_location_src_id")
            dest = row.get("default_location_dest_id")
            result.append({
                "odoo_operation_type_id": row["id"],
                "name": row.get("name") or "",
                "warehouse_id": warehouse[0] if isinstance(warehouse, (list, tuple)) else None,
                "warehouse_name": warehouse[1] if isinstance(warehouse, (list, tuple)) and len(warehouse) > 1 else None,
                "source_location": source[1] if isinstance(source, (list, tuple)) and len(source) > 1 else None,
                "destination_location": dest[1] if isinstance(dest, (list, tuple)) and len(dest) > 1 else None,
            })
        self.stdout.write(json.dumps(
            {"count": len(result), "operation_types": result},
            ensure_ascii=False, indent=2,
        ))
        self.stdout.write(self.style.SUCCESS(
            "READ-ONLY. Tidak ada perubahan Odoo atau PostgreSQL middleware."
        ))
