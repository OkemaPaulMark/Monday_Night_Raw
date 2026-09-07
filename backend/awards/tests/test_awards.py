from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from awards.models import Award
from awards.services.award_calculator import generate_monthly_awards
from matches.tests.helpers import (
    build_ready_match,
    complete_match_4_2,
    create_admin,
    create_player_user,
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
        match, players = build_ready_match()
        complete_match_4_2(match, players)
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)
        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        self.assertTrue(potw.is_confirmed)
        self.assertEqual(totw.recipients.count(), 7)
        # Top performer with 2 goals + assist + win should be POTW
        self.assertEqual(potw.recipients.first().player_id, players[0].id)
        stats = calculate_player_stats(players[0])
        self.assertGreaterEqual(stats.potw, 1)

    def test_flexible_squad_size_ten(self):
        from datetime import date
        from matches.models import Match
        from matches.services import match_service
        from matches.tests.helpers import create_fourteen_players

        players = create_fourteen_players()[:10]
        match = Match.objects.create(match_date=date(2026, 10, 5))
        match_service.set_participants(match, [p.id for p in players])
        match_service.assign_teams(
            match,
            [p.id for p in players[:5]],
            [p.id for p in players[5:]],
        )
        match_service.set_score(match, 2, 1)
        match_service.replace_goals(match, [
            {'scoring_team': 'A', 'scorer_id': players[0].id, 'assister_id': None},
            {'scoring_team': 'A', 'scorer_id': players[1].id, 'assister_id': None},
            {'scoring_team': 'B', 'scorer_id': players[5].id, 'assister_id': None},
        ])
        match_service.finalize_match(match)
        from awards.models import Award
        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        self.assertEqual(totw.recipients.count(), 5)

    def test_monthly_awards(self):
        match, players = build_ready_match()
        complete_match_4_2(match, players)
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

    def test_full_api_finalize_flow(self):
        match, players = build_ready_match()
        # Use service-built match; finalize already done path via API reopen/edit not needed
        # Create a fresh match via API
        from players.models import Player
        Player.objects.all().delete()
        players = []
        for i in range(14):
            players.append(Player.objects.create(name=f'API Player {i+1:02d}'))

        res = self.client.post('/api/matches/', {'match_date': '2026-09-21'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        match_id = res.data['id']

        res = self.client.post(
            f'/api/matches/{match_id}/participants/',
            {'player_ids': [p.id for p in players]},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(
            f'/api/matches/{match_id}/generate-teams/',
            {'method': 'random'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('team_ratings', res.data)

        team_a = [row['player']['id'] for row in res.data['teams'][0]['roster']]
        team_b = [row['player']['id'] for row in res.data['teams'][1]['roster']]
        # Normalize sides
        sides = {t['side']: [r['player']['id'] for r in t['roster']] for t in res.data['teams']}
        team_a = sides['A']
        team_b = sides['B']

        res = self.client.post(
            f'/api/matches/{match_id}/score/',
            {'team_a_score': 1, 'team_b_score': 0},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(
            f'/api/matches/{match_id}/goals/',
            {'goals': [{
                'scoring_team': 'A',
                'scorer_id': team_a[0],
                'assister_id': team_a[1],
            }]},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(f'/api/matches/{match_id}/finalize/', format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'COMPLETED')
        self.assertIsNotNone(res.data['finalized_at'])

        res = self.client.get('/api/leaderboard/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data) >= 14)
