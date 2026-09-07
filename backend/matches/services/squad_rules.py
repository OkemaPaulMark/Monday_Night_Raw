"""Squad size helpers for flexible 10–14 player matchdays."""

from django.conf import settings
from rest_framework.exceptions import ValidationError


def validate_squad_size(count: int) -> None:
    """Require an even squad size between MIN and MAX (equal teams)."""
    minimum = settings.MIN_MATCH_PLAYERS
    maximum = settings.MAX_MATCH_PLAYERS
    if count < minimum or count > maximum:
        raise ValidationError({
            'detail': (
                f'A match needs between {minimum} and {maximum} players, '
                f'got {count}.'
            ),
        })
    if count % 2 != 0:
        raise ValidationError({
            'detail': (
                f'Squad size must be even so teams are equal '
                f'(allowed: {", ".join(str(n) for n in range(minimum, maximum + 1) if n % 2 == 0)}). '
                f'Got {count}.'
            ),
        })


def team_size_for_squad(count: int) -> int:
    validate_squad_size(count)
    return count // 2
