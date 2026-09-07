from django.urls import path

from .views import DashboardView, LeaderboardView, StandingsView

urlpatterns = [
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('standings/', StandingsView.as_view(), name='standings'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]
