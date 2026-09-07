from datetime import date

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from matches.models import Match
from matches.services import match_service
from matches.services.team_generator import generate_balanced_teams, generate_random_teams
from matches.tests.helpers import build_ready_match, complete_match_4_2, create_fourteen_players
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


class TeamGenerationTests(TestCase):
    def setUp(self):
        self.players = create_fourteen_players()

    def test_random_teams_split_seven(self):
        result = generate_random_teams(self.players)
        self.assertEqual(len(result.team_a), 7)
        self.assertEqual(len(result.team_b), 7)
        ids = {p.id for p in result.team_a + result.team_b}
        self.assertEqual(len(ids), 14)

    def test_balanced_teams_split_seven(self):
        result = generate_balanced_teams(self.players)
        self.assertEqual(len(result.team_a), 7)
        self.assertEqual(len(result.team_b), 7)
        self.assertGreater(result.team_a_rating, 0)
        self.assertGreater(result.team_b_rating, 0)

    def test_team_size_validation(self):
        match, players = build_ready_match(self.players)
        with self.assertRaises(ValidationError):
            match_service.assign_teams(match, [players[0].id], [p.id for p in players[1:8]])

    def test_odd_squad_rejected(self):
        from datetime import date
        from matches.models import Match
        match = Match.objects.create(match_date=date(2026, 10, 12))
        with self.assertRaises(ValidationError):
            match_service.set_participants(match, [p.id for p in self.players[:11]])


class GoalValidationTests(TestCase):
    def setUp(self):
        self.match, self.players = build_ready_match()

    def test_scorer_must_belong_to_scoring_team(self):
        match_service.set_score(self.match, 1, 0)
        with self.assertRaises(ValidationError):
            match_service.replace_goals(self.match, [{
                'scoring_team': 'A',
                'scorer_id': self.players[10].id,  # Team B player
                'assister_id': None,
            }])

    def test_goal_count_must_match_score(self):
        match_service.set_score(self.match, 2, 0)
        with self.assertRaises(ValidationError):
            match_service.replace_goals(self.match, [{
                'scoring_team': 'A',
                'scorer_id': self.players[0].id,
                'assister_id': None,
            }])

    def test_assister_must_participate(self):
        outsider = Player.objects.create(name='Outsider')
        match_service.set_score(self.match, 1, 0)
        with self.assertRaises(ValidationError):
            match_service.replace_goals(self.match, [{
                'scoring_team': 'A',
                'scorer_id': self.players[0].id,
                'assister_id': outsider.id,
            }])


class CleanSheetTests(TestCase):
    def test_winning_team_clean_sheet_on_4_0(self):
        match, players = build_ready_match()
        match_service.set_score(match, 4, 0)
        goals = [
            {'scoring_team': 'A', 'scorer_id': players[0].id, 'assister_id': None},
            {'scoring_team': 'A', 'scorer_id': players[1].id, 'assister_id': None},
            {'scoring_team': 'A', 'scorer_id': players[2].id, 'assister_id': None},
            {'scoring_team': 'A', 'scorer_id': players[3].id, 'assister_id': None},
        ]
        match_service.replace_goals(match, goals)
        match_service.finalize_match(match)

        for p in players[:7]:
            self.assertEqual(calculate_player_stats(p).clean_sheets, 1)
        for p in players[7:]:
            self.assertEqual(calculate_player_stats(p).clean_sheets, 0)

    def test_no_clean_sheet_on_4_2(self):
        match, players = build_ready_match()
        complete_match_4_2(match, players)
        for p in players:
            self.assertEqual(calculate_player_stats(p).clean_sheets, 0)

    def test_both_teams_clean_sheet_on_0_0(self):
        match, players = build_ready_match()
        match_service.set_score(match, 0, 0)
        match_service.replace_goals(match, [])
        match_service.finalize_match(match)
        for p in players:
            self.assertEqual(calculate_player_stats(p).clean_sheets, 1)


class StatisticsTests(TestCase):
    def test_goals_assists_wins(self):
        match, players = build_ready_match()
        complete_match_4_2(match, players)

        p0 = calculate_player_stats(players[0])
        self.assertEqual(p0.goals, 2)
        self.assertEqual(p0.assists, 1)
        self.assertEqual(p0.wins, 1)
        self.assertEqual(p0.losses, 0)
        self.assertEqual(p0.potw, 1)
        self.assertEqual(p0.goal_contributions, 3)

        p7 = calculate_player_stats(players[7])
        self.assertEqual(p7.goals, 1)
        self.assertEqual(p7.losses, 1)
        self.assertEqual(p7.wins, 0)


class FinalizeTests(TestCase):
    def test_finalize_auto_selects_potw(self):
        from awards.models import Award

        match, players = build_ready_match()
        complete_match_4_2(match, players)
        match.refresh_from_db()
        # players[0] has 2 goals + 1 assist on the winning side — the clear
        # top performer, so the system should pick them automatically.
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)
        self.assertEqual([r.player_id for r in potw.recipients.all()], [players[0].id])

    def test_reopen_clears_finalized(self):
        match, players = build_ready_match()
        complete_match_4_2(match, players)
        self.assertTrue(match.is_finalized)
        match_service.reopen_match(match)
        match.refresh_from_db()
        self.assertFalse(match.is_finalized)
        self.assertEqual(match.status, Match.Status.READY)
