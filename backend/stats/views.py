from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from stats.services.statistics_calculator import dashboard_summary, leaderboard


class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ordering = request.query_params.get('ordering', '-goals')
        return Response(leaderboard(ordering))


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(dashboard_summary())
