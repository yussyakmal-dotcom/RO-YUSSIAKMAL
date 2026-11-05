"""Seed three standard delivery slots without overwriting operator changes."""
from django.core.management.base import BaseCommand
from ro_core.models import Schedule


DEFAULTS = (
    ("SUBUH", "Subuh", "Malam sebelumnya - subuh", 10),
    ("PAGI", "Pagi", "Subuh - 08:00", 20),
    ("SIANG", "Siang", "08:00 - 10:00", 30),
)


class Command(BaseCommand):
    help = "Create missing standard delivery schedule choices; never overwrite existing settings."

    def handle(self, *args, **options):
        count = 0
        for code, name, label, rank in DEFAULTS:
            _, created = Schedule.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "production_label": label,
                    "sort_order": rank,
                    "active": True,
                },
            )
            count += int(created)
        self.stdout.write(self.style.SUCCESS(
            f"Jadwal standar siap ({count} baru). Data jadwal yang sudah ada dipertahankan."
        ))
