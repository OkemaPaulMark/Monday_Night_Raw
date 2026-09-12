from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from players.models import Player


class SelfRegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_creates_user_and_player(self):
        res = self.client.post('/api/auth/register/', {
            'username': 'newplayer',
            'email': 'newplayer@example.com',
            'name': 'New Player',
            'password': 'SuperSecret123!',
            'position': 'STRIKER',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', res.data)
        self.assertEqual(res.data['user']['username'], 'newplayer')
        player = Player.objects.get(name='New Player')
        self.assertEqual(player.position, 'STRIKER')

    def test_register_requires_position(self):
        res = self.client.post('/api/auth/register/', {
            'username': 'noposition',
            'email': 'noposition@example.com',
            'name': 'No Position',
            'password': 'SuperSecret123!',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class MeUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='alex', password='pass12345', email='alex@old.local',
            first_name='Alex', last_name='Rivera', role=User.Role.PLAYER,
        )
        self.player = Player.objects.create(
            user=self.user, name='Alex Rivera', email='alex@old.local',
        )
        self.client.force_authenticate(user=self.user)

    def test_update_username_email_name(self):
        res = self.client.patch('/api/auth/me/', {
            'username': 'alexr',
            'email': 'alex@new.local',
            'name': 'Alexander Rivera',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['username'], 'alexr')
        self.assertEqual(res.data['email'], 'alex@new.local')

        self.user.refresh_from_db()
        self.player.refresh_from_db()
        self.assertEqual(self.user.username, 'alexr')
        self.assertEqual(self.user.first_name, 'Alexander')
        self.assertEqual(self.user.last_name, 'Rivera')
        self.assertEqual(self.player.name, 'Alexander Rivera')
        self.assertEqual(self.player.email, 'alex@new.local')

    def test_partial_update_only_email(self):
        res = self.client.patch('/api/auth/me/', {'email': 'only@new.local'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'alex')
        self.assertEqual(self.user.email, 'only@new.local')

    def test_cannot_take_existing_username(self):
        User.objects.create_user(username='taken', password='pass12345')
        res = self.client.patch('/api/auth/me/', {'username': 'taken'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_reuse_existing_player_name(self):
        other_user = User.objects.create_user(username='blake', password='pass12345')
        Player.objects.create(user=other_user, name='Blake Chen')
        res = self.client.patch('/api/auth/me/', {'name': 'Blake Chen'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_without_player_can_still_update_username(self):
        admin = User.objects.create_user(
            username='admin_x', password='pass12345', role=User.Role.ADMIN,
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        res = client.patch('/api/auth/me/', {'username': 'admin_y'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        admin.refresh_from_db()
        self.assertEqual(admin.username, 'admin_y')
