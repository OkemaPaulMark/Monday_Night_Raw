from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from players.models import Player


class Match(models.Model):
    """One Monday football game."""

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
    team_a_score = models.PositiveIntegerField(null=True, blank=True)
    team_b_score = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-match_date', '-id']
        verbose_name_plural = 'matches'
        constraints = [
            models.CheckConstraint(
                condition=Q(team_a_score__isnull=True) | Q(team_a_score__gte=0),
                name='match_team_a_score_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(team_b_score__isnull=True) | Q(team_b_score__gte=0),
                name='match_team_b_score_non_negative',
            ),
        ]

    @property
    def is_finalized(self) -> bool:
        return self.finalized_at is not None and self.status == self.Status.COMPLETED

    def __str__(self) -> str:
        return f'Match {self.match_date} ({self.status})'


class MatchParticipant(models.Model):
    """Players selected/confirmed to play in a specific match."""

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


class MatchTeam(models.Model):
    """Match-specific Team A or Team B (not a permanent club)."""

    class Side(models.TextChoices):
        A = 'A', 'Team A'
        B = 'B', 'Team B'

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='teams',
    )
    side = models.CharField(max_length=1, choices=Side.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['match', 'side'],
                name='unique_match_team_side',
            ),
        ]

    @property
    def display_name(self) -> str:
        return f'Team {self.side}'

    def __str__(self) -> str:
        return f'{self.display_name} — {self.match}'


class MatchTeamPlayer(models.Model):
    """Player assignment to a match-specific team."""

    team = models.ForeignKey(
        MatchTeam,
        on_delete=models.CASCADE,
        related_name='roster',
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='team_assignments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['team', 'player'],
                name='unique_team_player',
            ),
        ]
        indexes = [
            models.Index(fields=['team', 'player']),
        ]

    def clean(self):
        # Prevent same player on both sides of one match (also enforced in services).
        other = MatchTeamPlayer.objects.filter(
            team__match=self.team.match,
            player=self.player,
        ).exclude(pk=self.pk)
        if other.exists():
            raise ValidationError('Player cannot be assigned to both teams in one match.')

    def __str__(self) -> str:
        return f'{self.player} → {self.team}'


class GoalEvent(models.Model):
    """
    Source of truth for goals and assists.

    Assists are derived: if assister is set, that player gets +1 assist.
    """

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='goals',
    )
    scoring_team = models.ForeignKey(
        MatchTeam,
        on_delete=models.CASCADE,
        related_name='goals_scored',
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
