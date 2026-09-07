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
    ParticipantsSerializer,
    ScoreSerializer,
    TeamGenerateSerializer,
    TeamsAssignSerializer,
)
from matches.services import match_service
from matches.services.team_generator import generate_balanced_teams, generate_random_teams
from players.models import Player
from players.serializers import PlayerSerializer


class MatchViewSet(viewsets.ModelViewSet):
    queryset = (
        Match.objects.all()
        .prefetch_related(
            'participants__player',
            'availabilities__player',
            'teams__roster__player',
            'goals__scorer',
            'goals__assister',
            'goals__scoring_team',
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
            'participants', 'teams', 'generate_teams', 'score',
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
    def participants(self, request, pk=None):
        match = self.get_object()
        serializer = ParticipantsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        match_service.set_participants(match, serializer.validated_data['player_ids'])
        return Response(MatchSerializer(self.get_queryset().get(pk=match.pk)).data)

    @action(detail=True, methods=['post'])
    def teams(self, request, pk=None):
        match = self.get_object()
        serializer = TeamsAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        match_service.assign_teams(
            match,
            serializer.validated_data['team_a'],
            serializer.validated_data['team_b'],
        )
        return Response(MatchSerializer(self.get_queryset().get(pk=match.pk)).data)

    @action(detail=True, methods=['post'], url_path='generate-teams')
    def generate_teams(self, request, pk=None):
        match = self.get_object()
        serializer = TeamGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        players = list(
            Player.objects.filter(participations__match=match).order_by('id')
        )
        if serializer.validated_data['method'] == 'random':
            result = generate_random_teams(players)
        else:
            result = generate_balanced_teams(players)

        match_service.assign_teams(
            match,
            [p.id for p in result.team_a],
            [p.id for p in result.team_b],
        )
        payload = MatchSerializer(self.get_queryset().get(pk=match.pk)).data
        payload['team_ratings'] = {
            'method': result.method,
            'team_a_rating': float(result.team_a_rating),
            'team_b_rating': float(result.team_b_rating),
            'team_a': PlayerSerializer(result.team_a, many=True).data,
            'team_b': PlayerSerializer(result.team_b, many=True).data,
        }
        return Response(payload)

    @action(detail=True, methods=['post'])
    def score(self, request, pk=None):
        match = self.get_object()
        serializer = ScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        match_service.set_score(
            match,
            serializer.validated_data['team_a_score'],
            serializer.validated_data['team_b_score'],
        )
        return Response(MatchSerializer(self.get_queryset().get(pk=match.pk)).data)

    @action(detail=True, methods=['post'])
    def goals(self, request, pk=None):
        match = self.get_object()
        serializer = GoalsReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        match_service.replace_goals(match, serializer.validated_data['goals'])
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
