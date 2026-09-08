from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from awards.models import Award
from awards.services.award_calculator import generate_monthly_awards
from matches.models import Match
from matches.services import match_service
from matches.tests.helpers import (
    complete_match_with_goals,
    create_admin,
    create_match_with_players,
    create_player_user,
    create_players,
)
from stats.services.statistics_calculator import calculate_player_stats


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_admin()

    def test_login_success(self):
        res = self.client.post('/api/auth/login/', {
            'username': 'admin_test',
            'password': 'pass12345',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('token', res.data)
        self.assertEqual(res.data['user']['role'], 'ADMIN')

    def test_player_cannot_create_match(self):
        user = create_player_user('player1')
        self.client.force_authenticate(user=user)
        res = self.client.post('/api/matches/', {'match_date': '2026-09-14'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AwardTests(TestCase):
    def test_potw_and_totw_created_on_finalize(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)
        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        self.assertTrue(potw.is_confirmed)
        self.assertEqual(totw.recipients.count(), 7)
        # Top performer with 2 goals + 1 assist should be POTW
        self.assertEqual(potw.recipients.first().player_id, players[0].id)
        stats = calculate_player_stats(players[0])
        self.assertGreaterEqual(stats.potw, 1)

    def test_totw_fixed_at_seven_on_big_turnout(self):
        """
        The scenario that started all this: 22 people show up, no fixed
        teams, no score — just goals/assists. Team of the Week should still
        be a normal-sized 7, not scale up with turnout.
        """
        players = create_players(22)
        match = Match.objects.create(match_date=date(2026, 10, 5))
        match_service.replace_goals(match, [
            {'scorer_id': p.id, 'assister_id': None} for p in players
        ])
        match_service.finalize_match(match)

        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        self.assertEqual(totw.recipients.count(), 7)

    def test_totw_capped_by_small_turnout(self):
        players = create_players(4)
        match = Match.objects.create(match_date=date(2026, 10, 12))
        match_service.replace_goals(match, [
            {'scorer_id': p.id, 'assister_id': None} for p in players
        ])
        match_service.finalize_match(match)

        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        self.assertEqual(totw.recipients.count(), 4)

    def test_also_played_fills_totw_on_low_scoring_day(self):
        """
        A 1-0 game with a single scorer and no assist would otherwise only
        have 1 person to rank. "Also played" attendees (0 goals/assists)
        fill the remaining Team of the Week spots.
        """
        players = create_players(9)
        match = Match.objects.create(match_date=date(2026, 10, 19))
        match_service.replace_goals(
            match,
            [{'scorer_id': players[0].id, 'assister_id': None}],
            also_played_ids=[p.id for p in players[1:]],
        )
        match_service.finalize_match(match)

        self.assertEqual(match.participants.count(), 9)
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)
        self.assertEqual([r.player_id for r in potw.recipients.all()], [players[0].id])

        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        self.assertEqual(totw.recipients.count(), 7)
        # The scorer must be included; the rest are the "also played" filler.
        totw_ids = {r.player_id for r in totw.recipients.all()}
        self.assertIn(players[0].id, totw_ids)

    def test_monthly_awards(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        awards = generate_monthly_awards(match.match_date.year, match.match_date.month)
        types = {a.award_type for a in awards}
        self.assertIn(Award.AwardType.GOLDEN_BOOT, types)
        self.assertIn(Award.AwardType.TOP_ASSISTER, types)
        self.assertIn(Award.AwardType.PLAYER_OF_THE_MONTH, types)
        golden = next(a for a in awards if a.award_type == Award.AwardType.GOLDEN_BOOT)
        self.assertEqual(golden.recipients.first().player_id, players[0].id)


class MatchApiWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_admin()
        self.client.force_authenticate(user=self.admin)

    def test_full_api_finalize_flow_with_large_turnout(self):
        """
        End-to-end via the API with 22 players and no squad/team/score
        entry — the exact real-world case that prompted this rework.
        Participants are derived purely from who scores/assists.
        """
        players = create_players(22)

        res = self.client.post('/api/matches/', {'match_date': '2026-09-21'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        match_id = res.data['id']

        goals_payload = [{'scorer_id': players[0].id, 'assister_id': players[1].id}]
        goals_payload += [{'scorer_id': p.id, 'assister_id': None} for p in players[2:]]

        res = self.client.post(
            f'/api/matches/{match_id}/goals/',
            {'goals': goals_payload},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['squad_size'], 22)

        res = self.client.post(f'/api/matches/{match_id}/finalize/', format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'COMPLETED')
        self.assertIsNotNone(res.data['finalized_at'])

        res = self.client.get('/api/leaderboard/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data) >= 22)
