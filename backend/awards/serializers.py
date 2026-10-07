from rest_framework import serializers

from awards.models import Award, AwardRecipient
from players.serializers import PlayerSerializer
from stats.scoring import performance_to_rating


class AwardRecipientSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    rating = serializers.SerializerMethodField()
    stat_value = serializers.SerializerMethodField()

    class Meta:
        model = AwardRecipient
        fields = ('id', 'player', 'performance_score', 'rating', 'rank', 'stat_value')

    def get_rating(self, obj):
        if obj.performance_score is None:
            return None
        return float(performance_to_rating(obj.performance_score))

    def get_stat_value(self, obj):
        """Return the relevant integer stat for monthly awards (goals / assists / potw count)."""
        if obj.performance_score is None:
            return None
        award_type = obj.award.award_type
        if award_type in (
            Award.AwardType.GOLDEN_BOOT,
            Award.AwardType.TOP_ASSISTER,
            Award.AwardType.MOST_POTW,
        ):
            return int(obj.performance_score)
        return None


class AwardSerializer(serializers.ModelSerializer):
    recipients = AwardRecipientSerializer(many=True, read_only=True)
    award_type_display = serializers.CharField(
        source='get_award_type_display',
        read_only=True,
    )
    match_date = serializers.SerializerMethodField()

    class Meta:
        model = Award
        fields = (
            'id',
            'award_type',
            'award_type_display',
            'match',
            'game_week',
            'match_date',
            'year',
            'month',
            'is_confirmed',
            'notes',
            'created_at',
            'updated_at',
            'recipients',
        )

    def get_match_date(self, obj):
        if obj.match_id:
            return obj.match.match_date
        if obj.game_week_id:
            return obj.game_week.week_date
        return None
