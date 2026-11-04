from django.contrib import admin

from .models import AiComment, AnnualSalesTarget, AuditLog, ExpenseCategory, LedgerEntry, MonthlyFinance, OtherExpense, Receivable


class OtherExpenseInline(admin.TabularInline):
    model = OtherExpense
    extra = 0


@admin.register(AnnualSalesTarget)
class AnnualSalesTargetAdmin(admin.ModelAdmin):
    list_display = ("year", "target_amount", "headcount", "updated_at")


@admin.register(MonthlyFinance)
class MonthlyFinanceAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "status", "product_sales", "merchandise_sales", "service_sales", "updated_at")
    list_filter = ("year", "status")
    inlines = [OtherExpenseInline]


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "cost_type", "is_active", "sort_order")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "kind", "partner_name", "amount", "deleted_at")
    list_filter = ("year", "month", "kind")
    search_fields = ("partner_name",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """변경 기록은 보기만 (추가·수정·삭제 불가)"""

    list_display = ("occurred_at", "actor_username", "screen", "action", "target_label")
    list_filter = ("screen", "action")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Receivable)
class ReceivableAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "occurred_on", "amount", "is_collected", "collected_on", "deleted_at")
    list_filter = ("is_collected",)
    search_fields = ("customer_name",)


@admin.register(AiComment)
class AiCommentAdmin(admin.ModelAdmin):
    list_display = ("year", "quarter", "model", "prompt_version", "created_by", "created_at")
    list_filter = ("model",)
