from django.urls import path

from .views import DashboardView, LeaderboardView

urlpatterns = [
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]
