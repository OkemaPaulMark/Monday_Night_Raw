from django.db import models
from django.db.models import Q

from players.models import Player


class GameWeek(models.Model):
    """
    One evening's worth of fixtures (e.g. 3 teams, 12 games, one date).

    A GameWeek is the unit that gets finalized and awarded — Player of the
    Week / Team of the Week are computed once, from results aggregated
    across every fixture (Match) linked to it, not per individual game.
    Each fixture is an ordinary Match row with `game_week` set; standalone
    matchdays (most evenings, one game, dynamic turnout) don't use this at
    all and keep working exactly as before.
    """

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        COMPLETED = 'COMPLETED', 'Completed'

    week_date = models.DateField(db_index=True)
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
        ordering = ['-week_date', '-id']

    @property
    def is_finalized(self) -> bool:
        return self.finalized_at is not None and self.status == self.Status.COMPLETED

    def __str__(self) -> str:
        return f'Game week {self.week_date} ({self.status})'


class GameWeekTeam(models.Model):
    """
    A named roster for one evening (e.g. "A"), defined once and reused as
    the prefill source across every fixture that team plays that week.
    Ad-hoc and week-scoped — turnout/teams are picked fresh each evening,
    nothing persists week to week.
    """

    game_week = models.ForeignKey(
        GameWeek,
        on_delete=models.CASCADE,
        related_name='teams',
    )
    name = models.CharField(max_length=50)
    players = models.ManyToManyField(Player, related_name='game_week_teams', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['game_week', 'name'],
                name='unique_game_week_team_name',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name} @ {self.game_week}'


class Match(models.Model):
    """
    One matchday's stats session — or, when `game_week` is set, one fixture
    within a multi-game evening (e.g. "A vs C, 1:1" on a 3-team night).

    Teams are formed physically on the pitch each week (turnout is dynamic —
    could be 2 teams, could be 3) and are NOT required to be tracked in the
    app — goals/assists alone are enough to finalize. Team side + score are
    optional, entered only when the admin wants clean-sheet-based stats for
    that day (see MatchParticipant.side); on a 3-team day, or any day admin
    doesn't bother, they're just left blank.

    A standalone Match (`game_week` is None) is finalized and awarded on its
    own, exactly as before. A Match that belongs to a GameWeek is finalized
    individually (so its stats count) but does NOT get its own weekly
    awards — those are generated once, aggregated across every fixture in
    the GameWeek, when the GameWeek itself is finalized.
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
    game_week = models.ForeignKey(
        GameWeek,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='fixtures',
    )
    team_a = models.ForeignKey(
        GameWeekTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fixtures_as_a',
        help_text='Which named game-week team played as Side A in this fixture (display/prefill only).',
    )
    team_b = models.ForeignKey(
        GameWeekTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fixtures_as_b',
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

    @property
    def has_team_scores(self) -> bool:
        return self.team_a_score is not None and self.team_b_score is not None

    def __str__(self) -> str:
        return f'Match {self.match_date} ({self.status})'


class MatchParticipant(models.Model):
    """
    Players who played on a given matchday.

    `side` is optional — only set when the admin entered team scores for
    that day (dynamic turnout means most days won't have it). It only
    matters for clean-sheet/goals-conceded scoring of Defenders/Midfielders.
    """

    class Side(models.TextChoices):
        A = 'A', 'Team A'
        B = 'B', 'Team B'

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
    side = models.CharField(max_length=1, choices=Side.choices, null=True, blank=True)
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
