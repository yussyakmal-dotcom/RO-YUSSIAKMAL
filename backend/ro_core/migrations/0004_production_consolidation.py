"""Separate delivery/production schedules and persist real consolidations.

Old plans keep a NULL production_schedule (unknown, never invented).
Legacy plans are excluded from the new partial delivery-scope unique index,
and block new consolidations for their scope until an operator reconciles them.
"""
from decimal import Decimal
from django.db import migrations, models
from django.db.models import Q
from django.core.validators import MinValueValidator
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("ro_core", "0003_store_order_production_status")]

    operations = [
        migrations.RemoveConstraint(
            model_name="productionplan", name="uq_ro_production_plan",
        ),
        migrations.RemoveIndex(
            model_name="productionplan", name="ix_ro_plan_date",
        ),
        migrations.RenameField(
            model_name="productionplan",
            old_name="schedule", new_name="delivery_schedule",
        ),
        migrations.AlterField(
            model_name="productionplan", name="delivery_schedule",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="delivery_plans", to="ro_core.schedule",
            ),
        ),
        migrations.AddField(
            model_name="productionplan", name="production_schedule",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="production_plans", to="ro_core.schedule",
            ),
        ),
        migrations.AddConstraint(
            model_name="productionplan",
            constraint=models.UniqueConstraint(
                fields=("kitchen", "delivery_date", "delivery_schedule"),
                condition=Q(production_schedule__isnull=False),
                name="uq_ro_plan_delivery_scope",
            ),
        ),
        migrations.AddIndex(
            model_name="productionplan",
            index=models.Index(
                fields=["production_date", "production_schedule"],
                name="ix_ro_plan_prod_slot",
            ),
        ),
        migrations.AlterField(
            model_name="productionplanline", name="qty_mo",
            field=models.DecimalField(
                blank=True, null=True, default=None,
                max_digits=18, decimal_places=4,
                validators=[MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AlterField(
            model_name="productionplanline", name="batch_qty",
            field=models.DecimalField(
                blank=True, null=True, default=None,
                max_digits=18, decimal_places=4,
                validators=[MinValueValidator(Decimal("0.0001"))],
            ),
        ),
        migrations.AddField(
            model_name="productionplanline", name="capacity_used_before",
            field=models.DecimalField(
                max_digits=18, decimal_places=4, default=Decimal("0"),
                validators=[MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AddField(
            model_name="productionplanline", name="qty_shortfall",
            field=models.DecimalField(
                max_digits=18, decimal_places=4, default=Decimal("0"),
                validators=[MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.CreateModel(
            name="ProductionPlanSource",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("lines_snapshot", models.JSONField(default=list)),
                ("order", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="production_source", to="ro_core.storeorder",
                )),
                ("plan", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="sources", to="ro_core.productionplan",
                )),
            ],
            options={"ordering": ["order_id"]},
        ),
    ]
