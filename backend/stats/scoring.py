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
    clean_sheet: int
    win: int
    draw: int
    potw: int
    rating_points_for_five: int


def get_weights() -> PerformanceWeights:
    raw = settings.PERFORMANCE_SCORE_WEIGHTS
    return PerformanceWeights(
        goal=int(raw['GOAL_WEIGHT']),
        assist=int(raw['ASSIST_WEIGHT']),
        clean_sheet=int(raw['CLEAN_SHEET_WEIGHT']),
        win=int(raw['WIN_WEIGHT']),
        draw=int(raw.get('DRAW_WEIGHT', 1)),
        potw=int(raw.get('POTW_WEIGHT', 8)),
        rating_points_for_five=int(raw.get('RATING_POINTS_FOR_FIVE', 12)),
    )


def calculate_match_performance_score(
    *,
    goals: int = 0,
    assists: int = 0,
    clean_sheet: bool = False,
    won: bool = False,
    drew: bool = False,
) -> Decimal:
    """Deterministic per-match performance score used for POTW / TOTW / balancing."""
    w = get_weights()
    total = (
        goals * w.goal
        + assists * w.assist
        + (w.clean_sheet if clean_sheet else 0)
        + (w.win if won else 0)
        + (w.draw if drew else 0)
    )
    return Decimal(total)


def performance_to_rating(score: Decimal | int | float) -> Decimal:
    """
    Map raw performance points to a 0.0–5.0 player rating.

    Default: 12 performance points ≈ 5.0 stars (configurable, generous scale).
    Clean sheets count toward the raw score via CLEAN_SHEET_WEIGHT.
    """
    w = get_weights()
    full = Decimal(max(w.rating_points_for_five, 1))
    value = Decimal(str(score))
    if value <= 0:
        return Decimal('0.0')
    rating = (value / full) * Decimal('5')
    return min(Decimal('5.0'), rating).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
