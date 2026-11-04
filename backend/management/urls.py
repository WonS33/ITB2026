from django.urls import path

from . import views

urlpatterns = [
    path("monthly/export/", views.MonthlyExportView.as_view()),
    path("monthly/<int:year>/<int:month>/", views.MonthlyFinanceView.as_view()),
    path("monthly/<int:year>/<int:month>/unconfirm/", views.MonthlyUnconfirmView.as_view()),
    path("monthly/<int:year>/<int:month>/ledger/", views.MonthlyLedgerView.as_view()),
    path("history/", views.HistoryView.as_view()),
]
