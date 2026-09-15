"""Match lifecycle services: goals, finalize, reopen.

There's no separate "pick who's playing" step: participants are derived
from whoever's entered as a scorer/assister, plus anyone marked as "also
played" alongside the goals — both come from the same page, from the full
registered player list. The "also played" list matters for Team of the
Week: without it, a low-scoring day (e.g. 1-0, one scorer) would only have
1-2 people to rank at all, instead of filling out to a normal team size.

Team side (A/B) + final score are a further OPTIONAL layer on the same
page/call: entered only when admin wants clean-sheet/goals-conceded scoring
for Defenders/Midfielders that day. Most days (especially 3-team turnouts)
will just skip this — everyone still scores on goals/assists alone.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from matches.models import GameWeek, GameWeekTeam, GoalEvent, Match, MatchParticipant
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
    team_a_ids: list[int] | None = None,
    team_b_ids: list[int] | None = None,
    team_a_score: int | None = None,
    team_b_score: int | None = None,
    team_a_group_id: int | None = None,
    team_b_group_id: int | None = None,
) -> Match:
    """
    Replace all goal events for a match, and (re)derive participants as the
    set of players who scored, assisted, were marked "also played", or were
    assigned a team side.

    Each goal item: {scorer_id: int, assister_id: int|null, order?: int}

    Team assignment + score are optional and independent of the goals list
    (not reconciled against it) — whatever's passed here fully replaces the
    match's team/score state, same as goals and also_played.

    team_a_group_id/team_b_group_id (only meaningful when the match belongs
    to a GameWeek) record which of that week's named GameWeekTeams played
    each side of this specific fixture — display/prefill only, independent
    of the actual per-fixture roster in team_a_ids/team_b_ids.
    """
    ensure_editable(match)

    if team_a_group_id is not None or team_b_group_id is not None:
        valid_group_ids = set()
        if match.game_week_id is not None:
            valid_group_ids = set(
                GameWeekTeam.objects.filter(game_week_id=match.game_week_id).values_list('id', flat=True)
            )
        for group_id in (team_a_group_id, team_b_group_id):
            if group_id is not None and group_id not in valid_group_ids:
                raise ValidationError({'detail': f'Team {group_id} is not part of this fixture\'s game week.'})

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

    team_a_ids = team_a_ids or []
    team_b_ids = team_b_ids or []
    overlap = set(team_a_ids) & set(team_b_ids)
    if overlap:
        raise ValidationError({'detail': f'Players {sorted(overlap)} assigned to both teams.'})
    for pid in [*team_a_ids, *team_b_ids]:
        if pid not in active_player_ids:
            raise ValidationError({'detail': f'Player {pid} is not a valid active player.'})
        participant_ids.add(pid)

    sides: dict[int, str] = {}
    for pid in team_a_ids:
        sides[pid] = MatchParticipant.Side.A
    for pid in team_b_ids:
        sides[pid] = MatchParticipant.Side.B

    match.goals.all().delete()
    GoalEvent.objects.bulk_create(events)

    match.participants.all().delete()
    MatchParticipant.objects.bulk_create([
        MatchParticipant(match=match, player_id=pid, side=sides.get(pid))
        for pid in participant_ids
    ])

    match.team_a_score = team_a_score
    match.team_b_score = team_b_score
    match.team_a_id = team_a_group_id
    match.team_b_id = team_b_group_id
    update_fields = ['team_a_score', 'team_b_score', 'team_a_id', 'team_b_id', 'updated_at']
    if match.status == Match.Status.DRAFT and participant_ids:
        match.status = Match.Status.READY
        update_fields.append('status')
    match.save(update_fields=update_fields)
    return match


@transaction.atomic
def finalize_match(match: Match) -> Match:
    """
    Finalize a single fixture.

    A standalone match (no game_week) generates its own weekly awards right
    away, same as always. A match that's part of a GameWeek only locks in
    its own stats here — weekly awards for that case are generated once,
    aggregated across every fixture, when the GameWeek itself is finalized.
    """
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
    if match.game_week_id is None:
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
    if match.game_week_id is None:
        sync_monthly_awards_for_month(match.match_date.year, match.match_date.month)
    return match


@transaction.atomic
def create_game_week(week_date, notes: str = '') -> GameWeek:
    return GameWeek.objects.create(week_date=week_date, notes=notes)


@transaction.atomic
def create_game_week_team(game_week: GameWeek, name: str, player_ids: list[int] | None = None) -> GameWeekTeam:
    ensure_game_week_editable(game_week)
    team = GameWeekTeam.objects.create(game_week=game_week, name=name)
    if player_ids:
        _validate_no_cross_team_overlap(game_week, player_ids, exclude_team_id=team.id)
        team.players.set(player_ids)
    return team


@transaction.atomic
def update_game_week_team(
    team: GameWeekTeam,
    name: str | None = None,
    player_ids: list[int] | None = None,
) -> GameWeekTeam:
    ensure_game_week_editable(team.game_week)
    if name is not None:
        team.name = name
        team.save(update_fields=['name'])
    if player_ids is not None:
        _validate_no_cross_team_overlap(team.game_week, player_ids, exclude_team_id=team.id)
        team.players.set(player_ids)
    return team


def _validate_no_cross_team_overlap(game_week: GameWeek, player_ids: list[int], exclude_team_id: int) -> None:
    other_teams = GameWeekTeam.objects.filter(game_week=game_week).exclude(id=exclude_team_id)
    taken = set(
        Player.objects.filter(
            game_week_teams__in=other_teams,
            id__in=player_ids,
        ).values_list('id', flat=True)
    )
    if taken:
        raise ValidationError({
            'detail': f'Players {sorted(taken)} are already on another team this game week.',
        })


def ensure_game_week_editable(game_week: GameWeek) -> None:
    if game_week.is_finalized:
        raise ValidationError({'detail': 'Game week is finalized. Reopen it before editing.'})


@transaction.atomic
def finalize_game_week(game_week: GameWeek) -> GameWeek:
    from awards.services.award_calculator import (
        generate_weekly_awards_for_game_week,
        sync_monthly_awards_for_month,
    )

    if game_week.is_finalized:
        raise ValidationError({'detail': 'Game week is already finalized.'})

    fixtures = list(game_week.fixtures.all())
    if not fixtures:
        raise ValidationError({'detail': 'Add at least one fixture before finalizing the game week.'})

    for fixture in fixtures:
        if not fixture.is_finalized:
            finalize_match(fixture)

    game_week.status = GameWeek.Status.COMPLETED
    game_week.finalized_at = timezone.now()
    game_week.save(update_fields=['status', 'finalized_at', 'updated_at'])
    generate_weekly_awards_for_game_week(game_week)
    sync_monthly_awards_for_month(game_week.week_date.year, game_week.week_date.month)
    return game_week


@transaction.atomic
def reopen_game_week(game_week: GameWeek) -> GameWeek:
    from awards.models import Award
    from awards.services.award_calculator import sync_monthly_awards_for_month

    if not game_week.is_finalized:
        raise ValidationError({'detail': 'Game week is not finalized.'})

    Award.objects.filter(game_week=game_week).delete()
    for fixture in game_week.fixtures.filter(status=Match.Status.COMPLETED):
        fixture.finalized_at = None
        fixture.status = Match.Status.READY
        fixture.save(update_fields=['finalized_at', 'status', 'updated_at'])

    game_week.finalized_at = None
    game_week.status = GameWeek.Status.DRAFT
    game_week.save(update_fields=['finalized_at', 'status', 'updated_at'])
    sync_monthly_awards_for_month(game_week.week_date.year, game_week.week_date.month)
    return game_week
