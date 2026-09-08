from django.db import models

from players.models import Player


class Match(models.Model):
    """
    One matchday's stats session.

    Teams are formed physically on the pitch each week (turnout is dynamic —
    could be 2 teams, could be 3) and are never tracked in the app. This
    just records who showed up and who scored/assisted that day.
    """

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        READY = 'READY', 'Ready'
        COMPLETED = 'COMPLETED', 'Completed'

    match_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-match_date', '-id']
        verbose_name_plural = 'matches'

    @property
    def is_finalized(self) -> bool:
        return self.finalized_at is not None and self.status == self.Status.COMPLETED

    def __str__(self) -> str:
        return f'Match {self.match_date} ({self.status})'


class MatchParticipant(models.Model):
    """Players who played on a given matchday."""

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='participants',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='participations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'player'],
                name='unique_match_participant',
            ),
        ]
        indexes = [
            models.Index(fields=['match', 'player']),
        ]

    def __str__(self) -> str:
        return f'{self.player} @ {self.match}'


class MatchAvailability(models.Model):
    """
    Player RSVP for an upcoming match day.

    Separate from MatchParticipant: availability is the player's intent;
    participants are the admin-confirmed final squad.
    """

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        UNAVAILABLE = 'UNAVAILABLE', 'Unavailable'

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='availabilities',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='match_availabilities',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'match availabilities'
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'player'],
                name='unique_match_availability',
            ),
        ]
        indexes = [
            models.Index(fields=['match', 'status']),
        ]

    def __str__(self) -> str:
        return f'{self.player} → {self.match}: {self.status}'


class GoalEvent(models.Model):
    """
    Source of truth for goals and assists.

    Assists are derived: if assister is set, that player gets +1 assist.
    Not attributed to a team/side — teams aren't tracked in the app.
    """

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='goals',
    )
    scorer = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='goals_scored',
    )
    assister = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assists_made',
    )
    order = models.PositiveIntegerField(help_text='1-based goal order within the match')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'order'],
                name='unique_goal_order_per_match',
            ),
        ]
        indexes = [
            models.Index(fields=['match', 'scorer']),
            models.Index(fields=['match', 'assister']),
        ]

    def __str__(self) -> str:
        assist = f' (A: {self.assister})' if self.assister_id else ''
        return f'Goal #{self.order}: {self.scorer}{assist}'
