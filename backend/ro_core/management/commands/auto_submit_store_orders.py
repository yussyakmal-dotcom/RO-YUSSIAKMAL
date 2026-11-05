"""Preview or apply daily 07:00 WIB H-2 Draft cutoff."""
import json

from django.core.management.base import BaseCommand, CommandError

from ro_core.auto_submit import BeforeCutoffError, auto_submit_drafts


class Command(BaseCommand):
    help = (
        "Auto-submit existing store Drafts for delivery H+2 at/after 07:00 WIB. "
        "Default is PREVIEW (read-only); --apply finalizes and locks Drafts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Finalize today's eligible H-2 Drafts (middleware database only)."
        )

    def handle(self, *args, **options):
        try:
            result = auto_submit_drafts(apply=options["apply"])
        except BeforeCutoffError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps(result, indent=2, ensure_ascii=False))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "PREVIEW SAJA: tidak ada perubahan data. "
                "Penerapan memerlukan --apply dan waktu sudah >= 07:00 WIB."
            ))
        else:
            if result["invalid_drafts"]:
                raise CommandError(
                    f"{result['invalid_drafts']} Draft memiliki Qty tidak valid dan "
                    "sengaja TIDAK dikirim. Periksa invalid_order_ids dari output "
                    "JSON lalu koreksi Qty secara manual."
                )
            self.stdout.write(self.style.SUCCESS(
                "Auto-submit H-2 selesai. Hanya Draft eligible yang berubah; "
                "Odoo tidak diubah."
            ))
