"""Check Odoo external JSON-2 access without changing any data."""
from django.core.management.base import BaseCommand, CommandError

from ro_core.odoo_readonly import OdooReadOnlyClient, OdooReadError


class Command(BaseCommand):
    help = "Test Odoo API key using read-only search_read of one warehouse."

    def handle(self, *args, **options):
        try:
            client = OdooReadOnlyClient.from_env()
            result = client.search_read(
                "stock.warehouse", ["id", "code", "name"], limit=1
            )
        except OdooReadError as exc:
            raise CommandError(str(exc)) from None

        self.stdout.write(self.style.SUCCESS("Koneksi JSON-2 Odoo berhasil (READ-ONLY)."))
        if result:
            self.stdout.write(
                f"Contoh warehouse: {result[0].get('code', '-')}"
            )
        else:
            self.stdout.write(
                "Koneksi berhasil, tetapi pengguna API tidak melihat warehouse."
            )
