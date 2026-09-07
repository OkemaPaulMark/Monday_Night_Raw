from rest_framework import serializers

from matches.models import (
    GoalEvent,
    Match,
    MatchAvailability,
    MatchParticipant,
    MatchTeam,
    MatchTeamPlayer,
)
from players.serializers import PlayerSerializer


class MatchParticipantSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    player_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = MatchParticipant
        fields = ('id', 'player', 'player_id')


class MatchAvailabilitySerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)

    class Meta:
        model = MatchAvailability
        fields = ('id', 'player', 'status', 'updated_at', 'created_at')
        read_only_fields = fields


class AvailabilityWriteSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MatchAvailability.Status.choices)


class MatchTeamPlayerSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)

    class Meta:
        model = MatchTeamPlayer
        fields = ('id', 'player')


class MatchTeamSerializer(serializers.ModelSerializer):
    roster = MatchTeamPlayerSerializer(many=True, read_only=True)

    class Meta:
        model = MatchTeam
        fields = ('id', 'side', 'roster')


class GoalEventSerializer(serializers.ModelSerializer):
    scorer = PlayerSerializer(read_only=True)
    assister = PlayerSerializer(read_only=True)
    scoring_team_side = serializers.CharField(source='scoring_team.side', read_only=True)

    class Meta:
        model = GoalEvent
        fields = (
            'id',
            'order',
            'scoring_team',
            'scoring_team_side',
            'scorer',
            'assister',
            'created_at',
        )


class MatchSerializer(serializers.ModelSerializer):
    participants = MatchParticipantSerializer(many=True, read_only=True)
    availabilities = MatchAvailabilitySerializer(many=True, read_only=True)
    teams = MatchTeamSerializer(many=True, read_only=True)
    goals = GoalEventSerializer(many=True, read_only=True)
    is_finalized = serializers.BooleanField(read_only=True)
    squad_size = serializers.SerializerMethodField()
    team_size = serializers.SerializerMethodField()
    potw = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = (
            'id',
            'match_date',
            'status',
            'team_a_score',
            'team_b_score',
            'notes',
            'created_at',
            'updated_at',
            'finalized_at',
            'is_finalized',
            'squad_size',
            'team_size',
            'participants',
            'availabilities',
            'teams',
            'goals',
            'potw',
        )
        read_only_fields = (
            'status',
            'created_at',
            'updated_at',
            'finalized_at',
            'is_finalized',
            'squad_size',
            'team_size',
            'potw',
        )

    def get_squad_size(self, obj):
        return obj.participants.count()

    def get_team_size(self, obj):
        count = obj.participants.count()
        return count // 2 if count >= 2 else 0

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


class ParticipantsSerializer(serializers.Serializer):
    player_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
    )


class TeamsAssignSerializer(serializers.Serializer):
    team_a = serializers.ListField(child=serializers.IntegerField())
    team_b = serializers.ListField(child=serializers.IntegerField())


class TeamGenerateSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=['random', 'balanced'])


class ScoreSerializer(serializers.Serializer):
    team_a_score = serializers.IntegerField(min_value=0)
    team_b_score = serializers.IntegerField(min_value=0)


class GoalInputSerializer(serializers.Serializer):
    scoring_team = serializers.ChoiceField(choices=['A', 'B'])
    scorer_id = serializers.IntegerField()
    assister_id = serializers.IntegerField(required=False, allow_null=True)
    order = serializers.IntegerField(required=False, min_value=1)


class GoalsReplaceSerializer(serializers.Serializer):
    goals = GoalInputSerializer(many=True)
