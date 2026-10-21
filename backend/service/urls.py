from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.ServiceDashboardView.as_view()),
    path("reports/", views.TripReportListView.as_view()),
    path("reports/<int:pk>/", views.TripReportDetailView.as_view()),
    path("part-prices/", views.PartPriceListView.as_view()),
    path("part-prices/<int:pk>/", views.PartPriceDetailView.as_view()),
    path("requester-regions/", views.RequesterRegionListView.as_view()),
    path("requester-regions/<int:pk>/", views.RequesterRegionDetailView.as_view()),
]
