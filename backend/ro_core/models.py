"""RO Middleware V1: lean Django ORM baseline.

Place this module in the 'ro_core' Django app; configure INSTALLED_APPS.
Django's auth.User/Group manage accounts; do not duplicate auth tables.
Create database schema only via manage.py makemigrations/migrate.
"""
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, F

ZERO = Decimal("0")
POSITIVE = Decimal("0.0001")


def qty_field(default=ZERO):
    return models.DecimalField(
        max_digits=18, decimal_places=4, default=default,
        validators=[MinValueValidator(ZERO)],
    )


class Warehouse(models.Model):
    class Kind(models.TextChoices):
        CENTRAL = "CENTRAL", "Central"
        KITCHEN = "KITCHEN", "Kitchen"
        PACKING = "PACKING", "Packing"
        STORE = "STORE", "Store"

    odoo_id = models.BigIntegerField(unique=True)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    stock_location_odoo_id = models.BigIntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class UserWarehouseAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "warehouse"], name="uq_ro_user_warehouse"
            )
        ]


class Product(models.Model):
    odoo_id = models.BigIntegerField(unique=True)
    sku = models.CharField(max_length=100, blank=True, default="")
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, default="")
    uom = models.CharField(max_length=40, blank=True, default="")
    bom_odoo_id = models.BigIntegerField(null=True, blank=True)
    bom_output_qty = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(POSITIVE)],
    )
    # Direct (not recursively exploded) Odoo BoM component snapshot.
    bom_components = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.sku} — {self.name}" if self.sku else self.name


class ProductionAssignment(models.Model):
    """One SKU belongs to one kitchen order template, maintained locally.

    is_active is distinct from Product.active in Odoo: inactive assignment
    stays in middleware but is hidden from future store order forms.
    """
    product = models.OneToOneField(Product, on_delete=models.PROTECT)
    kitchen = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class Schedule(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    production_label = models.CharField(max_length=120, blank=True, default="")
    sort_order = models.IntegerField(default=0)
    active = models.BooleanField(default=True)


class ProductCapacity(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT)
    max_qty = qty_field()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "schedule"], name="uq_ro_sku_capacity"
            ),
            models.CheckConstraint(
                condition=Q(max_qty__gte=0), name="ck_ro_capacity_nonnegative"
            ),
        ]


class MinStockRule(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    min_qty = qty_field()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "warehouse"], name="uq_ro_min_stock"
            )
        ]


class StoreOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        KIRIM = "KIRIM", "Kirim"
        PROSES_PRODUKSI = "PROSES_PRODUKSI", "Proses Produksi"
        NO_ORDER = "NO_ORDER", "No Order"

    store = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="store_orders"
    )
    kitchen = models.ForeignKey(
        Warehouse, on_delete=models.PROTECT, related_name="kitchen_orders"
    )
    order_date = models.DateField()
    delivery_date = models.DateField()
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    auto_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store", "kitchen", "delivery_date", "schedule"],
                name="uq_ro_store_order",
            )
        ]
        indexes = [
            models.Index(fields=["delivery_date", "status"], name="ix_ro_order_date")
        ]

    def __str__(self):
        if not self.pk:
            return "Pesanan toko baru"
        return (
            f"Order #{self.pk} · {self.store.code} → {self.kitchen.code}"
            f" · {self.delivery_date} / {self.schedule.code}"
        )


class StoreOrderLine(models.Model):
    order = models.ForeignKey(
        StoreOrder, related_name="lines", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = qty_field()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"], name="uq_ro_store_order_line"
            )
        ]

    def __str__(self):
        if not self.pk:
            return "Baris pesanan baru"
        qty = str(int(self.qty)) if self.qty == self.qty.to_integral_value() else str(self.qty)
        return f"{self.product.sku or self.product.name} · Qty {qty} · Order #{self.order_id}"


class ProductionPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        READY = "READY", "Ready"
        SENT = "SENT", "Sent"
        PARTIAL = "PARTIAL", "Partial"

    kitchen = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    production_date = models.DateField()
    delivery_date = models.DateField()
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kitchen", "production_date", "delivery_date", "schedule"],
                name="uq_ro_production_plan",
            )
        ]
        indexes = [
            models.Index(
                fields=["production_date", "schedule"],
                name="ix_ro_plan_date",
            )
        ]


class ProductionPlanLine(models.Model):
    plan = models.ForeignKey(
        ProductionPlan, related_name="lines", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty_requested = qty_field()
    qty_planned = qty_field()
    qty_mo = qty_field()
    batch_qty = models.DecimalField(
        max_digits=18, decimal_places=4,
        validators=[MinValueValidator(POSITIVE)],
    )
    capacity_qty = qty_field()
    bom_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "product"], name="uq_ro_plan_line"
            ),
            models.CheckConstraint(
                condition=Q(qty_mo__lte=F("capacity_qty")),
                name="ck_ro_mo_within_capacity",
            ),
            models.CheckConstraint(
                condition=Q(batch_qty__gt=0), name="ck_ro_batch_positive"
            ),
        ]


class MaterialRequestLine(models.Model):
    plan = models.ForeignKey(
        ProductionPlan, related_name="material_lines", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    gross_qty = qty_field()
    # Snapshot from Odoo; may be signed for reconciliation.
    stock_qty = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    minimum_qty = qty_field()
    buffer_qty = qty_field()

    @property
    def requested_qty(self):
        return self.minimum_qty + self.buffer_qty

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "product"], name="uq_ro_material_line"
            )
        ]


class PackingAllocation(models.Model):
    delivery_date = models.DateField()
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT)
    store = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty_requested = qty_field()
    qty_allocated = qty_field()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["delivery_date", "schedule", "store", "product"],
                name="uq_ro_packing_allocation",
            )
        ]


class DocumentCounter(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    issue_date = models.DateField()
    last_value = models.BigIntegerField(default=10000)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "issue_date"], name="uq_ro_document_counter"
            )
        ]


class OdooDocument(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        UNKNOWN = "UNKNOWN", "Unknown"

    kind = models.CharField(max_length=24)
    source_document = models.CharField(max_length=100, unique=True)
    origin_key = models.CharField(max_length=180, unique=True)
    odoo_model = models.CharField(max_length=100)
    odoo_id = models.BigIntegerField(null=True, blank=True)
    state = models.CharField(
        max_length=16, choices=State.choices, default=State.PENDING
    )
    payload = models.JSONField(default=dict)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["odoo_model", "odoo_id"], name="uq_ro_remote_document"
            )
        ]
        indexes = [
            models.Index(fields=["state"], name="ix_ro_odoo_doc_state")
        ]


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL
    )
    entity = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80)
    action = models.CharField(max_length=40)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["entity", "entity_id", "created_at"],
                name="ix_ro_audit_entity",
            )
        ]
