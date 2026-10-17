from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


# 관리자 페이지(화면)를 만들기 전까지 Django 기본 관리 화면(/django-admin/)에서 계정을 관리한다
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "last_name", "first_name", "role", "view_teams", "edit_teams", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("역할·팀 권한", {"fields": ("role", "view_teams", "edit_teams", "must_change_password")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("역할·팀 권한", {"fields": ("last_name", "first_name", "role", "view_teams", "edit_teams")}),
    )
