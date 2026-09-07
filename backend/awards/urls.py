from django.urls import path

from .views import ConfirmAwardView, MonthlyAwardsView, WeeklyAwardsView

urlpatterns = [
    path('weekly/', WeeklyAwardsView.as_view(), name='awards-weekly'),
    path('monthly/', MonthlyAwardsView.as_view(), name='awards-monthly'),
    path('<int:pk>/confirm/', ConfirmAwardView.as_view(), name='awards-confirm'),
]
