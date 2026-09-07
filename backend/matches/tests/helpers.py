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


def create_fourteen_players():
    players = []
    for i in range(14):
        players.append(Player.objects.create(name=f'Test Player {i+1:02d}'))
    return players


def build_ready_match(players=None, match_date=None):
    players = players or create_fourteen_players()
    match = Match.objects.create(match_date=match_date or date(2026, 9, 7))
    match_service.set_participants(match, [p.id for p in players])
    match_service.assign_teams(
        match,
        [p.id for p in players[:7]],
        [p.id for p in players[7:]],
    )
    return match, players


def complete_match_4_2(match, players):
    match_service.set_score(match, 4, 2)
    goals = [
        {'scoring_team': 'A', 'scorer_id': players[0].id, 'assister_id': players[1].id},
        {'scoring_team': 'A', 'scorer_id': players[2].id, 'assister_id': None},
        {'scoring_team': 'A', 'scorer_id': players[0].id, 'assister_id': players[3].id},
        {'scoring_team': 'A', 'scorer_id': players[4].id, 'assister_id': players[0].id},
        {'scoring_team': 'B', 'scorer_id': players[7].id, 'assister_id': players[8].id},
        {'scoring_team': 'B', 'scorer_id': players[9].id, 'assister_id': None},
    ]
    match_service.replace_goals(match, goals)
    match_service.finalize_match(match)
    match.refresh_from_db()
    return match
