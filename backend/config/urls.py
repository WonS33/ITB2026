from django.contrib import admin
from django.urls import include, path, re_path

from common.views import PeriodYearsView

from .views import spa_index

urlpatterns = [
    # Django 기본 관리 화면. 우리 앱의 /admin 화면 주소와 겹치지 않게 django-admin으로 둔다
    path('django-admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/admin/', include('accounts.admin_urls')),
    path('api/production/', include('production.urls')),
    path('api/service/', include('service.urls')),
    path('api/uploads/', include('uploads.urls')),
    path('api/periods/years/', PeriodYearsView.as_view()),
    # 위에 해당하지 않는 나머지 주소는 Vue 화면으로 보낸다 (api·django-admin·static 주소는 제외)
    re_path(r'^(?!api/|django-admin/|static/).*$', spa_index),
]
