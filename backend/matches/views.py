from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminOrReadOnly, IsAdminRole
from matches.models import Match, MatchAvailability
from matches.serializers import (
    AvailabilityWriteSerializer,
    GoalsReplaceSerializer,
    MatchAvailabilitySerializer,
    MatchCreateSerializer,
    MatchSerializer,
)
from matches.services import match_service
from players.models import Player


class MatchViewSet(viewsets.ModelViewSet):
    queryset = (
        Match.objects.all()
        .prefetch_related(
            'participants__player',
            'availabilities__player',
            'goals__scorer',
            'goals__assister',
        )
    )
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['status', 'match_date']
    ordering_fields = ['match_date', 'created_at']
    ordering = ['-match_date', '-id']

    def get_serializer_class(self):
        if self.action == 'create':
            return MatchCreateSerializer
        return MatchSerializer

    def get_permissions(self):
        admin_actions = {
            'create', 'update', 'partial_update', 'destroy',
            'goals', 'finalize', 'reopen',
        }
        if self.action in admin_actions:
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        match = serializer.save()
        return Response(
            MatchSerializer(self.get_queryset().get(pk=match.pk)).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get', 'post'])
    def availability(self, request, pk=None):
        """
        GET: list RSVPs for the match.
        POST: player sets own availability {status: AVAILABLE|UNAVAILABLE}.
        """
        match = self.get_object()

        if request.method == 'GET':
            rows = match.availabilities.select_related('player').all()
            return Response(MatchAvailabilitySerializer(rows, many=True).data)

        if match.is_finalized:
            return Response(
                {'detail': 'Cannot change availability on a finalized match.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        player = getattr(request.user, 'player_profile', None)
        if player is None and not getattr(request.user, 'is_app_admin', False):
            return Response(
                {'detail': 'No player profile linked to this account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AvailabilityWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_player = player
        if getattr(request.user, 'is_app_admin', False) and request.data.get('player_id'):
            try:
                target_player = Player.objects.get(pk=request.data['player_id'])
            except Player.DoesNotExist:
                return Response({'detail': 'Player not found.'}, status=status.HTTP_404_NOT_FOUND)
        if target_player is None:
            return Response(
                {'detail': 'player_id is required for admin availability updates.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        row, _ = MatchAvailability.objects.update_or_create(
            match=match,
            player=target_player,
            defaults={'status': serializer.validated_data['status']},
        )
        return Response(MatchAvailabilitySerializer(row).data)

    @action(detail=True, methods=['post'])
    def goals(self, request, pk=None):
        match = self.get_object()
        serializer = GoalsReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        match_service.replace_goals(
            match,
            data['goals'],
            also_played_ids=data.get('also_played'),
            team_a_ids=data.get('team_a'),
            team_b_ids=data.get('team_b'),
            team_a_score=data.get('team_a_score'),
            team_b_score=data.get('team_b_score'),
        )
        return Response(MatchSerializer(self.get_queryset().get(pk=match.pk)).data)

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        match = self.get_object()
        match_service.finalize_match(match)
        return Response(MatchSerializer(self.get_queryset().get(pk=match.pk)).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        match = self.get_object()
        match_service.reopen_match(match)
        return Response(MatchSerializer(self.get_queryset().get(pk=match.pk)).data)
