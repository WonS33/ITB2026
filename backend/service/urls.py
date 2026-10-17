from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.ServiceDashboardView.as_view()),
    path("reports/", views.TripReportListView.as_view()),
    path("reports/<int:pk>/", views.TripReportDetailView.as_view()),
]
