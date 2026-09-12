"""Shared helpers for match workflow tests."""

from __future__ import annotations

from datetime import date

from accounts.models import User
from matches.models import Match
from matches.services import match_service
from players.models import Player


def create_admin(username='admin_test', password='pass12345'):
    return User.objects.create_user(
        username=username,
        password=password,
        role=User.Role.ADMIN,
        is_staff=True,
    )


def create_player_user(username, password='pass12345'):
    return User.objects.create_user(
        username=username,
        password=password,
        role=User.Role.PLAYER,
    )


_POSITION_CYCLE = [
    Player.Position.DEFENDER,
    Player.Position.MIDFIELDER,
    Player.Position.STRIKER,
]


def create_players(count=14):
    """Cycles through positions so tests naturally get a mix of all three."""
    return [
        Player.objects.create(
            name=f'Test Player {i+1:02d}',
            position=_POSITION_CYCLE[i % 3],
        )
        for i in range(count)
    ]


def create_fourteen_players():
    return create_players(14)


def create_match_with_players(players=None, match_date=None):
    """
    Create a match and a pool of registered players to test goal/assist
    entry against. There's no separate "who's playing" step — participants
    are derived from whoever ends up as a scorer/assister in replace_goals.
    """
    players = players or create_fourteen_players()
    match = Match.objects.create(match_date=match_date or date(2026, 9, 7))
    return match, players


def complete_match_with_goals(match, players):
    """Finalize a match with a fixed, deterministic set of goals/assists."""
    goals = [
        {'scorer_id': players[0].id, 'assister_id': players[1].id},
        {'scorer_id': players[2].id, 'assister_id': None},
        {'scorer_id': players[0].id, 'assister_id': players[3].id},
        {'scorer_id': players[4].id, 'assister_id': players[0].id},
        {'scorer_id': players[7].id, 'assister_id': players[8].id},
        {'scorer_id': players[9].id, 'assister_id': None},
    ]
    match_service.replace_goals(match, goals)
    match_service.finalize_match(match)
    match.refresh_from_db()
    return match
