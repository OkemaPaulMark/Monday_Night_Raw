"""
Seed the admin account and one sample player for a fresh deploy.

Real players are expected to self-register from there — this just bootstraps
enough to log in and start using the app.

Usage:
    python manage.py seed_data
    python manage.py seed_data --flush
    python manage.py seed_data --demo-players 8   # local testing only
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from awards.models import Award, AwardRecipient
from matches.models import GoalEvent, Match, MatchParticipant
from players.models import Player


DEMO_PLAYER_NAMES = [
    'Alex Rivera',
    'Blake Chen',
    'Casey Morgan',
    'Drew Patel',
    'Ellis Quinn',
    'Finley Brooks',
    'Gray Sullivan',
    'Harper Diaz',
    'Indigo Walsh',
    'Jordan Lee',
    'Kai Nakamura',
    'Logan Pierce',
    'Morgan Blake',
    'Noah Sanders',
]


class Command(BaseCommand):
    help = 'Seed the admin account and one sample player (or more, for local testing).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete existing seeded domain data before seeding.',
        )
        parser.add_argument(
            '--demo-players',
            type=int,
            default=1,
            help=(
                'Number of demo player accounts to create (default 1). '
                f'Local testing only — max {len(DEMO_PLAYER_NAMES)}.'
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write('Flushing existing domain data...')
            AwardRecipient.objects.all().delete()
            Award.objects.all().delete()
            GoalEvent.objects.all().delete()
            MatchParticipant.objects.all().delete()
            Match.objects.all().delete()
            Player.objects.all().delete()
            User.objects.filter(is_superuser=False).exclude(
                username=settings.SEED_ADMIN_USERNAME
            ).delete()

        demo_count = max(1, min(options['demo_players'], len(DEMO_PLAYER_NAMES)))

        admin = self._ensure_admin()
        players = self._ensure_demo_players(demo_count)

        self.stdout.write(self.style.SUCCESS(
            f'Seed complete: admin={admin.username}, players={len(players)}'
        ))
        self.stdout.write(
            f'Login: {settings.SEED_ADMIN_USERNAME} / {settings.SEED_ADMIN_PASSWORD}'
        )
        usernames = ', '.join(p.name.split()[0].lower() for p in players)
        self.stdout.write(f'Demo player logins ({usernames}): <username> / player123')

    def _ensure_admin(self) -> User:
        admin, created = User.objects.get_or_create(
            username=settings.SEED_ADMIN_USERNAME,
            defaults={
                'email': settings.SEED_ADMIN_EMAIL,
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created or not admin.check_password(settings.SEED_ADMIN_PASSWORD):
            admin.set_password(settings.SEED_ADMIN_PASSWORD)
            admin.role = User.Role.ADMIN
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()
            self.stdout.write(f'Admin user {"created" if created else "updated"}: {admin.username}')
        else:
            self.stdout.write(f'Admin user exists: {admin.username}')
        return admin

    def _ensure_demo_players(self, count: int) -> list[Player]:
        players: list[Player] = []
        for full_name in DEMO_PLAYER_NAMES[:count]:
            first = full_name.split()[0].lower()
            username = first
            email = f'{first}@demo.local'

            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'role': User.Role.PLAYER,
                    'first_name': full_name.split()[0],
                    'last_name': ' '.join(full_name.split()[1:]),
                },
            )
            if user_created:
                user.set_password('player123')
                user.save()

            player, created = Player.objects.get_or_create(
                name=full_name,
                defaults={
                    'email': email,
                    'user': user,
                    'is_active': True,
                },
            )
            if not created and player.user_id is None:
                player.user = user
                player.email = email
                player.save(update_fields=['user', 'email', 'updated_at'])

            players.append(player)

        self.stdout.write(f'Demo players ready: {len(players)}')
        return players
