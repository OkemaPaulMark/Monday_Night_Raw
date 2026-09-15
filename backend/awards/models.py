from django.db import models
from django.db.models import Q

from matches.models import GameWeek, Match
from players.models import Player


class Award(models.Model):
    """
    Stored awards (weekly and monthly).

    Weekly/monthly awards are stored here so the frontend never owns awards logic.
    """

    class AwardType(models.TextChoices):
        PLAYER_OF_THE_WEEK = 'POTW', 'Player of the Week'
        TEAM_OF_THE_WEEK = 'TOTW', 'Team of the Week'
        PLAYER_OF_THE_MONTH = 'POTM_MONTH', 'Player of the Month'
        GOLDEN_BOOT = 'GOLDEN_BOOT', 'Golden Boot'
        TOP_ASSISTER = 'TOP_ASSISTER', 'Top Assister'
        MOST_POTW = 'MOST_POTW', 'Most Player of the Week Awards'

    award_type = models.CharField(
        max_length=32,
        choices=AwardType.choices,
        db_index=True,
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='awards',
        help_text='Set for weekly awards tied to a standalone Monday match.',
    )
    game_week = models.ForeignKey(
        GameWeek,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='awards',
        help_text='Set for weekly awards aggregated across a multi-fixture game week.',
    )
    year = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    month = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    is_confirmed = models.BooleanField(
        default=False,
        help_text='Admin confirmation for recommended weekly awards.',
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['award_type', 'match'],
                condition=Q(match__isnull=False),
                name='unique_weekly_award_per_match_type',
            ),
            models.UniqueConstraint(
                fields=['award_type', 'game_week'],
                condition=Q(game_week__isnull=False),
                name='unique_weekly_award_per_game_week_type',
            ),
            models.UniqueConstraint(
                fields=['award_type', 'year', 'month'],
                condition=Q(
                    match__isnull=True,
                    year__isnull=False,
                    month__isnull=False,
                ),
                name='unique_monthly_award_per_period_type',
            ),
            models.CheckConstraint(
                condition=Q(month__isnull=True) | Q(month__gte=1, month__lte=12),
                name='award_month_valid_range',
            ),
        ]
        indexes = [
            models.Index(fields=['award_type', 'year', 'month']),
            models.Index(fields=['award_type', 'match']),
            models.Index(fields=['award_type', 'game_week']),
        ]

    def __str__(self) -> str:
        if self.match_id:
            return f'{self.get_award_type_display()} — {self.match}'
        if self.game_week_id:
            return f'{self.get_award_type_display()} — {self.game_week}'
        if self.year and self.month:
            return f'{self.get_award_type_display()} — {self.year}-{self.month:02d}'
        return f'{self.get_award_type_display()} #{self.pk}'


class AwardRecipient(models.Model):
    """
    Players who receive an award.

    Supports ties (multiple recipients) and Team of the Week (size = team size for that match).
    """

    award = models.ForeignKey(
        Award,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='awards_received',
    )
    performance_score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rank = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['rank', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['award', 'player'],
                name='unique_award_recipient',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.player} ← {self.award}'
