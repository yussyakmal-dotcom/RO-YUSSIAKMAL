"""Save incomplete production planning without changing StoreOrder status."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ro_core", "0004_production_consolidation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductionConsolidationDraft",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID",
                )),
                ("delivery_date", models.DateField()),
                ("production_date", models.DateField(
                    blank=True, null=True,
                )),
                ("source_order_ids", models.JSONField(default=list)),
                ("planned_items", models.JSONField(default=list)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("delivery_schedule", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="consolidation_drafts", to="ro_core.schedule",
                )),
                ("kitchen", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="consolidation_drafts", to="ro_core.warehouse",
                )),
                ("production_schedule", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="draft_production_slots", to="ro_core.schedule",
                )),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="production_drafts_updated",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="productionconsolidationdraft",
            constraint=models.UniqueConstraint(
                fields=("kitchen", "delivery_date", "delivery_schedule"),
                name="uq_ro_consolidation_draft_scope",
            ),
        ),
        migrations.AddIndex(
            model_name="productionconsolidationdraft",
            index=models.Index(
                fields=["updated_at"], name="ix_ro_draft_updated",
            ),
        ),
    ]
