from django.urls import path

from . import views

urlpatterns = [
    path("", views.UploadCreateView.as_view()),
    path("<int:pk>/", views.UploadDetailView.as_view()),
    path("<int:pk>/confirm/", views.UploadConfirmView.as_view()),
    path("<int:pk>/cancel/", views.UploadCancelView.as_view()),
]
