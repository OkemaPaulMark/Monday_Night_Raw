"""Team generation: manual validation helpers, random split, balanced split."""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal

from matches.models import GoalEvent, MatchTeam
from matches.services.squad_rules import team_size_for_squad, validate_squad_size
from players.models import Player
from stats.scoring import get_weights


@dataclass
class TeamSplitResult:
    team_a: list[Player]
    team_b: list[Player]
    team_a_rating: Decimal
    team_b_rating: Decimal
    method: str


def _player_historical_rating(player: Player) -> Decimal:
    """
    Simple career rating used for balanced team generation.

    Uses configurable weights against career aggregates from finalized matches.
    """
    w = get_weights()

    goals = GoalEvent.objects.filter(
        scorer=player,
        match__finalized_at__isnull=False,
    ).count()
    assists = GoalEvent.objects.filter(
        assister=player,
        match__finalized_at__isnull=False,
    ).count()

    wins = 0
    assignments = player.team_assignments.select_related('team__match').filter(
        team__match__finalized_at__isnull=False,
    )
    for assignment in assignments:
        match = assignment.team.match
        if match.team_a_score is None or match.team_b_score is None:
            continue
        if assignment.team.side == MatchTeam.Side.A:
            if match.team_a_score > match.team_b_score:
                wins += 1
        elif match.team_b_score > match.team_a_score:
            wins += 1

    from awards.models import Award, AwardRecipient

    potw = AwardRecipient.objects.filter(
        player=player,
        award__award_type=Award.AwardType.PLAYER_OF_THE_WEEK,
        award__is_confirmed=True,
    ).count()

    total = (
        goals * w.goal
        + assists * w.assist
        + potw * w.potw
        + wins * w.win
    )
    return Decimal(max(total, 1))


def validate_two_teams(team_a_ids: list[int], team_b_ids: list[int]) -> None:
    from rest_framework.exceptions import ValidationError

    total = len(team_a_ids) + len(team_b_ids)
    validate_squad_size(total)
    size = team_size_for_squad(total)

    if len(team_a_ids) != size:
        raise ValidationError({'detail': f'Team A must contain exactly {size} players.'})
    if len(team_b_ids) != size:
        raise ValidationError({'detail': f'Team B must contain exactly {size} players.'})
    if len(set(team_a_ids)) != size:
        raise ValidationError({'detail': 'Team A contains duplicate players.'})
    if len(set(team_b_ids)) != size:
        raise ValidationError({'detail': 'Team B contains duplicate players.'})
    overlap = set(team_a_ids) & set(team_b_ids)
    if overlap:
        raise ValidationError({'detail': 'A player cannot appear in both teams.'})


def generate_random_teams(players: list[Player]) -> TeamSplitResult:
    validate_squad_size(len(players))
    size = team_size_for_squad(len(players))
    shuffled = list(players)
    random.shuffle(shuffled)
    team_a = shuffled[:size]
    team_b = shuffled[size:]
    return TeamSplitResult(
        team_a=team_a,
        team_b=team_b,
        team_a_rating=_sum_ratings(team_a),
        team_b_rating=_sum_ratings(team_b),
        method='random',
    )


def generate_balanced_teams(players: list[Player]) -> TeamSplitResult:
    """
    Greedy snake draft by rating: strongest available alternates sides,
    with a final swap pass to minimize rating gap.
    """
    validate_squad_size(len(players))
    size = team_size_for_squad(len(players))

    rated = sorted(
        ((p, _player_historical_rating(p)) for p in players),
        key=lambda item: item[1],
        reverse=True,
    )

    team_a: list[Player] = []
    team_b: list[Player] = []
    rating_a = Decimal(0)
    rating_b = Decimal(0)

    for index, (player, rating) in enumerate(rated):
        if len(team_a) == size:
            team_b.append(player)
            rating_b += rating
        elif len(team_b) == size:
            team_a.append(player)
            rating_a += rating
        elif rating_a < rating_b or (rating_a == rating_b and index % 2 == 0):
            team_a.append(player)
            rating_a += rating
        else:
            team_b.append(player)
            rating_b += rating

    best_a, best_b = team_a, team_b
    best_gap = abs(rating_a - rating_b)
    for i, pa in enumerate(team_a):
        for j, pb in enumerate(team_b):
            ra = _player_historical_rating(pa)
            rb = _player_historical_rating(pb)
            new_a = rating_a - ra + rb
            new_b = rating_b - rb + ra
            gap = abs(new_a - new_b)
            if gap < best_gap:
                best_gap = gap
                cand_a = team_a.copy()
                cand_b = team_b.copy()
                cand_a[i] = pb
                cand_b[j] = pa
                best_a, best_b = cand_a, cand_b
                rating_a, rating_b = new_a, new_b

    return TeamSplitResult(
        team_a=best_a,
        team_b=best_b,
        team_a_rating=_sum_ratings(best_a),
        team_b_rating=_sum_ratings(best_b),
        method='balanced',
    )


def _sum_ratings(players: list[Player]) -> Decimal:
    return sum((_player_historical_rating(p) for p in players), Decimal(0))
