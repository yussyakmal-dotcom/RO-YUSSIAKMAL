"""Initial SKU -> kitchen mapping from cached Odoo Product Category.

Default: preview only. --apply writes local PostgreSQL mapping once and
never updates an existing ProductionAssignment.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from ro_core.category_mapping import (
    CATEGORY_TO_WAREHOUSE, apply_category_mapping, preview_category_mapping,
)


class Command(BaseCommand):
    help = "Preview initial mapping from product category; --apply inserts missing mappings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Insert NEW SKU-to-kitchen mappings into middleware only.",
        )

    def handle(self, *args, **options):
        preview = preview_category_mapping()
        self.stdout.write(json.dumps(preview.summary, indent=2, ensure_ascii=False))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "PREVIEW: tidak ada perubahan. Periksa kategori dan jumlahnya; "
                "gunakan --apply hanya setelah hasil sesuai."
            ))
            return

        if preview.summary["missing_warehouse_targets"]:
            raise CommandError(
                "Ada warehouse tujuan yang tidak ditemukan / jenisnya berbeda. "
                "Perbaiki sebelum menjalankan --apply."
            )
        if not preview.candidates:
            self.stdout.write("Tidak ada SKU baru untuk dipetakan.")
            return
        try:
            created = apply_category_mapping(preview)
        except ValueError as exc:
            raise CommandError(str(exc)) from None

        self.stdout.write(self.style.SUCCESS(
            f"Berhasil membuat {created} mapping baru di PostgreSQL middleware. "
            "Mapping lama tetap dipertahankan; Odoo tidak diubah."
        ))
