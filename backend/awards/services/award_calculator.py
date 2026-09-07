"""Deterministic weekly and monthly award calculations."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Count
from rest_framework.exceptions import ValidationError

from awards.models import Award, AwardRecipient
from matches.models import GoalEvent, Match, MatchTeamPlayer
from players.models import Player
from stats.services.statistics_calculator import match_player_performance


@transaction.atomic
def generate_weekly_awards_for_match(match: Match, *, confirm: bool = True) -> dict:
    """Create/replace POTW and TOTW for a finalized match."""
    if match.finalized_at is None:
        raise ValidationError({'detail': 'Match must be finalized before generating weekly awards.'})

    Award.objects.filter(
        match=match,
        award_type__in=[
            Award.AwardType.PLAYER_OF_THE_WEEK,
            Award.AwardType.TEAM_OF_THE_WEEK,
        ],
    ).delete()

    participants = list(
        Player.objects.filter(participations__match=match).distinct()
    )
    scored: list[tuple[Player, Decimal]] = []
    for player in participants:
        scored.append((player, match_player_performance(match, player)))
    scored.sort(key=lambda item: item[1], reverse=True)

    if not scored:
        raise ValidationError({'detail': 'No participants available for awards.'})

    # POTW: top score; include ties
    top_score = scored[0][1]
    potw_players = [p for p, s in scored if s == top_score]

    potw = Award.objects.create(
        award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
        match=match,
        is_confirmed=confirm,
    )
    for rank, player in enumerate(potw_players, start=1):
        AwardRecipient.objects.create(
            award=potw,
            player=player,
            performance_score=top_score,
            rank=rank,
        )

    totw_size = max(match.participants.count() // 2, 1)
    totw = Award.objects.create(
        award_type=Award.AwardType.TEAM_OF_THE_WEEK,
        match=match,
        is_confirmed=confirm,
    )
    for rank, (player, score) in enumerate(scored[:totw_size], start=1):
        AwardRecipient.objects.create(
            award=totw,
            player=player,
            performance_score=score,
            rank=rank,
        )

    return {
        'player_of_the_week': [p.id for p in potw_players],
        'team_of_the_week': [p.id for p, _ in scored[:totw_size]],
    }


@transaction.atomic
def confirm_weekly_award(award: Award) -> Award:
    if award.award_type not in (
        Award.AwardType.PLAYER_OF_THE_WEEK,
        Award.AwardType.TEAM_OF_THE_WEEK,
    ):
        raise ValidationError({'detail': 'Only weekly awards can be confirmed this way.'})
    award.is_confirmed = True
    award.save(update_fields=['is_confirmed', 'updated_at'])
    return award


def _month_matches(year: int, month: int):
    return Match.objects.filter(
        finalized_at__isnull=False,
        match_date__year=year,
        match_date__month=month,
    )


@transaction.atomic
def generate_monthly_awards(year: int, month: int) -> list[Award]:
    if month < 1 or month > 12:
        raise ValidationError({'detail': 'Month must be between 1 and 12.'})

    matches = _month_matches(year, month)
    if not matches.exists():
        raise ValidationError({'detail': 'No finalized matches in that month.'})

    Award.objects.filter(
        year=year,
        month=month,
        match__isnull=True,
    ).delete()

    # Aggregate via player stats scoped to month
    player_ids = set(
        MatchTeamPlayer.objects.filter(team__match__in=matches)
        .values_list('player_id', flat=True)
    )
    players = Player.objects.filter(id__in=player_ids)

    goals: dict[int, int] = defaultdict(int)
    assists: dict[int, int] = defaultdict(int)
    potw: dict[int, int] = defaultdict(int)
    performance: dict[int, Decimal] = defaultdict(lambda: Decimal(0))

    for match in matches:
        for ge in match.goals.all():
            goals[ge.scorer_id] += 1
            if ge.assister_id:
                assists[ge.assister_id] += 1
        for player in Player.objects.filter(participations__match=match).distinct():
            performance[player.id] += match_player_performance(match, player)

    potw_counts = (
        AwardRecipient.objects.filter(
            award__award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
            award__match__in=matches,
            award__is_confirmed=True,
        )
        .values('player_id')
        .annotate(c=Count('id'))
    )
    for row in potw_counts:
        potw[row['player_id']] = row['c']

    created: list[Award] = []

    def create_metric_award(award_type: str, metric: dict[int, int | Decimal]) -> Award:
        if not metric:
            winners: list[int] = []
            best = 0
        else:
            best = max(metric.values())
            winners = [pid for pid, val in metric.items() if val == best]

        award = Award.objects.create(
            award_type=award_type,
            year=year,
            month=month,
            is_confirmed=True,
        )
        for rank, pid in enumerate(winners, start=1):
            score = metric.get(pid)
            AwardRecipient.objects.create(
                award=award,
                player_id=pid,
                performance_score=Decimal(score) if score is not None else None,
                rank=rank,
            )
        created.append(award)
        return award

    create_metric_award(Award.AwardType.GOLDEN_BOOT, goals)
    create_metric_award(Award.AwardType.TOP_ASSISTER, assists)
    create_metric_award(Award.AwardType.MOST_POTW, potw)
    create_metric_award(Award.AwardType.PLAYER_OF_THE_MONTH, performance)

    return created


def sync_monthly_awards_for_month(year: int, month: int) -> list[Award]:
    """
    Regenerate monthly awards for (year, month) from current data, or clear
    them if no finalized matches remain (e.g. the only match was reopened).
    """
    if not _month_matches(year, month).exists():
        Award.objects.filter(year=year, month=month, match__isnull=True).delete()
        return []
    return generate_monthly_awards(year, month)
