from django.contrib import admin

from .models import AnnualProductionTarget, ManufacturingRecord


@admin.register(AnnualProductionTarget)
class AnnualProductionTargetAdmin(admin.ModelAdmin):
    list_display = ("year", "target_quantity", "updated_at")


@admin.register(ManufacturingRecord)
class ManufacturingRecordAdmin(admin.ModelAdmin):
    list_display = ("serial_full", "model_name", "manufactured_date", "customer", "due_date")
    search_fields = ("serial_full", "serial_short", "customer", "project_name")
    list_filter = ("source_sheet",)
