from django.urls import path

from . import views

urlpatterns = [
    path("targets/<int:year>/", views.ProductionTargetView.as_view()),
    path("dashboard/", views.ProductionDashboardView.as_view()),
    path("serials/", views.SerialSearchView.as_view()),
    path("serials/<str:serial_full>/", views.SerialDetailView.as_view()),
    path("due-calendar/", views.DueCalendarView.as_view()),
    path("due-calendar/search/", views.DueSearchView.as_view()),
    path("due-soon/", views.DueSoonView.as_view()),
]
