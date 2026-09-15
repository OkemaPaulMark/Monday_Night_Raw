"""
Game weeks: one evening, several fixtures (e.g. 3 teams, round-robin),
finalized and awarded once as a whole rather than per fixture.
"""

from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from awards.models import Award
from awards.services.award_calculator import set_totw_recipients
from matches.models import GameWeek, Match
from matches.services import match_service
from matches.tests.helpers import create_admin, create_player_user
from players.models import Player
from stats.services.statistics_calculator import calculate_player_stats, game_week_player_performance


def _three_teams():
    """6 defenders, 6 midfielders, 6 strikers — 2 of each per team, so every
    fixture (2 of the 3 teams) has a realistic position spread."""
    positions = [Player.Position.DEFENDER, Player.Position.MIDFIELDER, Player.Position.STRIKER]
    players = {}
    for team_name in ('A', 'B', 'C'):
        roster = []
        for i, position in enumerate(positions):
            for slot in range(2):
                p = Player.objects.create(
                    name=f'{team_name}-{position[:3]}-{slot}',
                    position=position,
                )
                roster.append(p)
        players[team_name] = roster
    return players


class GameWeekServiceTests(TestCase):
    def setUp(self):
        self.rosters = _three_teams()
        self.game_week = match_service.create_game_week(date(2026, 9, 7))
        self.team_a = match_service.create_game_week_team(
            self.game_week, 'A', [p.id for p in self.rosters['A']],
        )
        self.team_b = match_service.create_game_week_team(
            self.game_week, 'B', [p.id for p in self.rosters['B']],
        )
        self.team_c = match_service.create_game_week_team(
            self.game_week, 'C', [p.id for p in self.rosters['C']],
        )

    def _add_fixture(self, team_x, team_y, score_x, score_y, goals):
        fixture = Match.objects.create(match_date=self.game_week.week_date, game_week=self.game_week)
        match_service.replace_goals(
            fixture,
            goals,
            team_a_ids=[p.id for p in self.rosters[team_x]],
            team_b_ids=[p.id for p in self.rosters[team_y]],
            team_a_score=score_x,
            team_b_score=score_y,
            team_a_group_id={'A': self.team_a, 'B': self.team_b, 'C': self.team_c}[team_x].id,
            team_b_group_id={'A': self.team_a, 'B': self.team_b, 'C': self.team_c}[team_y].id,
        )
        return fixture

    def test_cross_team_player_rejected(self):
        with self.assertRaises(ValidationError):
            match_service.update_game_week_team(self.team_b, player_ids=[self.rosters['A'][0].id])

    def test_finalize_game_week_requires_a_fixture(self):
        with self.assertRaises(ValidationError):
            match_service.finalize_game_week(self.game_week)

    def test_fixture_finalize_alone_does_not_award(self):
        striker_a = self.rosters['A'][4]
        fixture = self._add_fixture('A', 'B', 1, 0, [
            {'scorer_id': striker_a.id, 'assister_id': None},
        ])
        match_service.finalize_match(fixture)
        fixture.refresh_from_db()
        self.assertTrue(fixture.is_finalized)
        self.assertFalse(Award.objects.filter(match=fixture).exists())

    def test_stats_and_awards_aggregate_across_fixtures(self):
        striker_a = self.rosters['A'][4]
        defender_a1, defender_a2 = self.rosters['A'][0], self.rosters['A'][1]

        # Fixture 1: A beats B 1-0 — striker_a scores, Team A keeps a clean sheet.
        self._add_fixture('A', 'B', 1, 0, [
            {'scorer_id': striker_a.id, 'assister_id': None},
        ])
        # Fixture 2: A beats C 1-0 too — same striker scores again, second
        # clean sheet in the week for Team A's defenders.
        self._add_fixture('A', 'C', 1, 0, [
            {'scorer_id': striker_a.id, 'assister_id': None},
        ])
        # Fixture 3: B draws C 0-0 — nobody from A involved.
        self._add_fixture('B', 'C', 0, 0, [])

        match_service.finalize_game_week(self.game_week)
        self.game_week.refresh_from_db()
        self.assertTrue(self.game_week.is_finalized)

        # Striker scored twice across two fixtures this week.
        striker_stats = calculate_player_stats(striker_a)
        self.assertEqual(striker_stats.goals, 2)
        self.assertEqual(striker_stats.matches_played, 2)

        # Team A's defenders played both their fixtures and kept 2 clean sheets.
        defender_stats = calculate_player_stats(defender_a1)
        self.assertEqual(defender_stats.clean_sheets, 2)
        self.assertEqual(defender_stats.matches_played, 2)

        # Aggregate weekly POTW: Team A's defenders played both fixtures and
        # kept 2 clean sheets (2 x 6 = 12), which actually outranks
        # striker_a's 2 goals (2 x 5 = 10) under the defender-favoring
        # weighting — confirming clean-sheet credit aggregates across
        # fixtures just like goals do.
        potw = Award.objects.get(game_week=self.game_week, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)
        potw_ids = set(potw.recipients.values_list('player_id', flat=True))
        self.assertEqual(potw_ids, {defender_a1.id, defender_a2.id})
        self.assertGreater(
            game_week_player_performance(self.game_week, defender_a1),
            game_week_player_performance(self.game_week, striker_a),
        )

        # Aggregate TOTW: filled 2 Defender / 3 Midfielder / 2 Striker across
        # the whole week, not per fixture.
        totw = Award.objects.get(game_week=self.game_week, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        by_position = {}
        for r in totw.recipients.select_related('player'):
            by_position.setdefault(r.player.position, 0)
            by_position[r.player.position] += 1
        self.assertEqual(by_position.get(Player.Position.DEFENDER), 2)
        self.assertEqual(by_position.get(Player.Position.MIDFIELDER), 3)
        self.assertEqual(by_position.get(Player.Position.STRIKER), 2)

        # Defenders who played both A fixtures and kept 2 clean sheets should
        # outrank a defender from a scoreless draw.
        weekly_score_defender_a1 = game_week_player_performance(self.game_week, defender_a1)
        weekly_score_defender_b = game_week_player_performance(self.game_week, self.rosters['B'][0])
        self.assertGreater(weekly_score_defender_a1, weekly_score_defender_b)

    def test_reopen_game_week_clears_awards_and_allows_edits(self):
        striker_a = self.rosters['A'][4]
        self._add_fixture('A', 'B', 1, 0, [{'scorer_id': striker_a.id, 'assister_id': None}])
        match_service.finalize_game_week(self.game_week)
        self.assertTrue(Award.objects.filter(game_week=self.game_week).exists())

        match_service.reopen_game_week(self.game_week)
        self.game_week.refresh_from_db()
        self.assertFalse(self.game_week.is_finalized)
        self.assertFalse(Award.objects.filter(game_week=self.game_week).exists())
        fixture = self.game_week.fixtures.first()
        self.assertFalse(fixture.is_finalized)
        # editable again
        match_service.replace_goals(fixture, [{'scorer_id': striker_a.id, 'assister_id': None}])

    def test_manual_totw_override_at_game_week_level(self):
        striker_a = self.rosters['A'][4]
        self._add_fixture('A', 'B', 1, 0, [{'scorer_id': striker_a.id, 'assister_id': None}])
        match_service.finalize_game_week(self.game_week)

        totw = Award.objects.get(game_week=self.game_week, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        chosen = [self.rosters['A'][0].id, self.rosters['A'][1].id, striker_a.id]
        set_totw_recipients(totw, chosen)
        totw.refresh_from_db()
        ranked = list(totw.recipients.order_by('rank').values_list('player_id', flat=True))
        self.assertEqual(ranked, chosen)

        outsider = Player.objects.create(name='Never Played', position=Player.Position.STRIKER)
        with self.assertRaises(ValidationError):
            set_totw_recipients(totw, [outsider.id])


class GameWeekApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_admin()
        self.client.force_authenticate(user=self.admin)
        self.rosters = _three_teams()

    def test_full_game_week_api_flow(self):
        res = self.client.post('/api/matches/game-weeks/', {'week_date': '2026-09-07'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        game_week_id = res.data['id']

        team_res = self.client.post('/api/matches/game-week-teams/', {
            'game_week': game_week_id,
            'name': 'A',
            'player_ids': [p.id for p in self.rosters['A']],
        }, format='json')
        self.assertEqual(team_res.status_code, status.HTTP_201_CREATED, team_res.data)
        team_b_res = self.client.post('/api/matches/game-week-teams/', {
            'game_week': game_week_id,
            'name': 'B',
            'player_ids': [p.id for p in self.rosters['B']],
        }, format='json')
        self.assertEqual(team_b_res.status_code, status.HTTP_201_CREATED)

        fixture_res = self.client.post('/api/matches/', {
            'match_date': '2026-09-07',
            'game_week': game_week_id,
        }, format='json')
        self.assertEqual(fixture_res.status_code, status.HTTP_201_CREATED)
        fixture_id = fixture_res.data['id']

        striker_a = self.rosters['A'][4]
        goals_res = self.client.post(f'/api/matches/{fixture_id}/goals/', {
            'goals': [{'scorer_id': striker_a.id, 'assister_id': None, 'order': 1}],
            'team_a': [p.id for p in self.rosters['A']],
            'team_b': [p.id for p in self.rosters['B']],
            'team_a_score': 1,
            'team_b_score': 0,
            'team_a_group': team_res.data['id'],
            'team_b_group': team_b_res.data['id'],
        }, format='json')
        self.assertEqual(goals_res.status_code, status.HTTP_200_OK, goals_res.data)
        self.assertEqual(goals_res.data['team_a_name'], 'A')

        finalize_res = self.client.post(f'/api/matches/game-weeks/{game_week_id}/finalize/')
        self.assertEqual(finalize_res.status_code, status.HTTP_200_OK, finalize_res.data)
        self.assertTrue(finalize_res.data['is_finalized'])

        weekly_res = self.client.get('/api/awards/weekly/', {'game_week': game_week_id})
        self.assertEqual(weekly_res.status_code, status.HTTP_200_OK)
        award_types = {a['award_type'] for a in weekly_res.data}
        self.assertEqual(award_types, {'POTW', 'TOTW'})

        reopen_res = self.client.post(f'/api/matches/game-weeks/{game_week_id}/reopen/')
        self.assertEqual(reopen_res.status_code, status.HTTP_200_OK)
        self.assertFalse(reopen_res.data['is_finalized'])

    def test_player_cannot_create_game_week(self):
        player = create_player_user('gw_player')
        self.client.force_authenticate(user=player)
        res = self.client.post('/api/matches/game-weeks/', {'week_date': '2026-09-07'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
