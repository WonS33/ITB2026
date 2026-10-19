from django.contrib import admin

from .models import RequesterRegion, TripReport, TripReportCompanion, TripReportPart, TripReportProduct


class CompanionInline(admin.TabularInline):
    model = TripReportCompanion
    extra = 0


class ProductInline(admin.TabularInline):
    model = TripReportProduct
    extra = 0


class PartInline(admin.TabularInline):
    model = TripReportPart
    extra = 0


@admin.register(TripReport)
class TripReportAdmin(admin.ModelAdmin):
    list_display = ("start_date", "requester", "region", "district", "paid_type", "author")
    list_filter = ("region", "paid_type")
    inlines = [CompanionInline, ProductInline, PartInline]


@admin.register(RequesterRegion)
class RequesterRegionAdmin(admin.ModelAdmin):
    list_display = ("requester", "region", "district")
    search_fields = ("requester",)
