from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import GameWeekTeamViewSet, GameWeekViewSet, MatchViewSet

router = DefaultRouter()
router.register(r'game-weeks', GameWeekViewSet, basename='game-week')
router.register(r'game-week-teams', GameWeekTeamViewSet, basename='game-week-team')
router.register(r'', MatchViewSet, basename='match')

urlpatterns = [
    path('', include(router.urls)),
]
