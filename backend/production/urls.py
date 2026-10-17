from django.urls import path

from . import views

urlpatterns = [
    path("targets/<int:year>/", views.ProductionTargetView.as_view()),
    path("dashboard/", views.ProductionDashboardView.as_view()),
]
