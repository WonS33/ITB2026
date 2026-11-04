from django.urls import path

from . import dashboard_views, settings_views, views

urlpatterns = [
    path("monthly/export/", views.MonthlyExportView.as_view()),
    path("monthly/<int:year>/<int:month>/", views.MonthlyFinanceView.as_view()),
    path("monthly/<int:year>/<int:month>/unconfirm/", views.MonthlyUnconfirmView.as_view()),
    path("monthly/<int:year>/<int:month>/ledger/", views.MonthlyLedgerView.as_view()),
    path("history/", views.HistoryView.as_view()),
    path("dashboard/", dashboard_views.DashboardView.as_view()),
    path("targets/<int:year>/", settings_views.TargetView.as_view()),
    path("targets/<int:year>/export/", dashboard_views.TargetsExportView.as_view()),
    path("expense-categories/", settings_views.ExpenseCategoriesView.as_view()),
]
