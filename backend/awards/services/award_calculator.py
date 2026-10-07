"""Deterministic weekly and monthly award calculations."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from rest_framework.exceptions import ValidationError

from awards.models import Award, AwardRecipient
from matches.models import GameWeek, Match
from players.models import Player
from stats.services.statistics_calculator import (
    game_week_player_performance,
    match_player_performance,
)

TOTW_SLOTS = {
    Player.Position.DEFENDER: 2,
    Player.Position.MIDFIELDER: 3,
    Player.Position.STRIKER: 2,
}


def _build_weekly_awards(*, award_kwargs: dict, participants: list[Player], scores: dict, confirm: bool, goal_counts: dict | None = None, assist_counts: dict | None = None) -> dict:
    """
    Shared POTW/TOTW builder used for both a standalone match and a
    game-week aggregate — `award_kwargs` pins the FK (match= or game_week=)
    every created Award should carry, `scores` maps player id -> Decimal.

    Tiebreaker order: performance score → goals → assists → name (alphabetical).
    Only a genuine tie on all three metrics results in multiple POTW recipients.
    """
    Award.objects.filter(
        award_type__in=[
            Award.AwardType.PLAYER_OF_THE_WEEK,
            Award.AwardType.TEAM_OF_THE_WEEK,
        ],
        **award_kwargs,
    ).delete()

    gc = goal_counts or {}
    ac = assist_counts or {}

    scored: list[tuple[Player, Decimal]] = [(p, scores[p.id]) for p in participants]
    # Primary: score desc. Tiebreakers: goals desc → assists desc → name asc.
    scored.sort(key=lambda item: (
        -item[1],
        -gc.get(item[0].id, 0),
        -ac.get(item[0].id, 0),
        item[0].name.lower(),
    ))

    if not scored:
        raise ValidationError({'detail': 'No participants available for awards.'})

    # POTW: winner is the top player; only include others if they are genuinely
    # tied on score AND goals AND assists (i.e. identical contribution).
    top_player, top_score = scored[0]
    top_goals = gc.get(top_player.id, 0)
    top_assists = ac.get(top_player.id, 0)
    potw_players = [
        p for p, s in scored
        if s == top_score
        and gc.get(p.id, 0) == top_goals
        and ac.get(p.id, 0) == top_assists
    ]

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
    goal_counts = {p.id: match.goals.filter(scorer=p).count() for p in participants}
    assist_counts = {p.id: match.goals.filter(assister=p).count() for p in participants}
    return _build_weekly_awards(
        award_kwargs={'match': match},
        participants=participants,
        scores=scores,
        confirm=confirm,
        goal_counts=goal_counts,
        assist_counts=assist_counts,
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
    goal_counts = {
        p.id: sum(f.goals.filter(scorer=p).count() for f in game_week.fixtures.all())
        for p in participants
    }
    assist_counts = {
        p.id: sum(f.goals.filter(assister=p).count() for f in game_week.fixtures.all())
        for p in participants
    }
    return _build_weekly_awards(
        award_kwargs={'game_week': game_week},
        participants=participants,
        scores=scores,
        confirm=confirm,
        goal_counts=goal_counts,
        assist_counts=assist_counts,
    )


def _set_manual_weekly_recipients(award: Award, player_ids: list[int], *, expected_type: str, label: str) -> Award:
    """
    Manually override Player of the Week or Team of the Week for a match or
    game week.

    Always available to admin, not just a fallback for missing data — the
    automatic calculation is a starting point, not the final word. TOTW's
    slot shape (2/3/2) isn't enforced here; admin has final say on the
    roster. Players must have actually played that matchday / game week.
    """
    if award.award_type != expected_type or (award.match is None and award.game_week is None):
        raise ValidationError({'detail': f"Only a match or game week's {label} can be manually edited."})

    if len(set(player_ids)) != len(player_ids):
        raise ValidationError({'detail': f'Duplicate players in {label} selection.'})

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
def set_totw_recipients(award: Award, player_ids: list[int]) -> Award:
    return _set_manual_weekly_recipients(
        award, player_ids,
        expected_type=Award.AwardType.TEAM_OF_THE_WEEK,
        label='Team of the Week',
    )


@transaction.atomic
def set_potw_recipients(award: Award, player_ids: list[int]) -> Award:
    return _set_manual_weekly_recipients(
        award, player_ids,
        expected_type=Award.AwardType.PLAYER_OF_THE_WEEK,
        label='Player of the Week',
    )


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

    # A weekly POTW is tied to *either* a standalone match or a game week
    # (mutually exclusive FKs) — has to check both, or POTW wins earned
    # through a game week silently don't count toward "Most POTW" that month.
    potw_counts = (
        AwardRecipient.objects.filter(
            award__award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
            award__is_confirmed=True,
        )
        .filter(
            Q(award__match__in=matches)
            | Q(award__game_week__week_date__year=year, award__game_week__week_date__month=month)
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
        # All `winners` tied on the same `best` value by construction — one
        # shared rank, not sequential #1/#2/#3, which would misrepresent a
        # tie as a real ordering.
        for pid in winners:
            score = metric.get(pid)
            AwardRecipient.objects.create(
                award=award,
                player_id=pid,
                performance_score=Decimal(score) if score is not None else None,
                rank=1,
            )
        created.append(award)
        return award

    create_metric_award(Award.AwardType.GOLDEN_BOOT, goals)
    create_metric_award(Award.AwardType.TOP_ASSISTER, assists)
    create_metric_award(Award.AwardType.MOST_POTW, potw)

    # POTM: primary = most POTW wins that month, tiebreaker = highest G+A score.
    # Collect every player who appeared in any of the three metrics.
    all_pids = set(goals) | set(assists) | set(potw) | set(performance)
    if all_pids:
        best_potw_count = max(potw.get(pid, 0) for pid in all_pids)
        # Candidates: everyone tied on the most POTW wins
        potm_candidates = [pid for pid in all_pids if potw.get(pid, 0) == best_potw_count]
        # Among those, pick whoever has the highest G+A score
        best_ga = max(performance.get(pid, Decimal(0)) for pid in potm_candidates)
        potm_winners = [pid for pid in potm_candidates if performance.get(pid, Decimal(0)) == best_ga]
    else:
        potm_winners = []

    potm_award = Award.objects.create(
        award_type=Award.AwardType.PLAYER_OF_THE_MONTH,
        year=year,
        month=month,
        is_confirmed=True,
    )
    for pid in potm_winners:
        AwardRecipient.objects.create(
            award=potm_award,
            player_id=pid,
            performance_score=performance.get(pid),
            rank=1,
        )
    created.append(potm_award)

    return created


@transaction.atomic
def set_potm_recipients(award: Award, player_ids: list[int]) -> Award:
    """Manually override Player of the Month recipients."""
    if award.award_type != Award.AwardType.PLAYER_OF_THE_MONTH:
        raise ValidationError({'detail': 'Only a Player of the Month award can be edited this way.'})
    if len(set(player_ids)) != len(player_ids):
        raise ValidationError({'detail': 'Duplicate players in selection.'})

    year, month = award.year, award.month
    participant_ids = set(
        Player.objects.filter(
            participations__match__finalized_at__isnull=False,
            participations__match__match_date__year=year,
            participations__match__match_date__month=month,
        ).values_list('id', flat=True)
    )
    invalid = [pid for pid in player_ids if pid not in participant_ids]
    if invalid:
        raise ValidationError({'detail': f'Players {invalid} did not play that month.'})

    award.recipients.all().delete()
    for rank, pid in enumerate(player_ids, start=1):
        AwardRecipient.objects.create(
            award=award,
            player_id=pid,
            performance_score=None,
            rank=rank,
        )
    award.is_confirmed = True
    award.save(update_fields=['is_confirmed', 'updated_at'])
    return award


def sync_monthly_awards_for_month(year: int, month: int) -> list[Award]:
    """
    Regenerate monthly awards for (year, month) from current data, or clear
    them if no finalized matches remain (e.g. the only match was reopened).
    """
    if not _month_matches(year, month).exists():
        Award.objects.filter(year=year, month=month, match__isnull=True).delete()
        return []
    return generate_monthly_awards(year, month)
