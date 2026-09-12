from rest_framework import serializers

from matches.models import GoalEvent, Match, MatchAvailability, MatchParticipant
from players.serializers import PlayerSerializer


class MatchParticipantSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    player_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = MatchParticipant
        fields = ('id', 'player', 'player_id', 'side')


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
    squad_size = serializers.SerializerMethodField()
    potw = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = (
            'id',
            'match_date',
            'status',
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
        fields = ('id', 'match_date', 'notes')


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
