from django.urls import path

from . import views

urlpatterns = [
    path("products/", views.ProductPriceView.as_view()),
    path("commission/", views.CommissionCalcView.as_view()),
]
