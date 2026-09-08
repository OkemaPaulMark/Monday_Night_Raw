"""
Performance scoring configuration and helpers.

Weights are loaded from Django settings.PERFORMANCE_SCORE_WEIGHTS so they are
not scattered as magic numbers across the codebase.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings


@dataclass(frozen=True)
class PerformanceWeights:
    goal: int
    assist: int
    rating_points_for_five: int


def get_weights() -> PerformanceWeights:
    raw = settings.PERFORMANCE_SCORE_WEIGHTS
    return PerformanceWeights(
        goal=int(raw['GOAL_WEIGHT']),
        assist=int(raw['ASSIST_WEIGHT']),
        rating_points_for_five=int(raw.get('RATING_POINTS_FOR_FIVE', 12)),
    )


def calculate_match_performance_score(
    *,
    goals: int = 0,
    assists: int = 0,
) -> Decimal:
    """
    Deterministic per-match performance score used for POTW / TOTW.

    Goals and assists only — there's no team score or fixed-team concept to
    derive clean sheets or wins/draws from (teams are formed on the pitch
    each week, never tracked in the app).
    """
    w = get_weights()
    total = goals * w.goal + assists * w.assist
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
