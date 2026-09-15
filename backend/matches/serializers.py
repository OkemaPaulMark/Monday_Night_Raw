from rest_framework import serializers

from matches.models import GameWeek, GameWeekTeam, GoalEvent, Match, MatchAvailability, MatchParticipant
from players.serializers import PlayerSerializer


class MatchParticipantSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    player_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = MatchParticipant
        fields = ('id', 'player', 'player_id', 'side')


class GameWeekTeamSerializer(serializers.ModelSerializer):
    players = PlayerSerializer(many=True, read_only=True)
    player_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False,
    )

    class Meta:
        model = GameWeekTeam
        fields = ('id', 'game_week', 'name', 'players', 'player_ids', 'created_at')
        read_only_fields = ('game_week', 'created_at')


class GameWeekTeamCreateSerializer(serializers.ModelSerializer):
    player_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False,
    )

    class Meta:
        model = GameWeekTeam
        fields = ('id', 'game_week', 'name', 'player_ids')


class MatchAvailabilitySerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)

    class Meta:
        model = MatchAvailability
        fields = ('id', 'player', 'status', 'updated_at', 'created_at')
        read_only_fields = fields


class AvailabilityWriteSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MatchAvailability.Status.choices)


class GoalEventSerializer(serializers.ModelSerializer):
    scorer = PlayerSerializer(read_only=True)
    assister = PlayerSerializer(read_only=True)

    class Meta:
        model = GoalEvent
        fields = (
            'id',
            'order',
            'scorer',
            'assister',
            'created_at',
        )


class MatchSerializer(serializers.ModelSerializer):
    participants = MatchParticipantSerializer(many=True, read_only=True)
    availabilities = MatchAvailabilitySerializer(many=True, read_only=True)
    goals = GoalEventSerializer(many=True, read_only=True)
    is_finalized = serializers.BooleanField(read_only=True)
    has_team_scores = serializers.BooleanField(read_only=True)
    team_a_name = serializers.CharField(source='team_a.name', read_only=True, default=None)
    team_b_name = serializers.CharField(source='team_b.name', read_only=True, default=None)
    squad_size = serializers.SerializerMethodField()
    potw = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = (
            'id',
            'match_date',
            'status',
            'game_week',
            'team_a',
            'team_b',
            'team_a_name',
            'team_b_name',
            'team_a_score',
            'team_b_score',
            'has_team_scores',
            'notes',
            'created_at',
            'updated_at',
            'finalized_at',
            'is_finalized',
            'squad_size',
            'participants',
            'availabilities',
            'goals',
            'potw',
        )
        read_only_fields = (
            'status',
            'game_week',
            'team_a',
            'team_b',
            'team_a_score',
            'team_b_score',
            'has_team_scores',
            'created_at',
            'updated_at',
            'finalized_at',
            'is_finalized',
            'squad_size',
            'potw',
        )

    def get_squad_size(self, obj):
        return obj.participants.count()

    def get_potw(self, obj):
        from awards.models import Award

        award = (
            Award.objects.filter(match=obj, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)
            .prefetch_related('recipients__player')
            .first()
        )
        if not award:
            return []
        return PlayerSerializer([r.player for r in award.recipients.all()], many=True).data


class MatchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = ('id', 'match_date', 'notes', 'game_week')


class GoalInputSerializer(serializers.Serializer):
    scorer_id = serializers.IntegerField()
    assister_id = serializers.IntegerField(required=False, allow_null=True)
    order = serializers.IntegerField(required=False, min_value=1)


class GoalsReplaceSerializer(serializers.Serializer):
    goals = GoalInputSerializer(many=True)
    also_played = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text='Players who played but neither scored nor assisted.',
    )
    team_a = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text='Optional: players on Team A, for clean-sheet scoring.',
    )
    team_b = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text='Optional: players on Team B, for clean-sheet scoring.',
    )
    team_a_score = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    team_b_score = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    team_a_group = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text='Optional: id of the GameWeekTeam playing as Team A in this fixture.',
    )
    team_b_group = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text='Optional: id of the GameWeekTeam playing as Team B in this fixture.',
    )


class GameWeekSerializer(serializers.ModelSerializer):
    is_finalized = serializers.BooleanField(read_only=True)
    teams = GameWeekTeamSerializer(many=True, read_only=True)
    fixtures = serializers.SerializerMethodField()

    class Meta:
        model = GameWeek
        fields = (
            'id',
            'week_date',
            'status',
            'notes',
            'created_at',
            'updated_at',
            'finalized_at',
            'is_finalized',
            'teams',
            'fixtures',
        )
        read_only_fields = (
            'status',
            'created_at',
            'updated_at',
            'finalized_at',
            'is_finalized',
        )

    def get_fixtures(self, obj):
        fixtures = obj.fixtures.order_by('id').prefetch_related(
            'participants__player',
            'goals__scorer',
            'goals__assister',
        )
        return MatchSerializer(fixtures, many=True).data


class GameWeekCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameWeek
        fields = ('id', 'week_date', 'notes')
