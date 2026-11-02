from django.urls import path

from . import views

urlpatterns = [
    path("products/", views.ProductPriceView.as_view()),
    path("commission/", views.CommissionCalcView.as_view()),
    path("settings/", views.SettingHistoryView.as_view()),
    path("access-log/", views.AccessLogView.as_view()),
]
