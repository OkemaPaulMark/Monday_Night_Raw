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
from stats.services.statistics_calculator import calculate_player_stats, match_player_performance


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


class TeamScoreTests(TestCase):
    """Team side + score are optional, entered independently of goals."""

    def test_overlapping_team_assignment_rejected(self):
        players = create_players(4)
        match = Match.objects.create(match_date=date(2026, 11, 9))
        with self.assertRaises(ValidationError):
            match_service.replace_goals(
                match,
                [],
                team_a_ids=[players[0].id, players[1].id],
                team_b_ids=[players[1].id, players[2].id],
                team_a_score=1,
                team_b_score=0,
            )

    def test_team_assignment_sets_side_score_and_participants(self):
        players = create_players(4)
        match = Match.objects.create(match_date=date(2026, 11, 16))
        match_service.replace_goals(
            match,
            [],
            team_a_ids=[players[0].id, players[1].id],
            team_b_ids=[players[2].id, players[3].id],
            team_a_score=3,
            team_b_score=0,
        )
        match.refresh_from_db()
        self.assertEqual(match.team_a_score, 3)
        self.assertEqual(match.team_b_score, 0)
        self.assertTrue(match.has_team_scores)
        self.assertEqual(match.participants.count(), 4)
        self.assertEqual(match.participants.get(player=players[0]).side, 'A')
        self.assertEqual(match.participants.get(player=players[2]).side, 'B')

    def test_no_team_data_leaves_scores_null(self):
        players = create_players(2)
        match = Match.objects.create(match_date=date(2026, 11, 23))
        match_service.replace_goals(match, _goals_for(players))
        match.refresh_from_db()
        self.assertIsNone(match.team_a_score)
        self.assertFalse(match.has_team_scores)
        self.assertIsNone(match.participants.first().side)


class PositionScoringTests(TestCase):
    """
    Clean sheets/goals conceded only apply to Defenders/Midfielders, and
    only when team side + score were entered. Goals/assists count the same
    for every position, which is what makes a scoring defender with a
    clean sheet outrank a clean-sheet defender with only an assist.
    """

    def test_clean_sheet_defender_beats_conceding_defender(self):
        defender_a = Player.objects.create(name='Defender A', position=Player.Position.DEFENDER)
        defender_b = Player.objects.create(name='Defender B', position=Player.Position.DEFENDER)
        match = Match.objects.create(match_date=date(2026, 11, 30))
        match_service.replace_goals(
            match,
            [],
            team_a_ids=[defender_a.id],
            team_b_ids=[defender_b.id],
            team_a_score=2,
            team_b_score=0,
        )
        match.refresh_from_db()
        score_a = match_player_performance(match, defender_a)
        score_b = match_player_performance(match, defender_b)
        self.assertGreater(score_a, 0)  # clean sheet bonus, no goals
        self.assertLess(score_b, 0)  # conceded penalty, no goals
        self.assertGreater(score_a, score_b)

    def test_scoring_defender_with_clean_sheet_beats_assist_only_defender(self):
        d1 = Player.objects.create(name='D One', position=Player.Position.DEFENDER)
        d2 = Player.objects.create(name='D Two', position=Player.Position.DEFENDER)
        striker = Player.objects.create(name='Lone Striker', position=Player.Position.STRIKER)
        match = Match.objects.create(match_date=date(2026, 12, 7))
        match_service.replace_goals(
            match,
            [
                {'scorer_id': d1.id, 'assister_id': None},
                {'scorer_id': striker.id, 'assister_id': d2.id},
            ],
            team_a_ids=[d1.id, d2.id],
            team_b_ids=[striker.id],
            team_a_score=1,
            team_b_score=0,
        )
        match.refresh_from_db()
        score_d1 = match_player_performance(match, d1)  # goal + clean sheet
        score_d2 = match_player_performance(match, d2)  # assist + clean sheet
        self.assertGreater(score_d1, score_d2)

    def test_strikers_unaffected_by_clean_sheet_or_conceded(self):
        striker = Player.objects.create(name='Test Striker', position=Player.Position.STRIKER)
        match = Match.objects.create(match_date=date(2026, 12, 14))
        match_service.replace_goals(
            match,
            [{'scorer_id': striker.id, 'assister_id': None}],
            team_a_ids=[striker.id],
            team_a_score=1,
            team_b_score=5,
        )
        match.refresh_from_db()
        from stats.scoring import get_weights
        score = match_player_performance(match, striker)
        self.assertEqual(score, get_weights().goal)

    def test_no_bonus_without_position_set(self):
        no_position = Player.objects.create(name='No Position Player')
        match = Match.objects.create(match_date=date(2026, 12, 21))
        match_service.replace_goals(
            match,
            [],
            team_a_ids=[no_position.id],
            team_a_score=1,
            team_b_score=0,
        )
        match.refresh_from_db()
        score = match_player_performance(match, no_position)
        self.assertEqual(score, 0)
