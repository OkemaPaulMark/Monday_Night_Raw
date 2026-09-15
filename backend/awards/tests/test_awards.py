from datetime import date

from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from awards.models import Award
from awards.services.award_calculator import generate_monthly_awards, set_potw_recipients, set_totw_recipients
from matches.models import Match
from matches.services import match_service
from matches.tests.helpers import (
    complete_match_with_goals,
    create_admin,
    create_match_with_players,
    create_player_user,
    create_players,
)
from players.models import Player
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

    def test_totw_filled_by_position_slots(self):
        """
        2 Defenders / 3 Midfielders / 2 Strikers, ranked within their own
        position group — not one global top-7. create_players cycles
        D/M/S, so 14 players give 5 of each, well over each slot.
        """
        players = create_players(14)
        match = Match.objects.create(match_date=date(2026, 10, 26))
        match_service.replace_goals(match, [
            {'scorer_id': p.id, 'assister_id': None} for p in players
        ])
        match_service.finalize_match(match)

        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        recipients = list(totw.recipients.select_related('player'))
        self.assertEqual(len(recipients), 7)
        positions = [r.player.position for r in recipients]
        self.assertEqual(positions.count(Player.Position.DEFENDER), 2)
        self.assertEqual(positions.count(Player.Position.MIDFIELDER), 3)
        self.assertEqual(positions.count(Player.Position.STRIKER), 2)

    def test_totw_slot_left_short_when_position_unavailable(self):
        """Only strikers played — Defender/Midfielder slots are just empty,
        not backfilled from another position."""
        strikers = [
            Player.objects.create(name=f'Striker {i}', position=Player.Position.STRIKER)
            for i in range(3)
        ]
        match = Match.objects.create(match_date=date(2026, 11, 2))
        match_service.replace_goals(match, [
            {'scorer_id': p.id, 'assister_id': None} for p in strikers
        ])
        match_service.finalize_match(match)

        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        self.assertEqual(totw.recipients.count(), 2)  # striker slot cap, not 3

    def test_manual_totw_override(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)

        # All participants of this match (see complete_match_with_goals)
        new_ids = [players[1].id, players[3].id, players[8].id]
        set_totw_recipients(totw, new_ids)
        totw.refresh_from_db()

        self.assertEqual(
            list(totw.recipients.order_by('rank').values_list('player_id', flat=True)),
            new_ids,
        )
        self.assertTrue(totw.is_confirmed)

    def test_manual_totw_override_rejects_non_participant(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        outsider = Player.objects.create(name='Never Played', position=Player.Position.STRIKER)
        with self.assertRaises(ValidationError):
            set_totw_recipients(totw, [outsider.id])

    def test_manual_totw_override_rejects_duplicates(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        with self.assertRaises(ValidationError):
            set_totw_recipients(totw, [players[1].id, players[1].id])

    def test_manual_potw_override(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)

        # Override to a single different winner, not the automatic top scorer.
        set_potw_recipients(potw, [players[2].id])
        potw.refresh_from_db()

        self.assertEqual(
            list(potw.recipients.values_list('player_id', flat=True)),
            [players[2].id],
        )
        self.assertTrue(potw.is_confirmed)

    def test_manual_potw_override_supports_declared_tie(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)

        tied_ids = [players[0].id, players[2].id]
        set_potw_recipients(potw, tied_ids)
        potw.refresh_from_db()

        self.assertEqual(
            list(potw.recipients.order_by('rank').values_list('player_id', flat=True)),
            tied_ids,
        )

    def test_manual_potw_override_rejects_non_participant(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)
        outsider = Player.objects.create(name='Never Played', position=Player.Position.STRIKER)
        with self.assertRaises(ValidationError):
            set_potw_recipients(potw, [outsider.id])

    def test_manual_potw_override_rejects_wrong_award_type(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)
        with self.assertRaises(ValidationError):
            set_potw_recipients(totw, [players[1].id])

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

    def test_goals_api_accepts_optional_team_and_score(self):
        players = create_players(4)
        res = self.client.post('/api/matches/', {'match_date': '2026-09-28'}, format='json')
        match_id = res.data['id']

        res = self.client.post(
            f'/api/matches/{match_id}/goals/',
            {
                'goals': [],
                'team_a': [players[0].id, players[1].id],
                'team_b': [players[2].id, players[3].id],
                'team_a_score': 2,
                'team_b_score': 0,
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['team_a_score'], 2)
        self.assertEqual(res.data['team_b_score'], 0)
        self.assertTrue(res.data['has_team_scores'])
        self.assertEqual(res.data['squad_size'], 4)

    def test_set_totw_api(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        totw = Award.objects.get(match=match, award_type=Award.AwardType.TEAM_OF_THE_WEEK)

        res = self.client.post(
            f'/api/awards/{totw.id}/set-totw/',
            {'player_ids': [players[1].id, players[3].id]},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data['recipients']), 2)

    def test_set_potw_api(self):
        match, players = create_match_with_players()
        complete_match_with_goals(match, players)
        potw = Award.objects.get(match=match, award_type=Award.AwardType.PLAYER_OF_THE_WEEK)

        res = self.client.post(
            f'/api/awards/{potw.id}/set-potw/',
            {'player_ids': [players[7].id]},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data['recipients']), 1)
        self.assertEqual(res.data['recipients'][0]['player']['id'], players[7].id)
