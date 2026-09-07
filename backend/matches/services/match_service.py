"""Match lifecycle services: participants, teams, goals, finalize, reopen."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from matches.models import GoalEvent, Match, MatchParticipant, MatchTeam, MatchTeamPlayer
from matches.services.squad_rules import validate_squad_size
from matches.services.team_generator import validate_two_teams
from players.models import Player


def ensure_editable(match: Match) -> None:
    if match.is_finalized and match.status == Match.Status.COMPLETED:
        raise ValidationError({
            'detail': 'Match is finalized. Reopen it before editing.',
        })


@transaction.atomic
def set_participants(match: Match, player_ids: list[int]) -> Match:
    ensure_editable(match)
    ids = list(dict.fromkeys(player_ids))  # preserve order, unique
    validate_squad_size(len(ids))

    players = list(Player.objects.filter(id__in=ids, is_active=True))
    if len(players) != len(ids):
        raise ValidationError({'detail': 'One or more players are invalid or inactive.'})

    # Clearing teams/goals if participants change
    match.goals.all().delete()
    MatchTeamPlayer.objects.filter(team__match=match).delete()
    match.participants.all().delete()

    MatchParticipant.objects.bulk_create([
        MatchParticipant(match=match, player_id=pid) for pid in ids
    ])
    if match.status == Match.Status.DRAFT:
        match.status = Match.Status.READY
        match.save(update_fields=['status', 'updated_at'])
    return match


@transaction.atomic
def assign_teams(
    match: Match,
    team_a_ids: list[int],
    team_b_ids: list[int],
) -> Match:
    ensure_editable(match)
    validate_two_teams(team_a_ids, team_b_ids)

    participant_ids = set(match.participants.values_list('player_id', flat=True))
    if not participant_ids:
        raise ValidationError({'detail': 'Select participating players before assigning teams.'})

    all_ids = set(team_a_ids) | set(team_b_ids)
    if all_ids != participant_ids:
        raise ValidationError({
            'detail': 'Team rosters must include exactly the participating players.',
        })

    match.goals.all().delete()
    MatchTeamPlayer.objects.filter(team__match=match).delete()
    match.teams.all().delete()

    team_a = MatchTeam.objects.create(match=match, side=MatchTeam.Side.A)
    team_b = MatchTeam.objects.create(match=match, side=MatchTeam.Side.B)
    MatchTeamPlayer.objects.bulk_create([
        MatchTeamPlayer(team=team_a, player_id=pid) for pid in team_a_ids
    ])
    MatchTeamPlayer.objects.bulk_create([
        MatchTeamPlayer(team=team_b, player_id=pid) for pid in team_b_ids
    ])

    if match.status == Match.Status.DRAFT:
        match.status = Match.Status.READY
        match.save(update_fields=['status', 'updated_at'])
    return match


@transaction.atomic
def set_score(match: Match, team_a_score: int, team_b_score: int) -> Match:
    ensure_editable(match)
    if team_a_score < 0 or team_b_score < 0:
        raise ValidationError({'detail': 'Scores must be non-negative integers.'})
    match.team_a_score = team_a_score
    match.team_b_score = team_b_score
    match.save(update_fields=['team_a_score', 'team_b_score', 'updated_at'])
    return match


@transaction.atomic
def replace_goals(match: Match, goals_payload: list[dict]) -> Match:
    """
    Replace all goal events for a match.

    Each item: {scoring_team: 'A'|'B', scorer_id: int, assister_id: int|null, order?: int}
    """
    ensure_editable(match)
    if match.team_a_score is None or match.team_b_score is None:
        raise ValidationError({'detail': 'Enter the final score before recording goals.'})

    teams = {t.side: t for t in match.teams.all()}
    if MatchTeam.Side.A not in teams or MatchTeam.Side.B not in teams:
        raise ValidationError({'detail': 'Assign teams before recording goals.'})

    roster = {
        side: set(
            MatchTeamPlayer.objects.filter(team=team).values_list('player_id', flat=True)
        )
        for side, team in teams.items()
    }
    participants = set(match.participants.values_list('player_id', flat=True))

    expected_total = match.team_a_score + match.team_b_score
    if len(goals_payload) != expected_total:
        raise ValidationError({
            'detail': (
                f'Goal events must equal the final score total '
                f'({expected_total}), got {len(goals_payload)}.'
            ),
        })

    team_a_goals = 0
    team_b_goals = 0
    events: list[GoalEvent] = []

    for index, item in enumerate(goals_payload, start=1):
        side = item.get('scoring_team')
        scorer_id = item.get('scorer_id')
        assister_id = item.get('assister_id')
        order = item.get('order', index)

        if side not in (MatchTeam.Side.A, MatchTeam.Side.B):
            raise ValidationError({'detail': f'Invalid scoring_team for goal #{order}.'})
        if scorer_id is None:
            raise ValidationError({'detail': f'Scorer is required for goal #{order}.'})
        if scorer_id not in roster[side]:
            raise ValidationError({
                'detail': f'Scorer for goal #{order} must belong to Team {side}.',
            })
        if assister_id is not None:
            if assister_id not in participants:
                raise ValidationError({
                    'detail': f'Assister for goal #{order} must have participated.',
                })
            if assister_id == scorer_id:
                raise ValidationError({
                    'detail': f'Assister cannot be the same as scorer for goal #{order}.',
                })

        if side == MatchTeam.Side.A:
            team_a_goals += 1
        else:
            team_b_goals += 1

        events.append(GoalEvent(
            match=match,
            scoring_team=teams[side],
            scorer_id=scorer_id,
            assister_id=assister_id,
            order=order,
        ))

    if team_a_goals != match.team_a_score:
        raise ValidationError({
            'detail': (
                f'Team A score is {match.team_a_score} but {team_a_goals} '
                f'Team A goals were provided.'
            ),
        })
    if team_b_goals != match.team_b_score:
        raise ValidationError({
            'detail': (
                f'Team B score is {match.team_b_score} but {team_b_goals} '
                f'Team B goals were provided.'
            ),
        })

    match.goals.all().delete()
    GoalEvent.objects.bulk_create(events)
    return match


def validate_ready_to_finalize(match: Match) -> None:
    teams = list(match.teams.prefetch_related('roster'))
    if len(teams) != 2:
        raise ValidationError({'detail': 'Both Team A and Team B must be assigned.'})

    sides = {t.side: t for t in teams}
    if MatchTeam.Side.A not in sides or MatchTeam.Side.B not in sides:
        raise ValidationError({'detail': 'Both Team A and Team B must be assigned.'})

    a_ids = list(sides[MatchTeam.Side.A].roster.values_list('player_id', flat=True))
    b_ids = list(sides[MatchTeam.Side.B].roster.values_list('player_id', flat=True))
    validate_two_teams(a_ids, b_ids)

    participant_count = match.participants.count()
    validate_squad_size(participant_count)
    if participant_count != len(a_ids) + len(b_ids):
        raise ValidationError({
            'detail': 'Team rosters must match the confirmed participating players.',
        })

    if match.team_a_score is None or match.team_b_score is None:
        raise ValidationError({'detail': 'Final score is required before finalizing.'})

    if match.goals.count() != match.team_a_score + match.team_b_score:
        raise ValidationError({'detail': 'Goal events do not match the final score.'})


@transaction.atomic
def finalize_match(match: Match) -> Match:
    from awards.services.award_calculator import (
        generate_weekly_awards_for_match,
        sync_monthly_awards_for_month,
    )

    if match.is_finalized:
        raise ValidationError({'detail': 'Match is already finalized.'})

    validate_ready_to_finalize(match)

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
