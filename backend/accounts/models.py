from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user with an explicit role for RBAC."""

    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        PLAYER = 'PLAYER', 'Player'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PLAYER,
        db_index=True,
    )

    @property
    def is_app_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self) -> str:
        return f'{self.username} ({self.role})'
