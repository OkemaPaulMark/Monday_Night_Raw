"""Deterministic weekly and monthly award calculations."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Count
from rest_framework.exceptions import ValidationError

from awards.models import Award, AwardRecipient
from matches.models import GameWeek, Match
from players.models import Player
from stats.services.statistics_calculator import (
    game_week_player_performance,
    match_player_performance,
)

TOTW_SIZE = 7
TOTW_SLOTS = {
    Player.Position.DEFENDER: 2,
    Player.Position.MIDFIELDER: 3,
    Player.Position.STRIKER: 2,
}


def _build_weekly_awards(*, award_kwargs: dict, participants: list[Player], scores: dict, confirm: bool) -> dict:
    """
    Shared POTW/TOTW builder used for both a standalone match and a
    game-week aggregate — `award_kwargs` pins the FK (match= or game_week=)
    every created Award should carry, `scores` maps player id -> Decimal.
    """
    Award.objects.filter(
        award_type__in=[
            Award.AwardType.PLAYER_OF_THE_WEEK,
            Award.AwardType.TEAM_OF_THE_WEEK,
        ],
        **award_kwargs,
    ).delete()

    scored: list[tuple[Player, Decimal]] = [(p, scores[p.id]) for p in participants]
    # Score descending, then name ascending as a deterministic tie-break —
    # matters most for "also played" attendees who all sit at 0 and need a
    # stable, explainable fill order for the remaining Team of the Week spots.
    scored.sort(key=lambda item: (-item[1], item[0].name.lower()))

    if not scored:
        raise ValidationError({'detail': 'No participants available for awards.'})

    # POTW: top score; include ties
    top_score = scored[0][1]
    potw_players = [p for p, s in scored if s == top_score]

    potw = Award.objects.create(
        award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
        is_confirmed=confirm,
        **award_kwargs,
    )
    for rank, player in enumerate(potw_players, start=1):
        AwardRecipient.objects.create(
            award=potw,
            player=player,
            performance_score=top_score,
            rank=rank,
        )

    # Filled by position slot (2 Defenders / 3 Midfielders / 2 Strikers), not
    # a flat top-7 — a striker's goals shouldn't crowd out every defender.
    # Ranking within each slot already uses the same performance score, which
    # only credits Defenders/Midfielders for clean sheets/conceded when that
    # data exists; players with no position set can't fill a slot at all. A
    # short-handed slot (e.g. only 1 defender played) is just left short —
    # admin can fill it via the manual override if they want.
    totw = Award.objects.create(
        award_type=Award.AwardType.TEAM_OF_THE_WEEK,
        is_confirmed=confirm,
        **award_kwargs,
    )
    totw_player_ids: list[int] = []
    for position, slot_count in TOTW_SLOTS.items():
        position_scored = [(p, s) for p, s in scored if p.position == position]
        for rank, (player, score) in enumerate(position_scored[:slot_count], start=1):
            AwardRecipient.objects.create(
                award=totw,
                player=player,
                performance_score=score,
                rank=rank,
            )
            totw_player_ids.append(player.id)

    return {
        'player_of_the_week': [p.id for p in potw_players],
        'team_of_the_week': totw_player_ids,
    }


@transaction.atomic
def generate_weekly_awards_for_match(match: Match, *, confirm: bool = True) -> dict:
    """Create/replace POTW and TOTW for a finalized standalone match."""
    if match.finalized_at is None:
        raise ValidationError({'detail': 'Match must be finalized before generating weekly awards.'})

    participants = list(Player.objects.filter(participations__match=match).distinct())
    scores = {p.id: match_player_performance(match, p) for p in participants}
    return _build_weekly_awards(
        award_kwargs={'match': match},
        participants=participants,
        scores=scores,
        confirm=confirm,
    )


@transaction.atomic
def generate_weekly_awards_for_game_week(game_week: GameWeek, *, confirm: bool = True) -> dict:
    """Create/replace POTW and TOTW for a finalized game week, aggregated
    across every one of its fixtures."""
    if game_week.finalized_at is None:
        raise ValidationError({'detail': 'Game week must be finalized before generating weekly awards.'})

    participants = list(
        Player.objects.filter(participations__match__game_week=game_week).distinct()
    )
    scores = {p.id: game_week_player_performance(game_week, p) for p in participants}
    return _build_weekly_awards(
        award_kwargs={'game_week': game_week},
        participants=participants,
        scores=scores,
        confirm=confirm,
    )


@transaction.atomic
def set_totw_recipients(award: Award, player_ids: list[int]) -> Award:
    """
    Manually override Team of the Week for a match or game week.

    Always available to admin, not just a fallback for missing data — the
    automatic slot-filling is a starting point, not the final word. Slot
    shape (2/3/2) isn't enforced here; admin has final say on the roster.
    Players must have actually played that matchday / game week.
    """
    if award.award_type != Award.AwardType.TEAM_OF_THE_WEEK or (award.match is None and award.game_week is None):
        raise ValidationError({'detail': "Only a match or game week's Team of the Week can be manually edited."})

    if len(set(player_ids)) != len(player_ids):
        raise ValidationError({'detail': 'Duplicate players in Team of the Week selection.'})

    if award.match is not None:
        participant_ids = set(award.match.participants.values_list('player_id', flat=True))
    else:
        participant_ids = set(
            award.game_week.fixtures.values_list('participants__player_id', flat=True)
        )
    invalid = [pid for pid in player_ids if pid not in participant_ids]
    if invalid:
        raise ValidationError({'detail': f'Players {invalid} did not play that matchday.'})

    award.recipients.all().delete()
    players_by_id = {p.id: p for p in Player.objects.filter(id__in=player_ids)}
    for rank, pid in enumerate(player_ids, start=1):
        player = players_by_id[pid]
        if award.match is not None:
            score = match_player_performance(award.match, player)
        else:
            score = game_week_player_performance(award.game_week, player)
        AwardRecipient.objects.create(
            award=award,
            player=player,
            performance_score=score,
            rank=rank,
        )
    award.is_confirmed = True
    award.save(update_fields=['is_confirmed', 'updated_at'])
    return award


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
