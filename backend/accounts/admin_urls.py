from django.urls import path

from . import views

# /api/admin/ 아래 주소 — 대표·경영지원팀·관리자만 (specs/08-api.md 2절)
urlpatterns = [
    path("users/", views.AdminUserListView.as_view()),
    path("users/<int:pk>/", views.AdminUserDetailView.as_view()),
    path("users/<int:pk>/reset-password/", views.AdminPasswordResetView.as_view()),
]
