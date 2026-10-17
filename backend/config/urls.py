from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django 기본 관리 화면. 우리 앱의 /admin 화면 주소와 겹치지 않게 django-admin으로 둔다
    path('django-admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/production/', include('production.urls')),
]
