"""
Performance scoring configuration and helpers.

Weights are loaded from Django settings.PERFORMANCE_SCORE_WEIGHTS so they are
not scattered as magic numbers across the codebase.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from players.models import Player


@dataclass(frozen=True)
class PerformanceWeights:
    goal: int
    assist: int
    clean_sheet_defender: int
    clean_sheet_midfielder: int
    conceded_penalty_defender: int
    conceded_penalty_midfielder: int
    rating_points_for_five: int


def get_weights() -> PerformanceWeights:
    raw = settings.PERFORMANCE_SCORE_WEIGHTS
    return PerformanceWeights(
        goal=int(raw['GOAL_WEIGHT']),
        assist=int(raw['ASSIST_WEIGHT']),
        clean_sheet_defender=int(raw.get('CLEAN_SHEET_DEFENDER_WEIGHT', 6)),
        clean_sheet_midfielder=int(raw.get('CLEAN_SHEET_MIDFIELDER_WEIGHT', 3)),
        conceded_penalty_defender=int(raw.get('CONCEDED_PENALTY_DEFENDER', 2)),
        conceded_penalty_midfielder=int(raw.get('CONCEDED_PENALTY_MIDFIELDER', 1)),
        rating_points_for_five=int(raw.get('RATING_POINTS_FOR_FIVE', 12)),
    )


def calculate_match_performance_score(
    *,
    goals: int = 0,
    assists: int = 0,
    position: str | None = None,
    clean_sheet: bool | None = None,
    goals_conceded: int | None = None,
) -> Decimal:
    """
    Deterministic per-match performance score used for POTW / TOTW.

    Goals and assists count the same for every position — a defender's goal
    is worth exactly as much as a striker's, which is what makes "a scoring
    defender with a clean sheet outranks a clean-sheet defender with an
    assist" fall out for free, since goal weight already beats assist weight.

    Clean-sheet/goals-conceded terms only apply to Defenders and Midfielders,
    and only when team side + score were entered for that matchday (dynamic
    turnout means most days won't have them — clean_sheet/goals_conceded are
    None in that case, and this reduces to goals + assists for everyone).
    Strikers never get these terms, per the design: strikers are goals and
    assists, full stop.
    """
    w = get_weights()
    total = goals * w.goal + assists * w.assist

    if goals_conceded is not None:
        if position == Player.Position.DEFENDER:
            if clean_sheet:
                total += w.clean_sheet_defender
            total -= goals_conceded * w.conceded_penalty_defender
        elif position == Player.Position.MIDFIELDER:
            if clean_sheet:
                total += w.clean_sheet_midfielder
            total -= goals_conceded * w.conceded_penalty_midfielder

    return Decimal(total)


def performance_to_rating(score: Decimal | int | float) -> Decimal:
    """
    Map raw performance points to a 0.0–5.0 player rating.

    Default: 12 performance points ≈ 5.0 stars (configurable, generous scale).
    """
    w = get_weights()
    full = Decimal(max(w.rating_points_for_five, 1))
    value = Decimal(str(score))
    if value <= 0:
        return Decimal('0.0')
    rating = (value / full) * Decimal('5')
    return min(Decimal('5.0'), rating).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
