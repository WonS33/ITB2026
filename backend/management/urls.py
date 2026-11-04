from django.urls import path

from . import ai_views, dashboard_views, detail_views, ledger_import_views, ledger_views, receivables_views, settings_views, views

urlpatterns = [
    path("monthly/export/", views.MonthlyExportView.as_view()),
    path("monthly/<int:year>/<int:month>/", views.MonthlyFinanceView.as_view()),
    path("monthly/<int:year>/<int:month>/unconfirm/", views.MonthlyUnconfirmView.as_view()),
    path("monthly/<int:year>/<int:month>/ledger/", views.MonthlyLedgerView.as_view()),
    path("history/", views.HistoryView.as_view()),
    path("history/row/", receivables_views.RowHistoryView.as_view()),
    path("ledger/", ledger_views.LedgerView.as_view()),
    path("ledger/copy/", ledger_views.LedgerCopyView.as_view()),
    path("ledger/export/", ledger_views.LedgerExportView.as_view()),
    path("ledger/import/preview/", ledger_import_views.LedgerImportPreviewView.as_view()),
    path("ledger/import/", ledger_import_views.LedgerImportView.as_view()),
    path("ledger/<int:pk>/", ledger_views.LedgerDetailView.as_view()),
    path("ledger/<int:pk>/<str:action>/", ledger_views.LedgerActionView.as_view()),
    path("receivables/", receivables_views.ReceivablesView.as_view()),
    path("receivables/export/", receivables_views.ReceivablesExportView.as_view()),
    path("receivables/<int:pk>/", receivables_views.ReceivableDetailView.as_view()),
    path("receivables/<int:pk>/<str:action>/", receivables_views.ReceivableActionView.as_view()),
    path("ai-comment/", ai_views.AiCommentView.as_view()),
    path("dashboard/", dashboard_views.DashboardView.as_view()),
    path("detail/", detail_views.DetailView.as_view()),
    path("targets/<int:year>/", settings_views.TargetView.as_view()),
    path("targets/<int:year>/export/", dashboard_views.TargetsExportView.as_view()),
    path("expense-categories/", settings_views.ExpenseCategoriesView.as_view()),
]
