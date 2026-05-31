from django.urls import path
from . import views

urlpatterns = [
    path('group-suggestions/', views.group_suggestions, name='group_suggestions'),
    path('auth/login/', views.LoginView.as_view(),
         name='api_login'),   # 使用基于类的 JWT 登录视图
]
