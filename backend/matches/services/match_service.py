"""Match lifecycle services: goals, finalize, reopen.

There's no separate "pick who's playing" step: participants are derived
from whoever's entered as a scorer/assister, plus anyone marked as "also
played" alongside the goals — both come from the same page, from the full
registered player list. The "also played" list matters for Team of the
Week: without it, a low-scoring day (e.g. 1-0, one scorer) would only have
1-2 people to rank at all, instead of filling out to a normal team size.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from matches.models import GoalEvent, Match, MatchParticipant
from players.models import Player


def ensure_editable(match: Match) -> None:
    if match.is_finalized and match.status == Match.Status.COMPLETED:
        raise ValidationError({
            'detail': 'Match is finalized. Reopen it before editing.',
        })


@transaction.atomic
def replace_goals(
    match: Match,
    goals_payload: list[dict],
    also_played_ids: list[int] | None = None,
) -> Match:
    """
    Replace all goal events for a match, and (re)derive participants as the
    set of players who scored, assisted, or were marked "also played".

    Each goal item: {scorer_id: int, assister_id: int|null, order?: int}
    """
    ensure_editable(match)

    active_player_ids = set(Player.objects.filter(is_active=True).values_list('id', flat=True))

    events: list[GoalEvent] = []
    participant_ids: set[int] = set()

    for index, item in enumerate(goals_payload, start=1):
        scorer_id = item.get('scorer_id')
        assister_id = item.get('assister_id')
        order = item.get('order', index)

        if scorer_id is None:
            raise ValidationError({'detail': f'Scorer is required for goal #{order}.'})
        if scorer_id not in active_player_ids:
            raise ValidationError({
                'detail': f'Scorer for goal #{order} is not a valid active player.',
            })
        participant_ids.add(scorer_id)

        if assister_id is not None:
            if assister_id not in active_player_ids:
                raise ValidationError({
                    'detail': f'Assister for goal #{order} is not a valid active player.',
                })
            if assister_id == scorer_id:
                raise ValidationError({
                    'detail': f'Assister cannot be the same as scorer for goal #{order}.',
                })
            participant_ids.add(assister_id)

        events.append(GoalEvent(
            match=match,
            scorer_id=scorer_id,
            assister_id=assister_id,
            order=order,
        ))

    for pid in also_played_ids or []:
        if pid not in active_player_ids:
            raise ValidationError({'detail': f'Player {pid} is not a valid active player.'})
        participant_ids.add(pid)

    match.goals.all().delete()
    GoalEvent.objects.bulk_create(events)

    match.participants.all().delete()
    MatchParticipant.objects.bulk_create([
        MatchParticipant(match=match, player_id=pid) for pid in participant_ids
    ])

    if match.status == Match.Status.DRAFT and participant_ids:
        match.status = Match.Status.READY
        match.save(update_fields=['status', 'updated_at'])
    return match


@transaction.atomic
def finalize_match(match: Match) -> Match:
    from awards.services.award_calculator import (
        generate_weekly_awards_for_match,
        sync_monthly_awards_for_month,
    )

    if match.is_finalized:
        raise ValidationError({'detail': 'Match is already finalized.'})

    # No squad-size floor/ceiling — turnout is whatever it is. The only real
    # requirement is at least one participant, which generate_weekly_awards_
    # for_match already enforces ('No participants available for awards.').

    match.status = Match.Status.COMPLETED
    match.finalized_at = timezone.now()
    match.save(update_fields=['status', 'finalized_at', 'updated_at'])
    generate_weekly_awards_for_match(match)
    sync_monthly_awards_for_month(match.match_date.year, match.match_date.month)
    return match


@transaction.atomic
def reopen_match(match: Match) -> Match:
    """Controlled reopen for corrections; clears finalized flag and weekly/monthly awards."""
    from awards.models import Award
    from awards.services.award_calculator import sync_monthly_awards_for_month

    if not match.is_finalized:
        raise ValidationError({'detail': 'Match is not finalized.'})

    Award.objects.filter(match=match).delete()
    match.finalized_at = None
    match.status = Match.Status.READY
    match.save(update_fields=['finalized_at', 'status', 'updated_at'])
    sync_monthly_awards_for_month(match.match_date.year, match.match_date.month)
    return match
