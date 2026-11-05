# Initial migration for RO Middleware V1 (review against Django makemigrations)
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("odoo_id", models.BigIntegerField(unique=True)),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("kind", models.CharField(choices=[("CENTRAL", "Central"), ("KITCHEN", "Kitchen"), ("PACKING", "Packing"), ("STORE", "Store")], max_length=16)),
                ("stock_location_odoo_id", models.BigIntegerField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("odoo_id", models.BigIntegerField(unique=True)),
                ("sku", models.CharField(blank=True, default="", max_length=100)),
                ("name", models.CharField(max_length=255)),
                ("category", models.CharField(blank=True, default="", max_length=100)),
                ("uom", models.CharField(blank=True, default="", max_length=40)),
                ("bom_odoo_id", models.BigIntegerField(blank=True, null=True)),
                ("bom_output_qty", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True, validators=[MinValueValidator(Decimal("0.0001"))])),
                ("bom_components", models.JSONField(blank=True, default=list)),
                ("active", models.BooleanField(default=True)),
                ("synced_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Schedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("production_label", models.CharField(blank=True, default="", max_length=120)),
                ("sort_order", models.IntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="UserWarehouseAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="ro_core.warehouse")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("user", "warehouse"), name="uq_ro_user_warehouse")],
            },
        ),
        migrations.CreateModel(
            name="ProductionAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='ro_core.product')),
                ("kitchen", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.warehouse")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ProductCapacity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.product")),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.schedule")),
                ("max_qty", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("product", "schedule"), name="uq_ro_sku_capacity"), models.CheckConstraint(condition=models.Q(max_qty__gte=0), name="ck_ro_capacity_nonnegative")],
            },
        ),
        migrations.CreateModel(
            name="MinStockRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.product")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.warehouse")),
                ("min_qty", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("product", "warehouse"), name="uq_ro_min_stock")],
            },
        ),
        migrations.CreateModel(
            name="StoreOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="store_orders", to="ro_core.warehouse")),
                ("kitchen", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="kitchen_orders", to="ro_core.warehouse")),
                ("order_date", models.DateField()),
                ("delivery_date", models.DateField()),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.schedule")),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("KIRIM", "Kirim"), ("NO_ORDER", "No Order")], default="DRAFT", max_length=12)),
                ("auto_submitted", models.BooleanField(default=False)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("store", "kitchen", "delivery_date", "schedule"), name="uq_ro_store_order")],
                "indexes": [models.Index(fields=["delivery_date", "status"], name="ix_ro_order_date")],
            },
        ),
        migrations.CreateModel(
            name="StoreOrderLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="ro_core.storeorder")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.product")),
                ("qty", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("order", "product"), name="uq_ro_store_order_line")],
            },
        ),
        migrations.CreateModel(
            name="ProductionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kitchen", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.warehouse")),
                ("production_date", models.DateField()),
                ("delivery_date", models.DateField()),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.schedule")),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("READY", "Ready"), ("SENT", "Sent"), ("PARTIAL", "Partial")], default="DRAFT", max_length=12)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("kitchen", "production_date", "delivery_date", "schedule"), name="uq_ro_production_plan")],
                "indexes": [models.Index(fields=["production_date", "schedule"], name="ix_ro_plan_date")],
            },
        ),
        migrations.CreateModel(
            name="ProductionPlanLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="ro_core.productionplan")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.product")),
                ("qty_requested", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
                ("qty_planned", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
                ("qty_mo", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
                ("batch_qty", models.DecimalField(decimal_places=4, max_digits=18, validators=[MinValueValidator(Decimal("0.0001"))])),
                ("capacity_qty", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
                ("bom_snapshot", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("plan", "product"), name="uq_ro_plan_line"), models.CheckConstraint(condition=models.Q(qty_mo__lte=models.F("capacity_qty")), name="ck_ro_mo_within_capacity"), models.CheckConstraint(condition=models.Q(batch_qty__gt=0), name="ck_ro_batch_positive")],
            },
        ),
        migrations.CreateModel(
            name="MaterialRequestLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="material_lines", to="ro_core.productionplan")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.product")),
                ("gross_qty", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
                ("stock_qty", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18)),
                ("minimum_qty", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
                ("buffer_qty", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("plan", "product"), name="uq_ro_material_line")],
            },
        ),
        migrations.CreateModel(
            name="PackingAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("delivery_date", models.DateField()),
                ("schedule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.schedule")),
                ("store", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.warehouse")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.product")),
                ("qty_requested", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
                ("qty_allocated", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18, validators=[MinValueValidator(Decimal("0"))])),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("delivery_date", "schedule", "store", "product"), name="uq_ro_packing_allocation")],
            },
        ),
        migrations.CreateModel(
            name="DocumentCounter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="ro_core.warehouse")),
                ("issue_date", models.DateField()),
                ("last_value", models.BigIntegerField(default=10000)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("warehouse", "issue_date"), name="uq_ro_document_counter")],
            },
        ),
        migrations.CreateModel(
            name="OdooDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=24)),
                ("source_document", models.CharField(max_length=100, unique=True)),
                ("origin_key", models.CharField(max_length=180, unique=True)),
                ("odoo_model", models.CharField(max_length=100)),
                ("odoo_id", models.BigIntegerField(blank=True, null=True)),
                ("state", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSING", "Processing"), ("SUCCEEDED", "Succeeded"), ("FAILED", "Failed"), ("UNKNOWN", "Unknown")], default="PENDING", max_length=16)),
                ("payload", models.JSONField(default=dict)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("odoo_model", "odoo_id"), name="uq_ro_remote_document")],
                "indexes": [models.Index(fields=["state"], name="ix_ro_odoo_doc_state")],
            },
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("entity", models.CharField(max_length=80)),
                ("entity_id", models.CharField(max_length=80)),
                ("action", models.CharField(max_length=40)),
                ("changes", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["entity", "entity_id", "created_at"], name="ix_ro_audit_entity")],
            },
        ),
    ]
