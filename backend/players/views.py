from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminOrReadOnly, IsAdminRole
from players.models import Player
from players.serializers import (
    PlayerPhotoUploadSerializer,
    PlayerSerializer,
    PlayerWriteSerializer,
)
from stats.services.statistics_calculator import calculate_player_stats, player_match_history


class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all().select_related('user')
    permission_classes = [IsAdminOrReadOnly]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    search_fields = ['name', 'email']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return PlayerWriteSerializer
        if self.action == 'upload_photo':
            return PlayerPhotoUploadSerializer
        return PlayerSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsAdminRole()]
        if self.action == 'upload_photo':
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        player = self.get_object()
        has_history = (
            player.participations.exists()
            or player.goals_scored.exists()
            or player.assists_made.exists()
            or player.team_assignments.exists()
            or player.awards_received.exists()
        )
        if has_history:
            return Response(
                {
                    'detail': (
                        'Cannot delete a player with match or award history. '
                        'Deactivate them instead.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = player.user
        player.delete()
        if user is not None:
            user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        player = self.get_object()
        return Response(calculate_player_stats(player).to_dict())

    @action(detail=True, methods=['get'], url_path='match-history')
    def match_history(self, request, pk=None):
        player = self.get_object()
        return Response(player_match_history(player))

    @action(
        detail=True,
        methods=['post'],
        url_path='upload-photo',
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_photo(self, request, pk=None):
        """
        Players may upload a photo for their own linked profile.
        Admins may upload for any player.
        """
        player = self.get_object()
        user = request.user
        is_owner = (
            hasattr(user, 'player_profile')
            and user.player_profile
            and user.player_profile.id == player.id
        )
        if not (getattr(user, 'is_app_admin', False) or is_owner):
            return Response(
                {'detail': 'You can only update your own profile photo.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PlayerPhotoUploadSerializer(
            player,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PlayerSerializer(player, context={'request': request}).data)
