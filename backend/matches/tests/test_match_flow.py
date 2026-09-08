from datetime import date

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from matches.models import Match
from matches.services import match_service
from matches.tests.helpers import (
    complete_match_with_goals,
    create_match_with_players,
    create_players,
)
from players.models import Player
from stats.services.statistics_calculator import calculate_player_stats


class PlayerModelTests(TestCase):
    def test_create_player(self):
        p = Player.objects.create(name='Unique Name')
        self.assertEqual(str(p), 'Unique Name')

    def test_duplicate_player_name_rejected(self):
        Player.objects.create(name='Same Name')
        with self.assertRaises(Exception):
            Player.objects.create(name='Same Name')


def _goals_for(players):
    """One goal per player — a simple way to get an exact participant count."""
    return [{'scorer_id': p.id, 'assister_id': None} for p in players]


class SquadSizeTests(TestCase):
    """
    Turnout is dynamic (12 one week, 22+ the next) — participants are
    derived from who scores/assists, and there's no min/max range check at
    all: whatever turnout produced is what gets recorded.
    """

    def test_odd_squad_size_allowed(self):
        players = create_players(15)
        match = Match.objects.create(match_date=date(2026, 10, 12))
        match_service.replace_goals(match, _goals_for(players))
        match_service.finalize_match(match)
        self.assertEqual(match.participants.count(), 15)

    def test_large_turnout_allowed(self):
        players = create_players(22)
        match = Match.objects.create(match_date=date(2026, 10, 19))
        match_service.replace_goals(match, _goals_for(players))
        match_service.finalize_match(match)
        self.assertEqual(match.participants.count(), 22)

    def test_very_small_turnout_allowed(self):
        players = create_players(1)
        match = Match.objects.create(match_date=date(2026, 10, 26))
        match_service.replace_goals(match, _goals_for(players))
        match_service.finalize_match(match)
        self.assertEqual(match.participants.count(), 1)

    def test_no_upper_bound(self):
        players = create_players(40)
        match = Match.objects.create(match_date=date(2026, 11, 2))
        match_service.replace_goals(match, _goals_for(players))
        match_service.finalize_match(match)
        self.assertEqual(match.participants.count(), 40)

    def test_cannot_finalize_with_zero_participants(self):
        match = Match.objects.create(match_date=date(2026, 11, 9))
        with self.assertRaises(ValidationError):
            match_service.finalize_match(match)


class GoalValidationTests(TestCase):
    def setUp(self):
        self.match, self.players = create_match_with_players()

    def test_scorer_must_be_valid_active_player(self):
        with self.assertRaises(ValidationError):
            match_service.replace_goals(self.match, [{
                'scorer_id': 999999,
                'assister_id': None,
            }])

    def test_assister_must_be_valid_active_player(self):
        with self.assertRaises(ValidationError):
            match_service.replace_goals(self.match, [{
                'scorer_id': self.players[0].id,
                'assister_id': 999999,
            }])

    def test_assister_cannot_be_scorer(self):
        with self.assertRaises(ValidationError):
            match_service.replace_goals(self.match, [{
                'scorer_id': self.players[0].id,
                'assister_id': self.players[0].id,
            }])

    def test_scorer_and_assister_auto_become_participants(self):
        match_service.replace_goals(self.match, [{
            'scorer_id': self.players[0].id,
            'assister_id': self.players[1].id,
        }])
        participant_ids = set(self.match.participants.values_list('player_id', flat=True))
        self.assertEqual(participant_ids, {self.players[0].id, self.players[1].id})


class StatisticsTests(TestCase):
    def test_goals_assists_and_matches_played(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)

        p0 = calculate_player_stats(players[0])
        self.assertEqual(p0.matches_played, 1)
        self.assertEqual(p0.goals, 2)
        self.assertEqual(p0.assists, 1)
        self.assertEqual(p0.potw, 1)
        self.assertEqual(p0.goal_contributions, 3)

        # A player who never appears as a scorer/assister that day isn't
        # counted as having played — there's no separate attendance record,
        # only who's in a GoalEvent.
        never_involved = players[13]
        stats = calculate_player_stats(never_involved)
        self.assertEqual(stats.matches_played, 0)
        self.assertEqual(stats.goals, 0)


class FinalizeTests(TestCase):
    def test_finalize_auto_selects_potw(self):
        from awards.models import Award

        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        match.refresh_from_db()
        # players[0] has 2 goals + 1 assist — the clear top performer, so
        # the system should pick them automatically.
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)
        self.assertEqual([r.player_id for r in potw.recipients.all()], [players[0].id])

    def test_reopen_clears_finalized(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        self.assertTrue(match.is_finalized)
        match_service.reopen_match(match)
        match.refresh_from_db()
        self.assertFalse(match.is_finalized)
        self.assertEqual(match.status, Match.Status.READY)
