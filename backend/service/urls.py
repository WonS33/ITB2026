from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.ServiceDashboardView.as_view()),
    path("reports/", views.TripReportListView.as_view()),
    path("reports/<int:pk>/", views.TripReportDetailView.as_view()),
    path("part-prices/", views.PartPriceListView.as_view()),
    path("part-prices/<int:pk>/", views.PartPriceDetailView.as_view()),
    path("part-catalog/", views.PartCatalogListView.as_view()),
    path("part-catalog/choices/", views.PartCatalogChoicesView.as_view()),
    path("part-catalog/export/", views.PartCatalogExportView.as_view()),
    path("part-catalog/companies/", views.PartCompanyCompareView.as_view()),
    path("part-catalog/companies/export/", views.PartCompanyExportView.as_view()),
    path("part-catalog/<int:pk>/", views.PartCatalogDetailView.as_view()),
    path("price-standard/", views.PriceStandardView.as_view()),
    path("requester-regions/", views.RequesterRegionListView.as_view()),
    path("requester-regions/<int:pk>/", views.RequesterRegionDetailView.as_view()),
]
