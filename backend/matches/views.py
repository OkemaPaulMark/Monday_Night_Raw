from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminOrReadOnly, IsAdminRole
from matches.models import GameWeek, GameWeekTeam, Match, MatchAvailability
from matches.serializers import (
    AvailabilityWriteSerializer,
    GameWeekCreateSerializer,
    GameWeekSerializer,
    GameWeekTeamCreateSerializer,
    GameWeekTeamSerializer,
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
    filterset_fields = ['status', 'match_date', 'game_week']
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
            team_a_group_id=data.get('team_a_group'),
            team_b_group_id=data.get('team_b_group'),
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


class GameWeekViewSet(viewsets.ModelViewSet):
    queryset = GameWeek.objects.all().prefetch_related(
        'teams__players',
        'fixtures__participants__player',
        'fixtures__goals__scorer',
        'fixtures__goals__assister',
    )
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ['status', 'week_date']
    ordering_fields = ['week_date', 'created_at']
    ordering = ['-week_date', '-id']
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return GameWeekCreateSerializer
        return GameWeekSerializer

    def get_permissions(self):
        if self.action in {'create', 'finalize', 'reopen', 'destroy'}:
            return [IsAuthenticated(), IsAdminRole()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        game_week = serializer.save()
        return Response(
            GameWeekSerializer(self.get_queryset().get(pk=game_week.pk)).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def finalize(self, request, pk=None):
        game_week = self.get_object()
        match_service.finalize_game_week(game_week)
        return Response(GameWeekSerializer(self.get_queryset().get(pk=game_week.pk)).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        game_week = self.get_object()
        match_service.reopen_game_week(game_week)
        return Response(GameWeekSerializer(self.get_queryset().get(pk=game_week.pk)).data)


class GameWeekTeamViewSet(viewsets.ModelViewSet):
    queryset = GameWeekTeam.objects.all().prefetch_related('players')
    permission_classes = [IsAuthenticated, IsAdminRole]
    filterset_fields = ['game_week']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return GameWeekTeamCreateSerializer
        return GameWeekTeamSerializer

    def create(self, request, *args, **kwargs):
        game_week_id = request.data.get('game_week')
        try:
            game_week = GameWeek.objects.get(pk=game_week_id)
        except (GameWeek.DoesNotExist, TypeError, ValueError):
            return Response({'detail': 'Valid game_week is required.'}, status=status.HTTP_400_BAD_REQUEST)
        name = request.data.get('name', '')
        player_ids = request.data.get('player_ids')
        team = match_service.create_game_week_team(game_week, name, player_ids)
        return Response(GameWeekTeamSerializer(team).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        team = self.get_object()
        team = match_service.update_game_week_team(
            team,
            name=request.data.get('name'),
            player_ids=request.data.get('player_ids'),
        )
        return Response(GameWeekTeamSerializer(team).data)

    def perform_destroy(self, instance):
        match_service.ensure_game_week_editable(instance.game_week)
        instance.delete()
