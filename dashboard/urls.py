from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.screener_view, name='screener'),
    path('backtest/', views.backtest_view, name='backtest'),
    path('run_backtest/', views.run_backtest, name='run_backtest'),
    path('login/', auth_views.LoginView.as_view(template_name='dashboard/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('get_market_data/', views.get_market_data, name='get_market_data'),
]