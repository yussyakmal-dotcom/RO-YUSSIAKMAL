from django.contrib import admin
from . import models

# Technical admin only; four user-facing workspaces will be separate.
for model in (
    models.Warehouse, models.UserWarehouseAccess, models.Product,
    models.ProductionAssignment, models.Schedule, models.ProductCapacity,
    models.MinStockRule, models.StoreOrder, models.StoreOrderLine,
    models.ProductionPlan, models.ProductionPlanLine, models.MaterialRequestLine,
    models.PackingAllocation, models.DocumentCounter, models.OdooDocument,
    models.AuditLog,
):
    admin.site.register(model)
