# core/urls.py
from django.urls import path, include
from . import views
from casos.urls import urlpatterns_api as casos_api_urls
from rest_framework.authtoken import views as authtoken_views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/v1/', include(casos_api_urls)),
    path('api-token-auth/', authtoken_views.obtain_auth_token)
    
]