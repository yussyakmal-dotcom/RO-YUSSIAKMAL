"""Pull warehouse/location/products/BoMs; local writes only with --apply."""
import json

from django.core.management.base import BaseCommand, CommandError

from ro_core.odoo_readonly import OdooReadOnlyClient, OdooReadError
from ro_core.odoo_master import download_master, build_preview, apply_master


class Command(BaseCommand):
    help = "Preview master sync from Odoo; use --apply to save locally."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Write imported master data to middleware PostgreSQL only."
        )

    def handle(self, *args, **options):
        try:
            client = OdooReadOnlyClient.from_env()
            snapshot = download_master(client)
            warehouses, locations, products, summary = build_preview(snapshot)
            self.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False))
            if not options["apply"]:
                self.stdout.write(self.style.WARNING(
                    "PREVIEW ONLY: tidak ada perubahan database lokal maupun Odoo. "
                    "Gunakan --apply jika hasilnya sesuai."
                ))
                return
            apply_master(warehouses, locations, products, summary)
        except OdooReadError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS(
            "Master berhasil disimpan ke PostgreSQL middleware. "
            "Odoo tidak diubah; mapping SKU ke dapur tetap dipertahankan."
        ))
