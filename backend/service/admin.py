from django.contrib import admin

from .models import PartPrice, QuotePartAlias, RequesterRegion, TripReport, TripReportCompanion, TripReportPart, TripReportProduct


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


@admin.register(PartPrice)
class PartPriceAdmin(admin.ModelAdmin):
    list_display = ("part_name", "unit_price", "effective_date", "source", "quote_no")
    search_fields = ("part_name", "quote_no", "quote_item")


@admin.register(QuotePartAlias)
class QuotePartAliasAdmin(admin.ModelAdmin):
    list_display = ("quote_item", "part_name")
    search_fields = ("quote_item", "part_name")
