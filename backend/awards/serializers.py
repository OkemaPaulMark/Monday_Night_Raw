from rest_framework import serializers

from awards.models import Award, AwardRecipient
from players.serializers import PlayerSerializer
from stats.scoring import performance_to_rating


class AwardRecipientSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta:
        model = AwardRecipient
        fields = ('id', 'player', 'performance_score', 'rating', 'rank')

    def get_rating(self, obj):
        if obj.performance_score is None:
            return None
        return float(performance_to_rating(obj.performance_score))


class AwardSerializer(serializers.ModelSerializer):
    recipients = AwardRecipientSerializer(many=True, read_only=True)
    award_type_display = serializers.CharField(
        source='get_award_type_display',
        read_only=True,
    )
    match_date = serializers.DateField(
        source='match.match_date',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Award
        fields = (
            'id',
            'award_type',
            'award_type_display',
            'match',
            'match_date',
            'year',
            'month',
            'is_confirmed',
            'notes',
            'created_at',
            'updated_at',
            'recipients',
        )
