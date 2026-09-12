from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from awards.models import Award
from awards.serializers import AwardSerializer
from awards.services.award_calculator import (
    confirm_weekly_award,
    generate_monthly_awards,
    set_totw_recipients,
)


class WeeklyAwardsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Award.objects.filter(
                award_type__in=[
                    Award.AwardType.PLAYER_OF_THE_WEEK,
                    Award.AwardType.TEAM_OF_THE_WEEK,
                ]
            )
            .prefetch_related('recipients__player')
            .select_related('match')
            .order_by('-match__match_date', 'award_type')
        )
        match_id = request.query_params.get('match')
        if match_id:
            qs = qs.filter(match_id=match_id)
        return Response(AwardSerializer(qs, many=True).data)


class MonthlyAwardsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Award.objects.filter(match__isnull=True)
            .prefetch_related('recipients__player')
            .order_by('-year', '-month', 'award_type')
        )
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)
        return Response(AwardSerializer(qs, many=True).data)

    def post(self, request):
        if not getattr(request.user, 'is_app_admin', False):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        year = int(request.data.get('year'))
        month = int(request.data.get('month'))
        awards = generate_monthly_awards(year, month)
        return Response(
            AwardSerializer(awards, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class ConfirmAwardView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            award = Award.objects.get(pk=pk)
        except Award.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        confirm_weekly_award(award)
        award.refresh_from_db()
        return Response(AwardSerializer(award).data)


class SetTotwRecipientsView(APIView):
    """Manual override of a match's Team of the Week — always available to
    admin, not just a fallback for missing clean-sheet data."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            award = Award.objects.get(pk=pk)
        except Award.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        player_ids = request.data.get('player_ids')
        if not isinstance(player_ids, list):
            return Response(
                {'detail': 'player_ids must be a list of player IDs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        set_totw_recipients(award, player_ids)
        award.refresh_from_db()
        return Response(AwardSerializer(award).data)
