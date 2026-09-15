from django.urls import path

from .views import (
    ConfirmAwardView,
    MonthlyAwardsView,
    SetPotwRecipientsView,
    SetTotwRecipientsView,
    WeeklyAwardsView,
)

urlpatterns = [
    path('weekly/', WeeklyAwardsView.as_view(), name='awards-weekly'),
    path('monthly/', MonthlyAwardsView.as_view(), name='awards-monthly'),
    path('<int:pk>/confirm/', ConfirmAwardView.as_view(), name='awards-confirm'),
    path('<int:pk>/set-totw/', SetTotwRecipientsView.as_view(), name='awards-set-totw'),
    path('<int:pk>/set-potw/', SetPotwRecipientsView.as_view(), name='awards-set-potw'),
]
