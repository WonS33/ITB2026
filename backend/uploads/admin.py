from django.contrib import admin

from .models import UploadBatch


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "file_name", "status", "saved_count", "created_by", "created_at")
    list_filter = ("kind", "status")
