"""Retired unsafe category-based initial mapping command.

Product Category is not the source of MO production routing in this tenant.
MO Operation Type (mrp.production.picking_type_id) determines production
warehouse. Do not infer assignments from a category name.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "DISABLED: category-based SKU kitchen assignment was an incorrect assumption."

    def add_arguments(self, parser):
        # Keep the flag to intercept old copy/pasted --apply commands safely.
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        raise CommandError(
            "DINONAKTIFKAN: Product Category BUKAN penentu dapur produksi. "
            "Odoo menentukan jalur MO melalui Operation Type (picking_type_id). "
            "Perintah ini tidak akan membuat atau mengubah mapping. "
            "Gunakan 'python manage.py odoo_mo_operation_types' untuk "
            "memeriksa operation type manufaktur Odoo secara READ-ONLY."
        )
